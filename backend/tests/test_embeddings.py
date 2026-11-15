"""Tests for embeddings.py. A fake embedder stands in for fastembed, so no model is downloaded."""

import sys
import types

import numpy as np
import pytest

import embeddings


class FakeEmbedder:
    """Maps each text to a small vector built from a few keyword counts."""

    KEYWORDS = ("plant", "energy", "war", "king")

    def __init__(self):
        self.embed_calls = []
        self.query_calls = []

    def _vector(self, text):
        lowered = text.lower()
        return np.array([lowered.count(k) for k in self.KEYWORDS], dtype=np.float64)

    def embed(self, texts, batch_size=256):
        self.embed_calls.append((list(texts), batch_size))
        for text in texts:
            yield self._vector(text)

    def query_embed(self, query):
        self.query_calls.append(query)
        yield self._vector(query)


@pytest.fixture
def fake(monkeypatch):
    for var in ("EMBEDDING_MODEL", "EMBEDDING_CACHE_DIR", "EMBEDDING_BATCH_SIZE"):
        monkeypatch.delenv(var, raising=False)
    embedder = FakeEmbedder()
    embeddings.set_embedder(embedder)
    yield embedder
    embeddings.set_embedder(None)


def test_default_model_is_minilm(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    assert embeddings.model_name() == "sentence-transformers/all-MiniLM-L6-v2"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2"),
        ("bge-small-en-v1.5", "BAAI/bge-small-en-v1.5"),
        ("intfloat/multilingual-e5-small", "intfloat/multilingual-e5-small"),
        ("   ", "sentence-transformers/all-MiniLM-L6-v2"),
    ],
)
def test_model_name_reads_environment_and_expands_aliases(monkeypatch, value, expected):
    monkeypatch.setenv("EMBEDDING_MODEL", value)
    assert embeddings.model_name() == expected


@pytest.mark.parametrize("raw, expected", [("", 64), ("16", 16), ("0", 1), ("lots", 64)])
def test_batch_size_falls_back_on_bad_values(monkeypatch, raw, expected):
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", raw)
    assert embeddings.batch_size() == expected


def test_embed_texts_returns_unit_float32_rows(fake, monkeypatch):
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "8")
    matrix = embeddings.embed_texts(["plant energy plant", "war king"])

    assert matrix.shape == (2, 4)
    assert matrix.dtype == np.float32
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0)
    assert fake.embed_calls == [(["plant energy plant", "war king"], 8)]


def test_embed_texts_keeps_zero_vectors_finite(fake):
    matrix = embeddings.embed_texts(["nothing relevant here"])
    assert np.all(np.isfinite(matrix))
    assert np.allclose(matrix, 0.0)


def test_embed_texts_handles_empty_input_without_loading_model(monkeypatch):
    embeddings.set_embedder(None)

    def explode():
        raise AssertionError("model should not load for empty input")

    monkeypatch.setattr(embeddings, "_load_fastembed", explode)
    assert embeddings.embed_texts([]).shape == (0, 0)


def test_embed_query_uses_query_embed_and_ranks_by_dot_product(fake):
    docs = embeddings.embed_texts(["plants store energy", "the king went to war"])
    query = embeddings.embed_query("where do plants get energy")

    assert query.shape == (4,)
    assert fake.query_calls == ["where do plants get energy"]
    scores = docs @ query
    assert scores[0] > scores[1]
    assert scores[0] == pytest.approx(1.0)


def test_embed_query_falls_back_to_embed_when_query_embed_is_missing():
    class PlainEmbedder:
        def embed(self, texts, batch_size=256):
            for _ in texts:
                yield [3.0, 4.0]

    embeddings.set_embedder(PlainEmbedder())
    try:
        assert np.allclose(embeddings.embed_query("anything"), [0.6, 0.8])
    finally:
        embeddings.set_embedder(None)


def test_get_embedder_loads_fastembed_once_with_configured_settings(monkeypatch):
    created = []

    class FakeTextEmbedding:
        def __init__(self, model_name, cache_dir=None):
            created.append((model_name, cache_dir))

    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=FakeTextEmbedding))
    monkeypatch.setenv("EMBEDDING_MODEL", "bge-small-en-v1.5")
    monkeypatch.setenv("EMBEDDING_CACHE_DIR", "/tmp/models")
    embeddings.set_embedder(None)
    try:
        first = embeddings.get_embedder()
        second = embeddings.get_embedder()
    finally:
        embeddings.set_embedder(None)

    assert first is second
    assert created == [("BAAI/bge-small-en-v1.5", "/tmp/models")]
