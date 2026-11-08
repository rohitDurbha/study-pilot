"""Tests for llm.py. The network is never touched; a fake session records requests."""

import base64

import pytest
import requests

import llm


class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


class FakeSession:
    """Returns queued replies per host and remembers every request."""

    def __init__(self, groq=None, gemini=None):
        self.replies = {"groq": list(groq or []), "gemini": list(gemini or [])}
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        host = "groq" if "groq.com" in url else "gemini"
        self.calls.append({"host": host, "url": url, "json": json, "headers": headers, "timeout": timeout})
        reply = self.replies[host].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def groq_ok(text="hello from groq", prompt_tokens=11, completion_tokens=7):
    return FakeResponse(
        payload={
            "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }
    )


def gemini_ok(text="hello from gemini"):
    return FakeResponse(
        payload={
            "candidates": [
                {
                    "content": {"parts": [{"text": "thinking...", "thought": True}, {"text": text}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 5},
        }
    )


BOTH = llm.LLMConfig(groq_api_key="gk", gemini_api_key="mk")


def make_pdf(text):
    """Build a one page PDF whose text layer holds text, with a valid xref table."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET" if text else ""
    objects = [
        "<</Type/Catalog/Pages 2 0 R>>",
        "<</Type/Pages/Kids[3 0 R]/Count 1>>",
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]"
        "/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
        "<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        f"<</Length {len(stream)}>>stream\n{stream}\nendstream",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


# load_config


def test_load_config_defaults():
    config = llm.load_config({})
    assert config.providers == ("groq", "gemini")
    assert config.groq_model == llm.DEFAULT_GROQ_MODEL
    assert config.gemini_model == llm.DEFAULT_GEMINI_MODEL
    assert config.active_providers == ()


def test_load_config_reads_overrides():
    config = llm.load_config(
        {
            "LLM_PROVIDERS": " Gemini , groq ",
            "GROQ_API_KEY": " gk ",
            "GEMINI_API_KEY": "mk",
            "GROQ_MODEL": "llama-3.1-8b-instant",
            "GEMINI_MODEL": "gemini-3.5-flash-lite",
            "LLM_TIMEOUT_SECONDS": "15",
            "LLM_PDF_TEXT_LIMIT": "1000",
        }
    )
    assert config.providers == ("gemini", "groq")
    assert config.active_providers == ("gemini", "groq")
    assert config.groq_api_key == "gk"
    assert config.groq_model == "llama-3.1-8b-instant"
    assert config.gemini_model == "gemini-3.5-flash-lite"
    assert config.timeout_seconds == 15.0
    assert config.pdf_text_limit == 1000


def test_load_config_ignores_bad_numbers():
    config = llm.load_config({"LLM_TIMEOUT_SECONDS": "soon"})
    assert config.timeout_seconds == llm.DEFAULT_TIMEOUT_SECONDS


def test_load_config_rejects_unknown_provider():
    with pytest.raises(llm.LLMError, match="openai"):
        llm.load_config({"LLM_PROVIDERS": "groq,openai"})


def test_providers_without_keys_are_skipped():
    config = llm.LLMConfig(gemini_api_key="mk")
    assert config.active_providers == ("gemini",)


# generate


def test_generate_without_keys_raises():
    with pytest.raises(llm.LLMError, match="GROQ_API_KEY or GEMINI_API_KEY"):
        llm.generate("hi", config=llm.LLMConfig(), session=FakeSession())


def test_generate_needs_a_prompt():
    with pytest.raises(ValueError):
        llm.generate(config=BOTH, session=FakeSession())


def test_generate_rejects_history_ending_with_assistant():
    with pytest.raises(ValueError):
        llm.generate(messages=[{"role": "assistant", "content": "x"}], config=BOTH, session=FakeSession())


def test_groq_request_shape_and_reply():
    session = FakeSession(groq=[groq_ok()])
    reply = llm.generate(
        "What is osmosis?",
        system="You are a tutor.",
        messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        max_tokens=300,
        json_mode=True,
        config=BOTH,
        session=session,
    )

    assert reply.text == "hello from groq"
    assert (reply.provider, reply.model) == ("groq", llm.DEFAULT_GROQ_MODEL)
    assert (reply.input_tokens, reply.output_tokens) == (11, 7)

    call = session.calls[0]
    assert call["headers"]["Authorization"] == "Bearer gk"
    assert call["timeout"] == llm.DEFAULT_TIMEOUT_SECONDS
    body = call["json"]
    assert body["model"] == llm.DEFAULT_GROQ_MODEL
    assert body["max_completion_tokens"] == 300
    assert body["response_format"] == {"type": "json_object"}
    assert body["reasoning_effort"] == "low"
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user"]
    assert body["messages"][-1]["content"] == "What is osmosis?"


def test_reasoning_effort_only_sent_to_reasoning_models():
    session = FakeSession(groq=[groq_ok()])
    config = llm.LLMConfig(groq_api_key="gk", groq_model="llama-3.1-8b-instant")
    llm.generate("hi", config=config, session=session)
    assert "reasoning_effort" not in session.calls[0]["json"]
    assert "response_format" not in session.calls[0]["json"]


def test_gemini_request_shape_and_reply():
    session = FakeSession(gemini=[gemini_ok()])
    config = llm.LLMConfig(gemini_api_key="mk")
    reply = llm.generate(
        "Summarize",
        system="Be brief.",
        messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        max_tokens=200,
        json_mode=True,
        config=config,
        session=session,
    )

    assert reply.text == "hello from gemini"  # the thought part is dropped
    assert (reply.provider, reply.input_tokens, reply.output_tokens) == ("gemini", 20, 5)

    call = session.calls[0]
    assert call["url"].endswith(f"/models/{llm.DEFAULT_GEMINI_MODEL}:generateContent")
    assert call["headers"] == {"x-goog-api-key": "mk"}
    body = call["json"]
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["systemInstruction"] == {"parts": [{"text": "Be brief."}]}
    assert body["generationConfig"] == {"maxOutputTokens": 200, "responseMimeType": "application/json"}


@pytest.mark.parametrize(
    "failure",
    [
        FakeResponse(status=429, text="rate limited"),
        requests.ConnectionError("network down"),
        groq_ok(text="   "),
    ],
    ids=["http-error", "connection-error", "empty-reply"],
)
def test_falls_back_to_gemini_when_groq_fails(failure):
    session = FakeSession(groq=[failure], gemini=[gemini_ok()])
    reply = llm.generate("hi", config=BOTH, session=session)
    assert reply.provider == "gemini"
    assert [c["host"] for c in session.calls] == ["groq", "gemini"]


def test_error_lists_every_failure_without_keys():
    session = FakeSession(
        groq=[FakeResponse(status=500, text="boom")],
        gemini=[FakeResponse(status=403, text="denied")],
    )
    with pytest.raises(llm.LLMError) as info:
        llm.generate("hi", config=BOTH, session=session)
    message = str(info.value)
    assert "groq failed, HTTP 500 boom" in message
    assert "gemini failed, HTTP 403 denied" in message
    assert "gk" not in message and "mk" not in message


def test_provider_order_is_respected():
    session = FakeSession(gemini=[gemini_ok()])
    config = llm.LLMConfig(providers=("gemini", "groq"), groq_api_key="gk", gemini_api_key="mk")
    assert llm.generate("hi", config=config, session=session).provider == "gemini"
    assert len(session.calls) == 1


def test_generate_text_returns_only_text():
    session = FakeSession(groq=[groq_ok(text="just text")])
    assert llm.generate_text("hi", config=BOTH, session=session) == "just text"


# PDFs


def test_pdf_to_text_reads_the_text_layer():
    assert "Photosynthesis basics" in llm.pdf_to_text(make_pdf("Photosynthesis basics"))


def test_pdf_goes_to_groq_as_extracted_text():
    session = FakeSession(groq=[groq_ok()])
    llm.generate("Split into sections", pdf_bytes=make_pdf("Cell biology notes"), config=BOTH, session=session)
    content = session.calls[0]["json"]["messages"][-1]["content"]
    assert "Cell biology notes" in content
    assert content.endswith("Split into sections")


def test_pdf_without_text_skips_groq_and_uses_gemini_inline():
    pdf = make_pdf("")
    session = FakeSession(gemini=[gemini_ok()])
    reply = llm.generate("Split into sections", pdf_bytes=pdf, config=BOTH, session=session)

    assert reply.provider == "gemini"
    assert [c["host"] for c in session.calls] == ["gemini"]
    parts = session.calls[0]["json"]["contents"][-1]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "application/pdf"
    assert base64.standard_b64decode(parts[0]["inline_data"]["data"]) == pdf
    assert parts[1] == {"text": "Split into sections"}


def test_long_pdf_skips_groq():
    config = llm.LLMConfig(groq_api_key="gk", gemini_api_key="mk", pdf_text_limit=5)
    session = FakeSession(gemini=[gemini_ok()])
    reply = llm.generate("go", pdf_bytes=make_pdf("Much longer than five"), config=config, session=session)
    assert reply.provider == "gemini"


def test_unreadable_pdf_skips_groq():
    session = FakeSession(gemini=[gemini_ok()])
    reply = llm.generate("go", pdf_bytes=b"not a pdf", config=BOTH, session=session)
    assert reply.provider == "gemini"


def test_pdf_only_groq_reports_skip():
    config = llm.LLMConfig(groq_api_key="gk")
    with pytest.raises(llm.LLMError, match="groq skipped, the PDF has no text layer"):
        llm.generate("go", pdf_bytes=make_pdf(""), config=config, session=FakeSession())
