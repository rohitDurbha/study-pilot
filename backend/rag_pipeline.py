"""RAG pipeline that chunks, embeds, stores and retrieves document text.

Chunk vectors live in the chunk_embeddings table of the app's SQLite
database (see database.py) rather than in ChromaDB, so the backend needs no
separate vector store. Vectors come from embeddings.py already scaled to unit
length, which makes cosine similarity a plain dot product that numpy computes
for all of a document's chunks at once. A study document holds at most a few
hundred chunks, so a full scan per query stays fast.
"""
import numpy as np

import database
import embeddings


def _session():
    # Looked up on every call so tests can point database.SessionLocal at a
    # throwaway engine.
    return database.SessionLocal()


def _to_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def _from_blob(blob: bytes, dim: int) -> np.ndarray:
    vector = np.frombuffer(blob, dtype=np.float32)
    if vector.shape[0] != dim:
        raise ValueError("stored vector length does not match its dimension")
    return vector


def chunk_section(
    section_id: str,
    section_title: str,
    content: str,
    max_tokens: int = 300,
    overlap: int = 50,
) -> list:
    """Split section content into chunks at paragraph boundaries."""
    if not content or not content.strip():
        return []

    paragraphs = content.split("\n\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_tokens = len(para.split())

        if current_length + para_tokens > max_tokens and current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                {
                    "text": chunk_text,
                    "section_id": section_id,
                    "section_title": section_title,
                    "chunk_index": len(chunks),
                }
            )
            # Keep overlap from end of current chunk
            overlap_words = chunk_text.split()[-overlap:]
            current_chunk = [" ".join(overlap_words), para]
            current_length = overlap + para_tokens
        else:
            current_chunk.append(para)
            current_length += para_tokens

    if current_chunk:
        chunks.append(
            {
                "text": "\n\n".join(current_chunk),
                "section_id": section_id,
                "section_title": section_title,
                "chunk_index": len(chunks),
            }
        )

    return chunks


def embed_and_store(document_id: str, sections: list) -> int:
    """Chunk all sections, embed them and store the vectors. Returns chunk count.

    Any chunks already stored for the document are replaced, so calling this
    again re-indexes the document.
    """
    all_chunks = []
    for section in sections:
        all_chunks.extend(
            chunk_section(
                section_id=section["id"],
                section_title=section["title"],
                content=section["content"],
            )
        )

    vectors = embeddings.embed_texts([c["text"] for c in all_chunks]) if all_chunks else None

    db = _session()
    try:
        db.query(database.ChunkEmbedding).filter_by(document_id=document_id).delete()
        for chunk, vector in zip(all_chunks, vectors if vectors is not None else []):
            db.add(
                database.ChunkEmbedding(
                    document_id=document_id,
                    section_id=chunk["section_id"],
                    section_title=chunk["section_title"],
                    chunk_index=chunk["chunk_index"],
                    text=chunk["text"],
                    dim=int(vector.shape[0]),
                    vector=_to_blob(vector),
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return len(all_chunks)


def retrieve_chunks(document_id: str, query: str, top_k: int = 5) -> list:
    """Embed the query and return the top_k most similar chunks of a document."""
    if top_k <= 0:
        return []

    db = _session()
    try:
        rows = (
            db.query(database.ChunkEmbedding)
            .filter_by(document_id=document_id)
            .order_by(database.ChunkEmbedding.id)
            .all()
        )
    finally:
        db.close()
    if not rows:
        return []

    query_vector = embeddings.embed_query(query)
    dim = query_vector.shape[0]
    # Chunks embedded with a different model cannot be compared with this
    # query. They are skipped until the document is re-indexed.
    rows = [r for r in rows if r.dim == dim]
    if not rows:
        return []

    matrix = np.vstack([_from_blob(r.vector, r.dim) for r in rows])
    scores = matrix @ query_vector
    order = np.argsort(-scores, kind="stable")[:top_k]

    return [
        {
            "text": rows[i].text,
            "section_id": rows[i].section_id,
            "section_title": rows[i].section_title,
            "chunk_index": rows[i].chunk_index,
            "score": round(float(scores[i]), 3),
        }
        for i in order
    ]


def build_rag_prompt(query: str, chunks: list) -> str:
    """Format retrieved chunks as numbered sources for the LLM."""
    context = "RETRIEVED CONTEXT (cite using [1], [2], etc.):\n\n"
    for i, chunk in enumerate(chunks):
        context += f'[{i + 1}] (Section: "{chunk["section_title"]}")\n'
        context += f"{chunk['text']}\n\n"
    context += "Answer the student's question using ONLY the context above. "
    context += "Cite your sources using [1], [2], etc.\n"
    return context


def delete_collection(document_id: str):
    """Remove every stored chunk vector for a document."""
    db = _session()
    try:
        db.query(database.ChunkEmbedding).filter_by(document_id=document_id).delete()
        db.commit()
    finally:
        db.close()
