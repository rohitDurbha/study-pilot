"""Study session routes.

These routes start and end a study session, record focus scores and
distractions while it runs, and report the analytics worked out at the end.
"""

import logging
import uuid
from datetime import datetime

from flask import Blueprint, jsonify

import database
from database import ContentTransition, DistractionEvent, FocusEvent, StudySession
from routes.common import json_body

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/api/sessions/latest", methods=["GET"])
def get_latest_session():
    """Get the most recent active session."""
    db = database.SessionLocal()
    session = db.query(StudySession).order_by(StudySession.started_at.desc()).first()
    db.close()

    if not session:
        return jsonify({"found": False}), 200

    return jsonify({
        "found": True,
        "id": session.id,
        "document_id": session.document_id,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "distraction_count": session.distraction_count or 0,
    })


@sessions_bp.route("/api/sessions", methods=["POST"])
def create_session():
    """Start a new study session."""
    data = json_body()
    try:
        session_id = f"session-{uuid.uuid4()}"
        document_id = data.get("document_id")

        db = database.SessionLocal()
        session = StudySession(
            id=session_id,
            document_id=document_id,
            started_at=datetime.utcnow(),
        )
        db.add(session)
        db.commit()
        db.close()

        return jsonify({"id": session_id})

    except Exception as e:
        logging.exception("Error creating session")
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/api/sessions/<session_id>/focus", methods=["POST"])
def record_focus_events(session_id):
    """Record a batch of focus events."""
    data = json_body()
    events = data.get("events", [])
    if not isinstance(events, list):
        return jsonify({"error": "events must be a list"}), 400
    try:
        db = database.SessionLocal()
        for event in events:
            if not isinstance(event, dict):
                continue
            fe = FocusEvent(
                session_id=session_id,
                focus_score=event.get("score", 0),
                content_type=event.get("contentType", "text"),
                timestamp=datetime.utcnow(),
            )
            db.add(fe)
        db.commit()
        db.close()

        return jsonify({"recorded": len(events)})

    except Exception as e:
        logging.exception("Error recording focus events")
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/api/sessions/<session_id>/distraction", methods=["POST"])
def record_distraction(session_id):
    """Record a distraction event."""
    data = json_body()
    try:
        db = database.SessionLocal()
        de = DistractionEvent(
            session_id=session_id,
            started_at=datetime.utcnow(),
            duration_sec=data.get("duration_sec", 0),
        )
        db.add(de)

        session = db.query(StudySession).filter(StudySession.id == session_id).first()
        if session:
            session.distraction_count = (session.distraction_count or 0) + 1
        db.commit()
        db.close()

        return jsonify({"ok": True})

    except Exception as e:
        logging.exception("Error recording distraction")
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/api/sessions/<session_id>/end", methods=["POST"])
def end_session(session_id):
    """End a study session and generate analytics."""
    try:
        db = database.SessionLocal()
        session = db.query(StudySession).filter(StudySession.id == session_id).first()
        if not session:
            db.close()
            return jsonify({"error": "Session not found"}), 404

        session.ended_at = datetime.utcnow()

        focus_events = db.query(FocusEvent).filter(FocusEvent.session_id == session_id).all()
        distractions = db.query(DistractionEvent).filter(DistractionEvent.session_id == session_id).all()
        transitions = db.query(ContentTransition).filter(ContentTransition.session_id == session_id).all()

        scores = [fe.focus_score for fe in focus_events if fe.focus_score is not None]
        avg_focus = sum(scores) / len(scores) if scores else 0

        duration_sec = (session.ended_at - session.started_at).total_seconds() if session.started_at else 0
        total_distraction_sec = sum(d.duration_sec or 0 for d in distractions)
        focused_time_sec = duration_sec - total_distraction_sec

        focus_by_type = {}
        for fe in focus_events:
            if fe.focus_score is None:
                continue
            ct = fe.content_type or "text"
            if ct not in focus_by_type:
                focus_by_type[ct] = {"scores": [], "count": 0}
            focus_by_type[ct]["scores"].append(fe.focus_score)
            focus_by_type[ct]["count"] += 1

        content_effectiveness = {}
        for ct, data in focus_by_type.items():
            content_effectiveness[ct] = {
                "avg_focus": round(sum(data["scores"]) / len(data["scores"]), 1),
                "time_pct": round(data["count"] / len(focus_events) * 100, 1) if focus_events else 0,
            }

        session_summary = {
            "total_duration_min": round(duration_sec / 60, 1),
            "focused_time_min": round(max(focused_time_sec, 0) / 60, 1),
            "focus_percentage": round(max(focused_time_sec, 0) / duration_sec * 100, 1) if duration_sec > 0 else 0,
            "avg_focus_score": round(avg_focus, 1),
            "distraction_count": len(distractions),
            "avg_distraction_sec": round(total_distraction_sec / len(distractions), 1) if distractions else 0,
            "content_switches": len(transitions),
            "content_effectiveness": content_effectiveness,
        }

        session.avg_focus_score = avg_focus
        session.total_focus_time_sec = max(focused_time_sec, 0)
        session.content_switches = len(transitions)
        session.session_summary = session_summary

        db.commit()
        db.close()

        return jsonify(session_summary)

    except Exception as e:
        logging.exception("Error ending session")
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/api/sessions/<session_id>/analytics", methods=["GET"])
def get_session_analytics(session_id):
    """Get analytics for a session."""
    db = database.SessionLocal()
    session = db.query(StudySession).filter(StudySession.id == session_id).first()
    db.close()

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(session.session_summary or {"status": "session still active"})
