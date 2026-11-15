"""Tests for reindex_rag.py against an in-memory database and a fake embedder."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
import embeddings
import rag_pipeline
import reindex_rag


class CountingEmbedder:
    def embed(self, texts, batch_size=256):
        for text in texts:
            yield [len(text), 1.0]

    def query_embed(self, query):
        yield [len(query), 1.0]


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    embeddings.set_embedder(CountingEmbedder())
    yield database
    embeddings.set_embedder(None)
    engine.dispose()


def add_document(doc_id, sections, age_days=0):
    session = database.SessionLocal()
    try:
        session.add(
            database.Document(
                id=doc_id,
                filename=f"{doc_id}.pdf",
                created_at=datetime(2026, 1, 1) + timedelta(days=age_days),
            )
        )
        for order, (title, content) in enumerate(sections):
            session.add(
                database.DocumentSection(
                    id=f"{doc_id}-s{order}",
                    document_id=doc_id,
                    title=title,
                    content=content,
                    section_order=order,
                )
            )
        session.commit()
    finally:
        session.close()


def chunk_counts():
    session = database.SessionLocal()
    try:
        counts = {}
        for (doc_id,) in session.query(database.ChunkEmbedding.document_id):
            counts[doc_id] = counts.get(doc_id, 0) + 1
        return counts
    finally:
        session.close()


def run(argv):
    lines = []
    code = reindex_rag.main(argv, out=lines.append)
    return code, lines


def test_default_run_indexes_only_documents_without_vectors(db):
    add_document("old", [("Intro", "Photosynthesis basics."), ("Light", "Chlorophyll.")])
    add_document("new", [("Intro", "Already indexed.")], age_days=1)
    rag_pipeline.embed_and_store("new", reindex_rag.load_sections("new"))

    code, lines = run([])

    assert code == 0
    assert chunk_counts() == {"old": 2, "new": 1}
    assert lines[0] == "indexed  old  (2 chunks from 2 sections)"
    assert lines[-1] == "1 indexed, 0 failed, 0 skipped"


def test_all_flag_rebuilds_every_document_oldest_first(db, monkeypatch):
    add_document("b", [("One", "Second upload.")], age_days=2)
    add_document("a", [("One", "First upload.")], age_days=1)
    rag_pipeline.embed_and_store("a", reindex_rag.load_sections("a"))

    seen = []
    real = rag_pipeline.embed_and_store
    monkeypatch.setattr(
        rag_pipeline, "embed_and_store", lambda d, s: seen.append(d) or real(d, s)
    )

    code, _ = run(["--all"])

    assert code == 0
    assert seen == ["a", "b"]
    assert chunk_counts() == {"a": 1, "b": 1}


def test_named_documents_are_reindexed_even_when_they_have_vectors(db):
    add_document("doc", [("One", "Some text.")])
    rag_pipeline.embed_and_store("doc", reindex_rag.load_sections("doc"))

    code, lines = run(["doc"])

    assert code == 0
    assert chunk_counts() == {"doc": 1}
    assert lines[0].startswith("indexed  doc")


def test_dry_run_lists_targets_without_writing(db):
    add_document("old", [("Intro", "Text.")])

    code, lines = run(["--dry-run"])

    assert code == 0
    assert lines == ["would index  old"]
    assert chunk_counts() == {}


def test_nothing_to_do_says_so(db):
    add_document("doc", [("One", "Text.")])
    rag_pipeline.embed_and_store("doc", reindex_rag.load_sections("doc"))

    code, lines = run([])

    assert code == 0
    assert "Pass --all" in lines[0]


def test_unknown_document_is_skipped(db):
    code, lines = run(["missing"])

    assert code == 0
    assert lines == [
        "skipped  missing  (no sections stored)",
        "0 indexed, 0 failed, 1 skipped",
    ]


def test_a_failure_is_reported_and_the_rest_still_run(db, monkeypatch):
    add_document("bad", [("One", "Breaks.")])
    add_document("good", [("One", "Works.")], age_days=1)

    real = rag_pipeline.embed_and_store

    def flaky(doc_id, sections):
        if doc_id == "bad":
            raise RuntimeError("model download failed")
        return real(doc_id, sections)

    monkeypatch.setattr(rag_pipeline, "embed_and_store", flaky)

    code, lines = run([])

    assert code == 1
    assert lines[0] == "FAILED   bad  (model download failed)"
    assert chunk_counts() == {"good": 1}
    assert lines[-1] == "1 indexed, 1 failed, 0 skipped"
