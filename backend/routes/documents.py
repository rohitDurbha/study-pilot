"""Document and section routes.

These routes store a processed document with its knowledge graph, list and
rename documents, and read or update the progress of each section.
"""

import logging
import uuid

from flask import Blueprint, jsonify

import agent_engine
import database
import knowledge_graph
from database import Document, DocumentSection, SectionProgress
from routes.common import json_body

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/api/documents", methods=["POST"])
def create_document():
    """Store a processed document with its summary and knowledge graph."""
    data = json_body()
    try:
        doc_id = data.get("id", f"doc-{uuid.uuid4()}")
        filename = data.get("filename", "untitled")
        summary = data.get("summary", "")

        kg = None
        try:
            kg = knowledge_graph.extract_knowledge_graph(summary)
        except Exception as e:
            logging.warning(f"Knowledge graph extraction failed: {e}")

        db = database.SessionLocal()
        doc = Document(
            id=doc_id,
            filename=filename,
            summary=summary,
            concepts=kg.get("concepts", []) if kg else [],
            knowledge_graph=kg,
        )
        db.merge(doc)  # Upsert
        db.commit()
        db.close()

        return jsonify({
            "id": doc_id,
            "knowledge_graph": kg,
        })

    except Exception as e:
        logging.exception("Error creating document")
        return jsonify({"error": str(e)}), 500


@documents_bp.route("/api/documents/<doc_id>/graph", methods=["GET"])
def get_knowledge_graph(doc_id):
    """Get the knowledge graph for a document."""
    db = database.SessionLocal()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    db.close()

    if not doc:
        return jsonify({"error": "Document not found"}), 404

    return jsonify({
        "document_id": doc_id,
        "concepts": doc.concepts or [],
        "knowledge_graph": doc.knowledge_graph,
    })


@documents_bp.route("/api/documents", methods=["GET"])
def list_documents():
    """List all documents."""
    db = database.SessionLocal()
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    db.close()

    return jsonify({
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]
    })


@documents_bp.route("/api/documents/<doc_id>/rename", methods=["POST"])
def rename_document(doc_id):
    """Rename a document."""
    data = json_body()
    try:
        new_name = str(data.get("name") or "").strip()
        if not new_name:
            return jsonify({"error": "Name cannot be empty"}), 400

        db = database.SessionLocal()
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            db.close()
            return jsonify({"error": "Document not found"}), 404

        doc.filename = new_name
        db.commit()
        db.close()
        return jsonify({"ok": True, "name": new_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@documents_bp.route("/api/documents/latest", methods=["GET"])
def get_latest_document():
    """Get the most recent document with its summary."""
    db = database.SessionLocal()
    doc = db.query(Document).order_by(Document.created_at.desc()).first()
    db.close()

    if not doc:
        return jsonify({"found": False}), 200

    return jsonify({
        "found": True,
        "id": doc.id,
        "filename": doc.filename,
        "summary": doc.summary,
        "concepts": doc.concepts,
        "knowledge_graph": doc.knowledge_graph,
    })


@documents_bp.route("/api/sections/<document_id>", methods=["GET"])
def get_sections(document_id):
    """Get all sections with progress for a document."""
    db = database.SessionLocal()
    sections = db.query(DocumentSection).filter(
        DocumentSection.document_id == document_id
    ).order_by(DocumentSection.section_order).all()

    result = []
    for sec in sections:
        prog = db.query(SectionProgress).filter(
            SectionProgress.section_id == sec.id,
            SectionProgress.document_id == document_id,
        ).first()

        result.append({
            "id": sec.id,
            "title": sec.title,
            "content": sec.content,
            "concepts": sec.concepts,
            "prerequisites": sec.prerequisites,
            "order": sec.section_order,
            "estimated_read_min": sec.estimated_read_min,
            "status": prog.status if prog else "not_started",
            "quiz_score": prog.quiz_score if prog else None,
        })

    db.close()
    return jsonify({"sections": result})


@documents_bp.route("/api/sections/<document_id>/<section_id>/progress", methods=["POST"])
def update_progress(document_id, section_id):
    """Update the progress of a section."""
    data = json_body()
    try:
        status = data.get("status", "in_progress")
        quiz_score = data.get("quiz_score")

        agent_engine.update_section_progress(document_id, section_id, status, quiz_score)

        return jsonify({"ok": True})
    except Exception as e:
        logging.exception("Error updating progress")
        return jsonify({"error": str(e)}), 500
