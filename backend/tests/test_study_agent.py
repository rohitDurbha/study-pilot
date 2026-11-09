"""Tests for study_agent.py with llm.generate replaced by a recorder."""

import sys
import types

import pytest

import llm
import study_agent


class Recorder:
    def __init__(self, text="Reply text", input_tokens=12, output_tokens=7):
        self.calls = []
        self.response = llm.LLMResponse(
            text=text,
            provider="groq",
            model="test-model",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def __call__(self, prompt=None, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return self.response


@pytest.fixture
def fake_generate(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(llm, "generate", recorder)
    return recorder


def test_chat_sends_system_prompt_history_and_message(fake_generate):
    history = [
        {"role": "user", "content": "What is entropy?"},
        {"role": "assistant", "content": "A measure of disorder."},
    ]

    reply = study_agent.chat_with_agent(
        "Give me an example",
        history,
        document_title="Thermodynamics",
        summary_text="Heat and work.",
        focus_score=40,
    )

    assert reply == "Reply text"
    call = fake_generate.calls[0]
    assert call["prompt"] == "Give me an example"
    assert call["messages"] == history
    assert call["max_tokens"] == study_agent.CHAT_MAX_TOKENS
    assert 'Document: "Thermodynamics"' in call["system"]
    assert "Student's focus score: 40%" in call["system"]


def test_chat_drops_empty_and_unknown_turns(fake_generate):
    history = [
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": "   "},
        {"role": "assistant", "content": None},
        {"role": "assistant", "content": " Kept "},
    ]

    study_agent.chat_with_agent("Next", history)

    assert fake_generate.calls[0]["messages"] == [{"role": "assistant", "content": "Kept"}]


def test_rag_chat_reports_sources_usage_and_provider(fake_generate, monkeypatch):
    chunks = [
        {"text": "x" * 300, "section_id": "s1", "section_title": "Intro", "score": 0.9},
    ]
    fake_rag = types.ModuleType("rag_pipeline")
    fake_rag.retrieve_chunks = lambda document_id, query, top_k=5: chunks
    fake_rag.build_rag_prompt = lambda query, found: "RETRIEVED CONTEXT [1] Intro"
    monkeypatch.setitem(sys.modules, "rag_pipeline", fake_rag)

    result = study_agent.chat_with_agent_rag(
        "Explain the intro",
        [],
        document_id="doc-1",
        knowledge_graph={"concepts": [{"name": "Energy"}, {"name": "Work"}]},
        quiz_performance={"correct": 3, "total": 4},
    )

    call = fake_generate.calls[0]
    assert call["prompt"] == "Explain the intro"
    assert "RETRIEVED CONTEXT [1] Intro" in call["system"]
    assert "KEY CONCEPTS: Energy, Work" in call["system"]
    assert "QUIZ: 3/4 correct" in call["system"]
    assert result["response"] == "Reply text"
    assert result["usage"] == {"input_tokens": 12, "output_tokens": 7}
    assert result["provider"] == "groq"
    assert result["model"] == "test-model"
    assert result["sources"][0]["text"] == "x" * 200


def test_recap_uses_a_short_text_prompt(fake_generate):
    recap = study_agent.generate_distraction_recap(
        document_title="Cells",
        summary_text="Mitochondria make energy.",
        last_content_type="flashcards",
        last_section_context="Organelles",
    )

    assert recap == "Reply text"
    call = fake_generate.calls[0]
    assert call["max_tokens"] == study_agent.RECAP_MAX_TOKENS
    assert "Cells" in call["prompt"]
    assert "They were last reading about: Organelles" in call["prompt"]
    assert "system" not in call


def test_errors_from_the_provider_module_reach_the_caller(monkeypatch):
    def fail(*args, **kwargs):
        raise llm.LLMError("No language model provider is configured.")

    monkeypatch.setattr(llm, "generate", fail)

    with pytest.raises(llm.LLMError):
        study_agent.chat_with_agent("Hello", [])
