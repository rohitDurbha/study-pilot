"""Text embeddings for the RAG pipeline, backed by fastembed.

fastembed runs the same all-MiniLM-L6-v2 model that sentence-transformers
used, but through ONNX Runtime, so the backend no longer needs PyTorch and
fits in free hosting. The model is downloaded on first use and loaded once
per process.

Settings, all optional and read from the environment:

    EMBEDDING_MODEL       fastembed model name (default all-MiniLM-L6-v2)
    EMBEDDING_CACHE_DIR   folder for the downloaded model files
    EMBEDDING_BATCH_SIZE  texts embedded per batch (default 64)

Every vector returned here is scaled to unit length, so the cosine
similarity of two vectors is simply their dot product.
"""

import os
import threading

import numpy as np

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_BATCH_SIZE = 64

# Short names people tend to type, mapped to the names fastembed expects.
MODEL_ALIASES = {
    "all-MiniLM-L6-v2": DEFAULT_MODEL,
    "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
}

_embedder = None
_lock = threading.Lock()


def model_name() -> str:
    """Return the configured model name in the form fastembed expects."""
    name = os.getenv("EMBEDDING_MODEL", "").strip() or DEFAULT_MODEL
    return MODEL_ALIASES.get(name, name)


def batch_size() -> int:
    raw = os.getenv("EMBEDDING_BATCH_SIZE", "").strip()
    try:
        value = int(raw) if raw else DEFAULT_BATCH_SIZE
    except ValueError:
        value = DEFAULT_BATCH_SIZE
    return max(1, value)


def _load_fastembed():
    from fastembed import TextEmbedding  # imported lazily so tests never need it

    cache_dir = os.getenv("EMBEDDING_CACHE_DIR", "").strip() or None
    return TextEmbedding(model_name=model_name(), cache_dir=cache_dir)


def get_embedder():
    """Return the shared embedder, loading the model on first use."""
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                _embedder = _load_fastembed()
    return _embedder


def set_embedder(embedder):
    """Swap in another embedder (used by tests). Pass None to reset."""
    global _embedder
    _embedder = embedder


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def embed_texts(texts: list) -> np.ndarray:
    """Embed document chunks. Returns a float32 array of shape (len(texts), dim)."""
    texts = [t if isinstance(t, str) else str(t) for t in texts]
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    vectors = list(get_embedder().embed(texts, batch_size=batch_size()))
    matrix = np.asarray(vectors, dtype=np.float32)
    return _normalize(matrix)


def embed_query(text: str) -> np.ndarray:
    """Embed a single search query. Returns a float32 vector of shape (dim,)."""
    embedder = get_embedder()
    if hasattr(embedder, "query_embed"):
        vectors = list(embedder.query_embed(text))
    else:
        vectors = list(embedder.embed([text]))
    matrix = np.asarray(vectors, dtype=np.float32)
    return _normalize(matrix)[0]
