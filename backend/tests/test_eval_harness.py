"""Tests for the language model calls in eval_harness.py.

rag_pipeline imports chromadb, which pulls in PyTorch until roadmap item 3
replaces it. When chromadb is not installed a stand in module is used so the
harness can still be imported and its prompts tested.
"""

import importlib.util
import json
import sys
import types

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if importlib.util.find_spec("chromadb") is None and "rag_pipeline" not in sys.modules:
    stub = types.ModuleType("rag_pipeline")
    stub.retrieve_chunks = lambda *args, **kwargs: []
    sys.modules["rag_pipeline"] = stub

import database  # noqa: E402
import eval_harness  # noqa: E402
import llm  # noqa: E402


@pytest.fixture
def replies(monkeypatch):
    """Queue reply texts for llm.generate and record each call."""
    queue = []
    calls = []

    def fake_generate(prompt=None, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return llm.LLMResponse(text=reply, provider="groq", model="test-model")

    monkeypatch.setattr(llm, "generate", fake_generate)
    return queue, calls


@pytest.fixture
def memory_db(monkeypatch):
    """Point the harness at a throwaway in-memory database."""
    engine = create_engine("sqlite://")
    database.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(eval_harness, "SessionLocal", Session)
    return Session


def test_judge_scores_are_parsed_from_a_fenced_reply(replies):
    queue, calls = replies
    queue.append('```json\n{"accuracy": 0.9, "groundedness": 0.8, "relevance": 1.0}\n```')

    scores = eval_harness.judge_answer("What is osmosis?", "Water moving", "Water moves", ["chunk"])

    assert scores == {"accuracy": 0.9, "groundedness": 0.8, "relevance": 1.0}
    assert calls[0]["json_mode"] is True
    assert calls[0]["max_tokens"] == eval_harness.JUDGE_MAX_TOKENS
    assert "Candidate Answer: Water moves" in calls[0]["prompt"]


def test_judge_falls_back_to_zero_scores_when_every_provider_fails(replies):
    queue, _ = replies
    queue.append(llm.LLMError("Every provider failed."))

    scores = eval_harness.judge_answer("Q", "A", "B")

    assert scores == {"accuracy": 0.0, "groundedness": 0.0, "relevance": 0.0}


def test_test_set_generation_stores_one_case_per_pair(replies, memory_db):
    queue, calls = replies
    # Sections shorter than 100 characters are skipped by the harness, so the
    # fixture text is repeated to clear that bar.
    db = memory_db()
    db.add(database.Document(id="doc-1", filename="cells.pdf"))
    db.add_all([
        database.DocumentSection(
            id="sec-1", document_id="doc-1", title="Membranes",
            content="Membranes separate cells from their surroundings. " * 3, section_order=1,
        ),
        database.DocumentSection(
            id="sec-2", document_id="doc-1", title="Transport",
            content="Osmosis moves water across a membrane. " * 3, section_order=2,
        ),
    ])
    db.commit()
    db.close()

    pairs = [{"question": "What does osmosis move?", "answer": "Water", "source_excerpt": "Osmosis moves water"}]
    queue.append("not json at all")
    queue.append("```json\n" + json.dumps(pairs) + "\n```")

    cases = eval_harness.generate_test_set("doc-1", questions_per_section=1)

    assert len(calls) == 2
    assert "json_mode" not in calls[0]
    assert calls[0]["max_tokens"] == eval_harness.TESTSET_MAX_TOKENS
    assert [c["section_id"] for c in cases] == ["sec-2"]
    assert cases[0]["ground_truth"] == "Water"

    db = memory_db()
    assert db.query(database.EvalTestCase).count() == 1
    db.close()
