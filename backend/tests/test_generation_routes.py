"""Tests for the generation blueprint with the model and database faked."""

import io
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
import embeddings
import llm
import main


@pytest.fixture
def client():
    main.app.config["TESTING"] = True
    with main.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def replies(monkeypatch):
    """Queue reply texts for llm.generate and record each prompt."""
    queue = []
    prompts = []

    def fake_generate(prompt=None, **kwargs):
        prompts.append(prompt)
        return llm.LLMResponse(text=queue.pop(0), provider="groq", model="test-model")

    monkeypatch.setattr(llm, "generate", fake_generate)
    return queue, prompts


@pytest.fixture
def db_session(monkeypatch):
    """Point the routes at a fresh in-memory SQLite database."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    database.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    yield Session
    engine.dispose()


def test_generation_routes_are_served_by_the_blueprint():
    endpoints = {rule.rule: rule.endpoint for rule in main.app.url_map.iter_rules()}

    assert endpoints["/upload"] == "generation.upload_pdf"
    assert endpoints["/generate-flashcards"] == "generation.generate_flashcards"
    assert endpoints["/generate-quiz"] == "generation.generate_quiz"
    assert endpoints["/generate-mindmap"] == "generation.generate_mindmap"
    assert endpoints["/generate-mini-game"] == "generation.generate_mini_game"


@pytest.mark.parametrize(
    "path", ["/generate-flashcards", "/generate-quiz", "/generate-mindmap", "/generate-mini-game"]
)
def test_generators_reject_a_body_without_text(client, path):
    resp = client.post(path, json={"document_id": "doc-1"})

    assert resp.status_code == 400
    assert resp.get_json() == {"error": "No text provided"}


def test_quiz_numbers_the_questions_from_the_model_reply(client, replies):
    queue, prompts = replies
    queue.append(json.dumps([
        {
            "question": "Why does ice float?",
            "options": ["Mass", "Density", "Color", "Heat"],
            "correctOptionIndex": 1,
            "explanation": "Ice is less dense than water.",
        }
    ]))

    resp = client.post("/generate-quiz", json={"text": "Water and ice"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "quiz"
    assert body["data"]["questions"][0]["id"] == "q1"
    assert body["data"]["questions"][0]["correctOptionIndex"] == 1
    assert "Water and ice" in prompts[0]


def test_mindmap_and_mini_game_pass_the_model_json_through(client, replies):
    queue, _ = replies
    mindmap = {"id": "m", "type": "mindmap", "data": {"title": "Cells", "root": {"title": "Cell", "children": []}}}
    game = {"id": "g", "type": "mini-game", "data": {"title": "Match", "challenges": []}}
    queue.extend(["```json\n" + json.dumps(mindmap) + "\n```", json.dumps(game)])

    mindmap_resp = client.post("/generate-mindmap", json={"text": "Cell biology"})
    game_resp = client.post("/generate-mini-game", json={"text": "Cell biology"})

    assert mindmap_resp.get_json() == mindmap
    assert game_resp.get_json() == game


def test_generated_content_is_cached_per_document_and_section(client, replies, db_session):
    queue, prompts = replies
    queue.append(json.dumps([{"front": "Mitosis", "back": "Cell division."}]))
    body = {"text": "Cell cycle", "document_id": "doc-1", "section_id": "section-1"}

    first = client.post("/generate-flashcards", json=body)
    second = client.post("/generate-flashcards", json=body)

    assert first.status_code == 200
    assert second.get_json() == first.get_json()
    assert len(prompts) == 1

    db = db_session()
    assert db.query(database.GeneratedContent).filter_by(
        document_id="doc-1", section_id="section-1", content_type="flipcard"
    ).count() == 1
    db.close()


def test_model_reply_that_is_not_json_returns_a_server_error(client, replies):
    queue, _ = replies
    queue.append("Sorry, I cannot help with that.")

    resp = client.post("/generate-quiz", json={"text": "Anything"})

    assert resp.status_code == 500
    assert "error" in resp.get_json()


def test_upload_without_a_file_is_rejected(client):
    resp = client.post("/upload", data={}, content_type="multipart/form-data")

    assert resp.status_code == 400
    assert resp.get_json() == {"error": "No file uploaded"}


def test_upload_of_an_empty_file_is_rejected(client):
    resp = client.post(
        "/upload",
        data={"file": (io.BytesIO(b""), "notes.md")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Empty file"}


def test_markdown_upload_saves_sections_and_progress(client, replies, db_session):
    class OneDimEmbedder:
        def embed(self, texts, batch_size=256):
            for text in texts:
                yield [float(len(text)), 1.0]

    queue, prompts = replies
    queue.append(json.dumps({
        "title": "Photosynthesis",
        "summary": "How plants make sugar.",
        "sections": [
            {"title": "Light", "content": "## Light\n\nChlorophyll absorbs light.", "concepts": ["light"]},
            {"title": "Calvin cycle", "content": "## Calvin\n\nCarbon is fixed.", "concepts": ["calvin"]},
        ],
        "knowledge_graph": {"concepts": [{"id": "light"}, {"id": "calvin"}]},
    }))
    embeddings.set_embedder(OneDimEmbedder())

    try:
        resp = client.post(
            "/upload",
            data={"file": (io.BytesIO(b"# Photosynthesis\n\nPlants use light."), "photo.md")},
            content_type="multipart/form-data",
        )
    finally:
        embeddings.set_embedder(None)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "sectioned"
    assert body["data"]["title"] == "Photosynthesis"
    assert [s["id"] for s in body["data"]["sections"]] == ["section-1", "section-2"]
    assert "Plants use light." in prompts[0]

    db = db_session()
    doc = db.query(database.Document).filter_by(id=body["id"]).one()
    assert doc.filename == "photo.md"
    assert doc.concepts == ["light", "calvin"]
    assert db.query(database.DocumentSection).filter_by(document_id=body["id"]).count() == 2
    statuses = {p.status for p in db.query(database.SectionProgress).filter_by(document_id=body["id"])}
    assert statuses == {"not_started"}
    assert db.query(database.ChunkEmbedding).filter_by(document_id=body["id"]).count() >= 2
    db.close()


@pytest.mark.parametrize(
    "name, data",
    [("slides.pptx", b"PK\x03\x04rest"), ("fake.pdf", b"not a pdf at all"), ("bin.txt", b"a\x00b")],
)
def test_upload_of_a_wrong_or_disguised_type_is_rejected(client, replies, name, data):
    resp = client.post(
        "/upload", data={"file": (io.BytesIO(data), name)}, content_type="multipart/form-data"
    )

    assert resp.status_code == 415
    assert "error" in resp.get_json()
    assert replies[1] == []  # nothing was sent to a model


def test_upload_over_the_size_limit_gets_a_json_413(client, monkeypatch):
    monkeypatch.setitem(main.app.config, "MAX_CONTENT_LENGTH", 1024)

    resp = client.post(
        "/upload",
        data={"file": (io.BytesIO(b"x" * 4096), "big.md")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 413
    assert "MB limit" in resp.get_json()["error"]


def test_cors_allows_only_the_configured_frontend(client):
    allowed = client.options(
        "/generate-quiz",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    refused = client.options(
        "/generate-quiz",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert allowed.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    assert "Access-Control-Allow-Origin" not in refused.headers


def test_health_lists_the_providers_with_a_key_without_calling_them(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "llm_providers": ["groq"]}
