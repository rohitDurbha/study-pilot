"""Tests for the document, session, agent, media and evaluation blueprints."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import agent_engine
import database
import knowledge_graph
import main
import study_agent
from routes import media


@pytest.fixture
def client():
    main.app.config["TESTING"] = True
    with main.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def db_session(monkeypatch):
    """Point every route at a fresh in-memory SQLite database."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    database.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    yield Session
    engine.dispose()


def test_main_only_builds_the_app_and_registers_blueprints():
    endpoints = {rule.rule: rule.endpoint for rule in main.app.url_map.iter_rules()}

    assert endpoints["/health"] == "health"
    assert endpoints["/api/documents/<doc_id>/graph"] == "documents.get_knowledge_graph"
    assert endpoints["/api/sections/<document_id>"] == "documents.get_sections"
    assert endpoints["/api/sessions/<session_id>/end"] == "sessions.end_session"
    assert endpoints["/api/agent/chat"] == "agent.agent_chat"
    assert endpoints["/api/agent/decide/quiz-result"] == "agent.agent_decide_quiz_result"
    assert endpoints["/api/tts"] == "media.text_to_speech"
    assert endpoints["/static/<path:filename>"] == "media.serve_static"
    assert endpoints["/api/eval/run/<document_id>"] == "evaluation.eval_run"
    assert endpoints["/api/rag/reindex/<document_id>"] == "evaluation.rag_reindex"

    owned_by_app = [e for e in endpoints.values() if "." not in e and e != "static"]
    assert owned_by_app == ["health"]


# Documents and sections


def test_documents_can_be_stored_listed_renamed_and_read(client, db_session, monkeypatch):
    graph = {"concepts": [{"id": "osmosis"}]}
    monkeypatch.setattr(knowledge_graph, "extract_knowledge_graph", lambda summary: graph)

    created = client.post("/api/documents", json={"id": "doc-1", "filename": "bio.pdf", "summary": "Cells"})
    assert created.status_code == 200
    assert created.get_json() == {"id": "doc-1", "knowledge_graph": graph}

    listed = client.get("/api/documents").get_json()["documents"]
    assert [d["id"] for d in listed] == ["doc-1"]

    renamed = client.post("/api/documents/doc-1/rename", json={"name": "  Biology  "})
    assert renamed.get_json() == {"ok": True, "name": "Biology"}

    latest = client.get("/api/documents/latest").get_json()
    assert latest["found"] is True
    assert latest["filename"] == "Biology"
    assert latest["concepts"] == [{"id": "osmosis"}]

    assert client.get("/api/documents/doc-1/graph").get_json()["knowledge_graph"] == graph
    assert client.get("/api/documents/nope/graph").status_code == 404
    assert client.post("/api/documents/nope/rename", json={"name": "x"}).status_code == 404
    assert client.post("/api/documents/doc-1/rename", json={"name": "  "}).status_code == 400


def test_a_failed_knowledge_graph_still_stores_the_document(client, db_session, monkeypatch):
    def broken(summary):
        raise RuntimeError("model down")

    monkeypatch.setattr(knowledge_graph, "extract_knowledge_graph", broken)

    resp = client.post("/api/documents", json={"filename": "notes.md", "summary": "x"})
    assert resp.status_code == 200
    assert resp.get_json()["knowledge_graph"] is None
    assert resp.get_json()["id"].startswith("doc-")


def test_sections_report_their_progress(client, db_session, monkeypatch):
    db = db_session()
    db.add(database.DocumentSection(id="s2", document_id="doc-1", title="Two", content="b", section_order=1))
    db.add(database.DocumentSection(id="s1", document_id="doc-1", title="One", content="a", section_order=0))
    db.add(database.SectionProgress(document_id="doc-1", section_id="s1", status="completed", quiz_score=80))
    db.commit()
    db.close()

    sections = client.get("/api/sections/doc-1").get_json()["sections"]
    assert [s["id"] for s in sections] == ["s1", "s2"]
    assert sections[0]["status"] == "completed"
    assert sections[0]["quiz_score"] == 80
    assert sections[1]["status"] == "not_started"

    calls = []
    monkeypatch.setattr(agent_engine, "update_section_progress", lambda *args: calls.append(args))
    resp = client.post("/api/sections/doc-1/s2/progress", json={"status": "in_progress"})
    assert resp.get_json() == {"ok": True}
    assert calls == [("doc-1", "s2", "in_progress", None)]


# Sessions


def test_a_session_records_focus_and_distractions_and_reports_analytics(client, db_session):
    session_id = client.post("/api/sessions", json={"document_id": "doc-1"}).get_json()["id"]

    db = db_session()
    session = db.query(database.StudySession).filter_by(id=session_id).first()
    session.started_at = datetime.utcnow() - timedelta(minutes=10)
    db.commit()
    db.close()

    focus = client.post(
        f"/api/sessions/{session_id}/focus",
        json={"events": [{"score": 80, "contentType": "text"}, {"score": 60, "contentType": "quiz"}]},
    )
    assert focus.get_json() == {"recorded": 2}
    assert client.post(f"/api/sessions/{session_id}/distraction", json={"duration_sec": 60}).get_json() == {"ok": True}

    latest = client.get("/api/sessions/latest").get_json()
    assert latest["id"] == session_id
    assert latest["distraction_count"] == 1

    assert client.get(f"/api/sessions/{session_id}/analytics").get_json() == {"status": "session still active"}

    summary = client.post(f"/api/sessions/{session_id}/end").get_json()
    assert summary["avg_focus_score"] == 70
    assert summary["distraction_count"] == 1
    assert summary["avg_distraction_sec"] == 60
    assert summary["content_effectiveness"]["quiz"] == {"avg_focus": 60, "time_pct": 50}
    assert 9.9 <= summary["total_duration_min"] <= 10.1
    assert client.get(f"/api/sessions/{session_id}/analytics").get_json() == summary


def test_unknown_sessions_answer_404(client, db_session):
    assert client.post("/api/sessions/nope/end").status_code == 404
    assert client.get("/api/sessions/nope/analytics").status_code == 404
    assert client.get("/api/sessions/latest").get_json() == {"found": False}


def test_focus_events_must_be_a_list(client, db_session):
    resp = client.post("/api/sessions/s/focus", json={"events": "lots"})
    assert resp.status_code == 400


# Agent


def test_agent_chat_saves_history_and_uses_rag_when_asked(client, db_session, monkeypatch):
    seen = {}

    def fake_rag(**kwargs):
        seen.update(kwargs)
        return {"response": "From the notes.", "sources": [{"section_id": "s1"}]}

    monkeypatch.setattr(study_agent, "chat_with_agent_rag", fake_rag)

    db = db_session()
    db.add(database.StudySession(id="sess-1", document_id="doc-1", started_at=datetime.utcnow()))
    db.commit()
    db.close()

    resp = client.post(
        "/api/agent/chat",
        json={"message": "What is osmosis?", "sessionId": "sess-1", "pipeline": "rag", "context": {"focusScore": 50}},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {
        "response": "From the notes.",
        "sources": [{"section_id": "s1"}],
        "pipeline": "rag",
    }
    assert seen["document_id"] == "doc-1"
    assert seen["focus_score"] == 50

    history = client.get("/api/agent/history/sess-1").get_json()["messages"]
    assert history == [
        {"role": "user", "content": "What is osmosis?"},
        {"role": "assistant", "content": "From the notes."},
    ]


def test_agent_chat_without_a_session_uses_full_context(client, db_session, monkeypatch):
    monkeypatch.setattr(study_agent, "chat_with_agent", lambda **kwargs: "Hello there.")

    resp = client.post("/api/agent/chat", json={"message": "Hi"})
    assert resp.get_json() == {"response": "Hello there.", "sources": [], "pipeline": "full_context"}
    assert client.post("/api/agent/chat", json={"message": ""}).status_code == 400
    assert client.post("/api/agent/chat", json={"message": "Hi", "context": "x"}).status_code == 400


def test_agent_recap_and_decisions_pass_through(client, monkeypatch):
    class Action:
        def __init__(self, name):
            self.name = name

        def to_dict(self):
            return {"action": self.name}

    calls = []
    monkeypatch.setattr(study_agent, "generate_distraction_recap", lambda **kwargs: "Welcome back.")
    monkeypatch.setattr(agent_engine, "decide_welcome", lambda doc: Action("welcome"))
    monkeypatch.setattr(agent_engine, "decide_focus_drop", lambda *a: calls.append(a) or Action("break"))
    monkeypatch.setattr(agent_engine, "decide_section_complete", lambda *a: Action("quiz"))
    monkeypatch.setattr(agent_engine, "decide_quiz_result", lambda *a: calls.append(a) or Action("review"))
    monkeypatch.setattr(agent_engine, "decide_distraction_return", lambda *a: Action("recap"))

    assert client.post("/api/agent/recap", json={"documentTitle": "Bio"}).get_json() == {"recap": "Welcome back."}
    assert client.post("/api/agent/decide/welcome", json={"document_id": "d"}).get_json() == {"action": "welcome"}
    assert client.post("/api/agent/decide/welcome", json={}).status_code == 400
    assert client.post("/api/agent/decide/focus-drop", json={"document_id": "d"}).get_json() == {"action": "break"}
    assert client.post("/api/agent/decide/section-complete", json={}).get_json() == {"action": "quiz"}
    assert client.post(
        "/api/agent/decide/quiz-result", json={"document_id": "d", "score": 2, "total": 5}
    ).get_json() == {"action": "review"}
    assert client.post("/api/agent/decide/distraction-return", json={}).get_json() == {"action": "recap"}

    assert calls == [("d", "", "text"), ("d", "", 2, 5, [])]


# Media


def test_tts_writes_audio_that_the_static_route_serves(client, tmp_path, monkeypatch):
    def fake_speech(text, voice, directory):
        path = tmp_path / "clip.mp3"
        path.write_bytes(b"ID3" + text.encode())
        return str(path)

    monkeypatch.setattr(media, "STATIC_DIR", str(tmp_path))
    monkeypatch.setattr(media, "synthesize_speech", fake_speech)

    resp = client.post("/api/tts", json={"text": "Hello"})
    assert resp.get_json() == {"url": "/static/clip.mp3"}

    audio = client.get("/static/clip.mp3")
    assert audio.status_code == 200
    assert audio.data == b"ID3Hello"
    assert client.post("/api/tts", json={"text": ""}).status_code == 400


def test_tts_truncates_long_text(client, tmp_path, monkeypatch):
    seen = {}

    def fake_speech(text, voice, directory):
        seen["length"] = len(text)
        return str(tmp_path / "long.mp3")

    monkeypatch.setattr(media, "STATIC_DIR", str(tmp_path))
    monkeypatch.setattr(media, "synthesize_speech", fake_speech)

    client.post("/api/tts", json={"text": "a" * (media.TTS_MAX_CHARS + 50)})
    assert seen["length"] == media.TTS_MAX_CHARS


# Evaluation


def test_eval_run_generates_test_cases_only_when_none_exist(client, db_session, monkeypatch):
    import eval_harness

    generated = []
    monkeypatch.setattr(eval_harness, "generate_test_set", lambda doc: generated.append(doc) or [])
    monkeypatch.setattr(eval_harness, "run_evaluation", lambda doc: {"document_id": doc, "rag_wins": 1})
    monkeypatch.setattr(eval_harness, "get_eval_runs", lambda doc: [{"id": 1}])
    monkeypatch.setattr(eval_harness, "get_eval_run_detail", lambda run_id: {"id": run_id})

    assert client.post("/api/eval/run/doc-1").get_json() == {"document_id": "doc-1", "rag_wins": 1}
    assert generated == ["doc-1"]
    assert client.get("/api/eval/runs/doc-1").get_json() == {"runs": [{"id": 1}]}
    assert client.get("/api/eval/detail/7").get_json() == {"id": 7}
    assert client.post("/api/eval/generate-tests/doc-1").get_json() == {"count": 0, "test_cases": []}


# Malformed request bodies


@pytest.mark.parametrize(
    "path",
    [
        "/api/documents",
        "/api/documents/doc-1/rename",
        "/api/sections/doc-1/s1/progress",
        "/api/sessions",
        "/api/sessions/s/focus",
        "/api/sessions/s/distraction",
        "/api/agent/chat",
        "/api/agent/recap",
        "/api/agent/decide/welcome",
        "/api/agent/decide/focus-drop",
        "/api/tts",
        "/generate-flashcards",
        "/generate-quiz",
        "/generate-mindmap",
        "/generate-mini-game",
    ],
)
def test_a_missing_or_broken_body_is_a_clear_400(client, path):
    missing = client.post(path)
    broken = client.post(path, data="{not json", content_type="application/json")
    wrong_shape = client.post(path, json=["a", "list"])

    for resp in (missing, broken, wrong_shape):
        assert resp.status_code == 400
        assert resp.is_json
        assert "JSON" in resp.get_json()["error"]
