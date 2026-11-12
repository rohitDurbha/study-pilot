"""Tests for smoke_llm.py, using the fake HTTP session from the llm tests."""

import io

import requests

import llm
import smoke_llm
from tests.test_llm import FakeResponse, FakeSession, gemini_ok, groq_ok

BOTH = llm.LLMConfig(groq_api_key="gk", gemini_api_key="mk")


def run(config, session, providers=None, **kwargs):
    out = io.StringIO()
    code = smoke_llm.run(
        providers or config.providers, config, prompt="ping", session=session, out=out, **kwargs
    )
    return code, out.getvalue().splitlines()


def test_each_provider_is_called_on_its_own():
    session = FakeSession(groq=[groq_ok("pong")], gemini=[gemini_ok("pong")])
    code, lines = run(BOTH, session)

    assert code == 0
    assert [c["host"] for c in session.calls] == ["groq", "gemini"]
    assert lines[0].startswith("ok") and "groq" in lines[0] and "11 in / 7 out" in lines[0]
    assert lines[1].startswith("ok") and "gemini" in lines[1] and "pong" in lines[1]


def test_a_failing_provider_is_reported_without_falling_back():
    error = FakeResponse(status=401, text='{"error": "invalid api key"}')
    session = FakeSession(groq=[error], gemini=[gemini_ok("pong")])
    code, lines = run(BOTH, session)

    assert code == 1
    # Groq failing must not send its prompt on to Gemini, so Gemini is hit once.
    assert [c["host"] for c in session.calls] == ["groq", "gemini"]
    assert lines[0].startswith("failed") and "HTTP 401" in lines[0]
    assert lines[1].startswith("ok")


def test_missing_keys_are_skipped_and_do_not_fail_the_run():
    config = llm.LLMConfig(gemini_api_key="mk")
    session = FakeSession(gemini=[gemini_ok("pong")])
    code, lines = run(config, session)

    assert code == 0
    assert lines[0].startswith("skipped") and "GROQ_API_KEY is not set" in lines[0]
    assert lines[1].startswith("ok")


def test_no_keys_at_all_exits_with_two():
    session = FakeSession()
    code, lines = run(llm.LLMConfig(), session)

    assert code == 2
    assert session.calls == []
    assert "No provider has an API key" in lines[-1]


def test_network_errors_are_reported_as_failures():
    session = FakeSession(groq=[requests.ConnectionError("no route to host")])
    code, lines = run(BOTH, session, providers=("groq",))

    assert code == 1
    assert "no route to host" in lines[0]


def test_json_mode_checks_that_the_reply_parses():
    session = FakeSession(groq=[groq_ok('{"reply": "pong"}')], gemini=[gemini_ok("not json")])
    code, lines = run(BOTH, session, json_mode=True)

    assert code == 1
    assert session.calls[0]["json"]["response_format"] == {"type": "json_object"}
    assert session.calls[1]["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert lines[0].startswith("ok")
    assert lines[1].startswith("failed") and "not valid JSON" in lines[1]


def test_check_provider_times_the_request():
    ticks = iter([10.0, 12.5])
    session = FakeSession(groq=[groq_ok("pong")])
    result = smoke_llm.check_provider(
        "groq", BOTH, prompt="ping", session=session, clock=lambda: next(ticks)
    )

    assert result.status == "ok"
    assert result.seconds == 2.5
    assert session.calls[0]["json"]["max_completion_tokens"] == smoke_llm.MAX_TOKENS


def test_main_reads_the_provider_flag(monkeypatch, capsys):
    monkeypatch.setattr(smoke_llm, "load_dotenv", lambda: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "mk")
    seen = {}

    def fake_run(providers, config, *, prompt, json_mode=False):
        seen.update(providers=providers, prompt=prompt, json_mode=json_mode)
        return 0

    monkeypatch.setattr(smoke_llm, "run", fake_run)
    assert smoke_llm.main(["--provider", "gemini", "--json-mode"]) == 0
    assert seen == {
        "providers": ("gemini",),
        "prompt": smoke_llm.JSON_PROMPT,
        "json_mode": True,
    }


def test_main_rejects_an_unknown_provider_order(monkeypatch, capsys):
    monkeypatch.setattr(smoke_llm, "load_dotenv", lambda: None)
    monkeypatch.setenv("LLM_PROVIDERS", "groq,openai")

    assert smoke_llm.main([]) == 2
    assert "Unknown provider" in capsys.readouterr().err
