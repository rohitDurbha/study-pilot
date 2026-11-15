"""Tests for the SQLite vector store in rag_pipeline.py.

Each test points database.SessionLocal at a fresh in-memory database and swaps
in a keyword embedder, so no model is downloaded and the real studybuddy.db
is never touched.
"""

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
import embeddings
import rag_pipeline


class KeywordEmbedder:
    KEYWORDS = ("cell", "energy", "treaty", "war")

    def embed(self, texts, batch_size=256):
        for text in texts:
            yield [text.lower().count(k) for k in self.KEYWORDS]

    def query_embed(self, query):
        yield [query.lower().count(k) for k in self.KEYWORDS]


@pytest.fixture
def rag(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    embeddings.set_embedder(KeywordEmbedder())
    yield rag_pipeline
    embeddings.set_embedder(None)
    engine.dispose()


def stored_rows(document_id):
    db = database.SessionLocal()
    try:
        return (
            db.query(database.ChunkEmbedding)
            .filter_by(document_id=document_id)
            .order_by(database.ChunkEmbedding.id)
            .all()
        )
    finally:
        db.close()


SECTIONS = [
    {"id": "s1", "title": "Cells", "content": "The cell makes energy in the mitochondria."},
    {"id": "s2", "title": "History", "content": "The treaty ended the war in 1648."},
]


def test_embed_and_store_saves_unit_vectors_in_sqlite(rag):
    assert rag.embed_and_store("doc-1", SECTIONS) == 2

    rows = stored_rows("doc-1")
    assert [r.section_id for r in rows] == ["s1", "s2"]
    assert [r.section_title for r in rows] == ["Cells", "History"]
    assert all(r.dim == 4 for r in rows)
    vectors = np.vstack([np.frombuffer(r.vector, dtype=np.float32) for r in rows])
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)


def test_embed_and_store_replaces_previous_chunks(rag):
    rag.embed_and_store("doc-1", SECTIONS)
    assert rag.embed_and_store("doc-1", SECTIONS[:1]) == 1

    assert [r.section_id for r in stored_rows("doc-1")] == ["s1"]


def test_embed_and_store_with_no_text_clears_the_document(rag):
    rag.embed_and_store("doc-1", SECTIONS)
    empty = [{"id": "s1", "title": "Blank", "content": "   "}]

    assert rag.embed_and_store("doc-1", empty) == 0
    assert stored_rows("doc-1") == []


def test_retrieve_chunks_ranks_by_cosine_similarity(rag):
    rag.embed_and_store("doc-1", SECTIONS)

    chunks = rag.retrieve_chunks("doc-1", "which treaty ended the war", top_k=2)

    assert [c["section_id"] for c in chunks] == ["s2", "s1"]
    assert chunks[0]["score"] == pytest.approx(1.0)
    assert chunks[1]["score"] == pytest.approx(0.0)
    assert set(chunks[0]) == {"text", "section_id", "section_title", "chunk_index", "score"}
    assert chunks[0]["text"] == "The treaty ended the war in 1648."


def test_retrieve_chunks_respects_top_k(rag):
    rag.embed_and_store("doc-1", SECTIONS)

    assert len(rag.retrieve_chunks("doc-1", "cell energy", top_k=1)) == 1
    assert len(rag.retrieve_chunks("doc-1", "cell energy", top_k=10)) == 2
    assert rag.retrieve_chunks("doc-1", "cell energy", top_k=0) == []


def test_retrieve_chunks_only_searches_the_requested_document(rag):
    rag.embed_and_store("doc-1", SECTIONS[:1])
    rag.embed_and_store("doc-2", SECTIONS[1:])

    chunks = rag.retrieve_chunks("doc-1", "treaty war", top_k=5)

    assert [c["section_id"] for c in chunks] == ["s1"]


def test_retrieve_chunks_returns_empty_for_unknown_document(rag):
    assert rag.retrieve_chunks("missing", "anything") == []


def test_retrieve_chunks_skips_vectors_from_another_model(rag):
    db = database.SessionLocal()
    db.add(
        database.ChunkEmbedding(
            document_id="doc-1",
            section_id="old",
            section_title="Old",
            chunk_index=0,
            text="embedded by a bigger model",
            dim=8,
            vector=np.ones(8, dtype=np.float32).tobytes(),
        )
    )
    db.commit()
    db.close()

    assert rag.retrieve_chunks("doc-1", "cell") == []


def test_delete_collection_removes_only_that_document(rag):
    rag.embed_and_store("doc-1", SECTIONS)
    rag.embed_and_store("doc-2", SECTIONS)

    rag.delete_collection("doc-1")

    assert stored_rows("doc-1") == []
    assert len(stored_rows("doc-2")) == 2
    rag.delete_collection("never-indexed")
