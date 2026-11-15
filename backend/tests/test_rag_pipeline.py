"""Tests that rag_pipeline.py embeds through embeddings.py.

ChromaDB stays in place until roadmap step 3b, so a small in-memory fake
replaces it here. The module is loaded under a private name so the fake never
leaks into other test files.
"""

import importlib.util
import os
import sys
import types

import numpy as np
import pytest

import embeddings

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeCollection:
    def __init__(self):
        self.rows = []

    def add(self, ids, embeddings, documents, metadatas):
        for row in zip(ids, embeddings, documents, metadatas):
            self.rows.append(row)

    def count(self):
        return len(self.rows)

    def query(self, query_embeddings, n_results):
        query = np.asarray(query_embeddings[0])
        scored = sorted(
            ((float(np.dot(query, vec)), doc, meta) for _, vec, doc, meta in self.rows),
            key=lambda item: item[0],
            reverse=True,
        )[:n_results]
        return {
            "ids": [[meta["section_id"] for _, _, meta in scored]],
            "documents": [[doc for _, doc, _ in scored]],
            "metadatas": [[meta for _, _, meta in scored]],
            "distances": [[1 - score for score, _, _ in scored]],
        }


class FakeClient:
    def __init__(self, path=None):
        self.collections = {}

    def create_collection(self, name, metadata=None):
        self.collections[name] = FakeCollection()
        return self.collections[name]

    def get_collection(self, name):
        return self.collections[name]

    def delete_collection(self, name):
        self.collections.pop(name, None)


class KeywordEmbedder:
    KEYWORDS = ("cell", "energy", "treaty", "war")

    def embed(self, texts, batch_size=256):
        for text in texts:
            yield [text.lower().count(k) for k in self.KEYWORDS]

    def query_embed(self, query):
        yield [query.lower().count(k) for k in self.KEYWORDS]


@pytest.fixture
def rag(monkeypatch):
    monkeypatch.setitem(sys.modules, "chromadb", types.SimpleNamespace(PersistentClient=FakeClient))
    spec = importlib.util.spec_from_file_location(
        "rag_pipeline_under_test", os.path.join(BACKEND_DIR, "rag_pipeline.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    embeddings.set_embedder(KeywordEmbedder())
    yield module
    embeddings.set_embedder(None)


SECTIONS = [
    {"id": "s1", "title": "Cells", "content": "The cell makes energy in the mitochondria."},
    {"id": "s2", "title": "History", "content": "The treaty ended the war in 1648."},
]


def test_embed_and_store_saves_unit_vectors_from_embeddings_module(rag):
    assert rag.embed_and_store("doc-1", SECTIONS) == 2

    collection = rag.get_chroma_client().get_collection("doc_doc_1")
    vectors = np.array([vec for _, vec, _, _ in collection.rows])
    assert vectors.shape == (2, 4)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)


def test_retrieve_chunks_ranks_by_query_embedding(rag):
    rag.embed_and_store("doc-1", SECTIONS)

    chunks = rag.retrieve_chunks("doc-1", "which treaty ended the war", top_k=2)

    assert [c["section_id"] for c in chunks] == ["s2", "s1"]
    assert chunks[0]["score"] == pytest.approx(1.0)


def test_retrieve_chunks_returns_empty_for_unknown_document(rag):
    assert rag.retrieve_chunks("missing", "anything") == []
