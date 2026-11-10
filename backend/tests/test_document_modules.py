"""Tests for document_processor.py and knowledge_graph.py with llm faked."""

import json

import pytest

import document_processor
import knowledge_graph
import llm


@pytest.fixture
def replies(monkeypatch):
    """Queue reply texts for llm.generate and record each call."""
    queue = []
    calls = []

    def fake_generate(prompt=None, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return llm.LLMResponse(text=queue.pop(0), provider="groq", model="test-model")

    monkeypatch.setattr(llm, "generate", fake_generate)
    return queue, calls


SECTIONED = {
    "title": "Cell Biology",
    "summary": "How cells work.",
    "sections": [
        {"title": "Membranes", "content": "## Membranes", "concepts": ["membrane"]},
        {"title": "Transport", "content": "## Transport", "concepts": ["osmosis"]},
    ],
    "knowledge_graph": {"concepts": []},
}


def test_pdf_documents_are_sent_with_their_bytes_and_numbered(replies):
    queue, calls = replies
    queue.append("```json\n" + json.dumps(SECTIONED) + "\n```")

    result = document_processor.process_document(b"%PDF-1.4 fake", "cells.pdf")

    assert calls[0]["pdf_bytes"] == b"%PDF-1.4 fake"
    assert calls[0]["json_mode"] is True
    assert calls[0]["max_tokens"] == document_processor.SECTION_MAX_TOKENS
    assert "structured study sections" in calls[0]["prompt"]
    assert [s["id"] for s in result["sections"]] == ["section-1", "section-2"]
    assert [s["order"] for s in result["sections"]] == [1, 2]


def test_text_documents_are_trimmed_and_sent_without_a_pdf(replies):
    queue, calls = replies
    queue.append(json.dumps(SECTIONED))

    long_text = "a" * 30000 + "TAIL_MARKER"
    result = document_processor.process_text_document(long_text, "notes.md")

    assert "pdf_bytes" not in calls[0]
    assert calls[0]["json_mode"] is True
    assert "TAIL_MARKER" not in calls[0]["prompt"]
    assert result["sections"][1]["id"] == "section-2"


def test_a_reply_that_is_not_json_raises(replies):
    queue, _ = replies
    queue.append("Sorry, I cannot help with that.")

    with pytest.raises(json.JSONDecodeError):
        document_processor.process_text_document("short notes", "notes.txt")


def test_knowledge_graph_includes_the_summary_and_parses_the_reply(replies):
    queue, calls = replies
    graph = {"concepts": [{"id": "osmosis", "name": "Osmosis", "prerequisites": ["membrane"]}]}
    queue.append("```\n" + json.dumps(graph) + "\n```")

    result = knowledge_graph.extract_knowledge_graph("Osmosis moves water across membranes.")

    assert result == graph
    assert "Osmosis moves water across membranes." in calls[0]["prompt"]
    assert calls[0]["json_mode"] is True
    assert calls[0]["max_tokens"] == knowledge_graph.GRAPH_MAX_TOKENS


def test_provider_errors_reach_the_caller(monkeypatch):
    def failing_generate(prompt=None, **kwargs):
        raise llm.LLMError("Every provider failed.")

    monkeypatch.setattr(llm, "generate", failing_generate)

    with pytest.raises(llm.LLMError):
        knowledge_graph.extract_knowledge_graph("anything")
