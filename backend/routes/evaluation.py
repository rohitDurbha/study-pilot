"""RAG evaluation and reindexing routes.

The evaluation routes compare RAG answers with full context answers for a
document. The reindex route rebuilds the stored vectors for one document.
"""

import logging

from flask import Blueprint, jsonify

import database
from database import DocumentSection, EvalTestCase

evaluation_bp = Blueprint("evaluation", __name__)


@evaluation_bp.route("/api/eval/generate-tests/<document_id>", methods=["POST"])
def eval_generate_tests(document_id):
    """Generate test cases for a document."""
    try:
        import eval_harness

        cases = eval_harness.generate_test_set(document_id)
        return jsonify({"count": len(cases), "test_cases": cases})
    except Exception as e:
        logging.exception("Error generating test cases")
        return jsonify({"error": str(e)}), 500


@evaluation_bp.route("/api/eval/run/<document_id>", methods=["POST"])
def eval_run(document_id):
    """Run full RAG vs Full-Context evaluation."""
    try:
        import eval_harness

        db = database.SessionLocal()
        count = db.query(EvalTestCase).filter(EvalTestCase.document_id == document_id).count()
        db.close()
        if count == 0:
            eval_harness.generate_test_set(document_id)

        return jsonify(eval_harness.run_evaluation(document_id))
    except Exception as e:
        logging.exception("Error running evaluation")
        return jsonify({"error": str(e)}), 500


@evaluation_bp.route("/api/eval/runs/<document_id>", methods=["GET"])
def eval_list_runs(document_id):
    """List all eval runs for a document."""
    import eval_harness

    return jsonify({"runs": eval_harness.get_eval_runs(document_id)})


@evaluation_bp.route("/api/eval/detail/<int:run_id>", methods=["GET"])
def eval_run_detail(run_id):
    """Get detailed results for a specific eval run."""
    import eval_harness

    return jsonify(eval_harness.get_eval_run_detail(run_id))


@evaluation_bp.route("/api/rag/reindex/<document_id>", methods=["POST"])
def rag_reindex(document_id):
    """Re-index an existing document for RAG (for docs uploaded before RAG was added)."""
    try:
        import rag_pipeline

        db = database.SessionLocal()
        sections = db.query(DocumentSection).filter(
            DocumentSection.document_id == document_id
        ).order_by(DocumentSection.section_order).all()

        sections_data = [
            {"id": s.id, "title": s.title, "content": s.content}
            for s in sections
        ]
        db.close()

        if not sections_data:
            return jsonify({"error": "No sections found"}), 404

        chunk_count = rag_pipeline.embed_and_store(document_id, sections_data)
        return jsonify({"chunks_indexed": chunk_count, "sections": len(sections_data)})
    except Exception as e:
        logging.exception("Error re-indexing")
        return jsonify({"error": str(e)}), 500
