"""RAG Pipeline — chunk, embed, store, retrieve from ChromaDB."""
import os
import chromadb
from sentence_transformers import SentenceTransformer

# Module-level singletons (loaded once at server startup)
_embedding_model = None
_chroma_client = None

CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return _chroma_client


def _collection_name(document_id: str) -> str:
    """Sanitize document ID into a valid ChromaDB collection name."""
    name = f"doc_{document_id.replace('-', '_')}"
    # ChromaDB collection names: 3-63 chars, alphanumeric + underscores
    return name[:63]


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
    """Chunk all sections, embed, and store in ChromaDB. Returns chunk count."""
    model = get_embedding_model()
    client = get_chroma_client()
    col_name = _collection_name(document_id)

    # Delete existing collection if re-indexing
    try:
        client.delete_collection(col_name)
    except Exception:
        pass

    collection = client.create_collection(
        name=col_name, metadata={"hnsw:space": "cosine"}
    )

    all_chunks = []
    for section in sections:
        chunks = chunk_section(
            section_id=section["id"],
            section_title=section["title"],
            content=section["content"],
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        return 0

    # Batch embed and store
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts).tolist()
    ids = [f"{c['section_id']}_chunk_{c['chunk_index']}" for c in all_chunks]
    metadatas = [
        {
            "section_id": c["section_id"],
            "section_title": c["section_title"],
            "chunk_index": c["chunk_index"],
            "document_id": document_id,
        }
        for c in all_chunks
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    return len(all_chunks)


def retrieve_chunks(document_id: str, query: str, top_k: int = 5) -> list:
    """Embed query and retrieve top-k relevant chunks from ChromaDB."""
    model = get_embedding_model()
    client = get_chroma_client()
    col_name = _collection_name(document_id)

    try:
        collection = client.get_collection(col_name)
    except Exception:
        return []

    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
    )

    if not results["ids"] or not results["ids"][0]:
        return []

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append(
            {
                "text": results["documents"][0][i],
                "section_id": results["metadatas"][0][i]["section_id"],
                "section_title": results["metadatas"][0][i]["section_title"],
                "chunk_index": results["metadatas"][0][i]["chunk_index"],
                "score": round(1 - results["distances"][0][i], 3),
            }
        )
    return chunks


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
    """Remove a document's vector collection."""
    client = get_chroma_client()
    col_name = _collection_name(document_id)
    try:
        client.delete_collection(col_name)
    except Exception:
        pass
