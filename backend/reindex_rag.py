"""Rebuild the SQLite chunk vectors for documents uploaded before the switch.

Documents uploaded while the RAG pipeline still used ChromaDB have their
sections in the database but no rows in the chunk_embeddings table, so Deep
Search finds nothing for them. This script embeds those documents again with
the current fastembed model and stores the vectors in SQLite.

Run it from backend/ with the same virtual environment as the server.

    python3 reindex_rag.py              # documents that have no vectors yet
    python3 reindex_rag.py --all        # every document, e.g. after changing EMBEDDING_MODEL
    python3 reindex_rag.py <doc_id>...  # only the documents you name
    python3 reindex_rag.py --dry-run    # list what would be reindexed

The first run downloads the embedding model (about 80 MB). The old
backend/chroma_db folder is no longer read by anything and can be deleted
once this script has finished.
"""

import argparse
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

import database  # noqa: E402
import rag_pipeline  # noqa: E402


def _session():
    # Looked up on every call so tests can point database.SessionLocal at a
    # throwaway engine.
    return database.SessionLocal()


def load_sections(document_id):
    """Return the sections of a document in reading order, as plain dicts."""
    db = _session()
    try:
        rows = (
            db.query(database.DocumentSection)
            .filter(database.DocumentSection.document_id == document_id)
            .order_by(database.DocumentSection.section_order)
            .all()
        )
        return [{"id": r.id, "title": r.title or "", "content": r.content or ""} for r in rows]
    finally:
        db.close()


def find_documents(include_indexed=False):
    """Return (id, filename) for documents that need vectors, oldest first.

    Without include_indexed only documents that have no stored chunk vectors
    are returned, which is what a database from before the switch looks like.
    """
    db = _session()
    try:
        docs = db.query(database.Document).order_by(database.Document.created_at).all()
        indexed = {
            doc_id
            for (doc_id,) in db.query(database.ChunkEmbedding.document_id).distinct()
        }
        return [
            (d.id, d.filename)
            for d in docs
            if include_indexed or d.id not in indexed
        ]
    finally:
        db.close()


def reindex(document_ids, out=print):
    """Embed and store each document. Returns (indexed, failed) counts."""
    indexed = failed = 0
    for doc_id in document_ids:
        sections = load_sections(doc_id)
        if not sections:
            out(f"skipped  {doc_id}  (no sections stored)")
            continue
        try:
            chunks = rag_pipeline.embed_and_store(doc_id, sections)
        except Exception as exc:  # noqa: BLE001 - keep going with the others
            out(f"FAILED   {doc_id}  ({exc})")
            failed += 1
            continue
        out(f"indexed  {doc_id}  ({chunks} chunks from {len(sections)} sections)")
        indexed += 1
    return indexed, failed


def main(argv=None, out=print):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("document_ids", nargs="*", help="documents to reindex")
    parser.add_argument(
        "--all",
        action="store_true",
        help="reindex every document, including ones that already have vectors",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list the documents that would be reindexed and stop",
    )
    args = parser.parse_args(argv)

    if args.document_ids:
        targets = list(args.document_ids)
    else:
        targets = [doc_id for doc_id, _ in find_documents(include_indexed=args.all)]

    if not targets:
        out("Every document already has vectors. Pass --all to rebuild them anyway.")
        return 0

    if args.dry_run:
        for doc_id in targets:
            out(f"would index  {doc_id}")
        return 0

    indexed, failed = reindex(targets, out=out)
    out(f"{indexed} indexed, {failed} failed, {len(targets) - indexed - failed} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
