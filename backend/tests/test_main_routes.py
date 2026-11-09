"""Route level tests for main.py with the language model calls faked."""

import pytest

import llm
import main


@pytest.fixture
def client():
    main.app.config["TESTING"] = True
    with main.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def replies(monkeypatch):
    """Queue reply texts for llm.generate and record each call."""
    queue = []
    calls = []

    def fake_generate(prompt=None, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return llm.LLMResponse(text=queue.pop(0), provider="gemini", model="test-model")

    monkeypatch.setattr(llm, "generate", fake_generate)
    return queue, calls


def test_ask_llm_helpers_pass_through_to_the_provider_module(replies):
    queue, calls = replies
    queue.extend(["plain answer", "pdf answer"])

    assert main.ask_llm("Hi") == "plain answer"
    assert main.ask_llm_with_pdf(b"%PDF-1.4", "Summarize", max_tokens=100) == "pdf answer"

    assert calls[0] == {"prompt": "Hi", "max_tokens": main.DEFAULT_MAX_TOKENS}
    assert calls[1] == {"prompt": "Summarize", "pdf_bytes": b"%PDF-1.4", "max_tokens": 100}


def test_flashcards_parse_a_fenced_json_reply(client, replies):
    queue, calls = replies
    queue.append('```json\n[{"front": "Osmosis", "back": "Water moving across a membrane."}]\n```')

    resp = client.post("/generate-flashcards", json={"text": "Osmosis notes"})

    assert resp.status_code == 200
    cards = resp.get_json()["data"]["cards"]
    assert len(cards) == 1
    assert "Osmosis notes" in calls[0]["prompt"]


def test_recap_route_returns_the_model_text(client, replies):
    queue, _ = replies
    queue.append("You were reviewing the Krebs cycle.")

    resp = client.post("/api/agent/recap", json={"documentTitle": "Biology"})

    assert resp.status_code == 200
    assert resp.get_json() == {"recap": "You were reviewing the Krebs cycle."}


def test_chat_route_without_a_session(client, replies):
    queue, calls = replies
    queue.append("Here is a hint.")

    resp = client.post(
        "/api/agent/chat",
        json={"message": "Help me", "context": {"documentTitle": "Algebra"}},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["response"] == "Here is a hint."
    assert body["pipeline"] == "full_context"
    assert calls[0]["messages"] == []


def test_missing_provider_keys_surface_as_a_server_error(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    resp = client.post("/api/agent/recap", json={"documentTitle": "Biology"})

    assert resp.status_code == 500
    assert "GROQ_API_KEY or GEMINI_API_KEY" in resp.get_json()["error"]
