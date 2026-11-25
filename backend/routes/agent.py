"""Study agent routes.

Chat with the agent (full context or RAG), load the chat history of a session,
ask for a recap after a distraction, and ask the agent what to do next at the
moments the frontend reports (welcome, focus drop, section done, quiz result
and return from a distraction).
"""

import logging

from flask import Blueprint, jsonify

import agent_engine
import database
import study_agent
from database import ChatMessage, StudySession
from routes.common import json_body

agent_bp = Blueprint("agent", __name__)


@agent_bp.route("/api/agent/chat", methods=["POST"])
def agent_chat():
    """Chat with the study agent. Supports both full-context and RAG pipelines."""
    data = json_body()
    user_message = data.get("message", "")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    context = data.get("context") or {}
    if not isinstance(context, dict):
        return jsonify({"error": "context must be a JSON object"}), 400

    try:
        session_id = data.get("sessionId")
        pipeline = data.get("pipeline", "full_context")  # "rag" or "full_context"

        conversation_history = []
        document_id = None
        if session_id:
            db = database.SessionLocal()
            msgs = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at).all()
            conversation_history = [{"role": m.role, "content": m.content} for m in msgs]

            session = db.query(StudySession).filter(StudySession.id == session_id).first()
            if session:
                document_id = session.document_id

            db.add(ChatMessage(session_id=session_id, role="user", content=user_message))
            db.commit()
            db.close()

        sources = []

        if pipeline == "rag" and document_id:
            result = study_agent.chat_with_agent_rag(
                user_message=user_message,
                conversation_history=conversation_history,
                document_id=document_id,
                document_title=context.get("documentTitle", ""),
                focus_score=context.get("focusScore", 75),
                current_content_type=context.get("contentType", "text"),
                distraction_count=context.get("distractionCount", 0),
                session_duration_min=context.get("sessionDurationMin", 0),
                knowledge_graph=context.get("knowledgeGraph"),
                quiz_performance=context.get("quizPerformance"),
            )
            response_text = result["response"]
            sources = result["sources"]
        else:
            response_text = study_agent.chat_with_agent(
                user_message=user_message,
                conversation_history=conversation_history,
                document_title=context.get("documentTitle", ""),
                summary_text=context.get("summaryText", ""),
                focus_score=context.get("focusScore", 75),
                current_content_type=context.get("contentType", "text"),
                distraction_count=context.get("distractionCount", 0),
                session_duration_min=context.get("sessionDurationMin", 0),
                knowledge_graph=context.get("knowledgeGraph"),
                quiz_performance=context.get("quizPerformance"),
            )

        if session_id:
            db = database.SessionLocal()
            db.add(ChatMessage(session_id=session_id, role="assistant", content=response_text))
            db.commit()
            db.close()

        return jsonify({
            "response": response_text,
            "sources": sources,
            "pipeline": pipeline,
        })

    except Exception as e:
        logging.exception("Error in agent chat")
        return jsonify({"error": str(e)}), 500


@agent_bp.route("/api/agent/history/<session_id>", methods=["GET"])
def get_chat_history(session_id):
    """Load chat history for a session."""
    db = database.SessionLocal()
    msgs = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).all()
    db.close()

    return jsonify({
        "messages": [{"role": m.role, "content": m.content} for m in msgs]
    })


@agent_bp.route("/api/agent/recap", methods=["POST"])
def agent_recap():
    """Generate a distraction recovery recap."""
    data = json_body()
    try:
        recap = study_agent.generate_distraction_recap(
            document_title=data.get("documentTitle", ""),
            summary_text=data.get("summaryText", ""),
            last_content_type=data.get("contentType", "text"),
            last_section_context=data.get("lastSection", ""),
            absence_duration_sec=data.get("absenceDurationSec", 0),
        )

        return jsonify({"recap": recap})

    except Exception as e:
        logging.exception("Error generating recap")
        return jsonify({"error": str(e)}), 500


@agent_bp.route("/api/agent/decide/welcome", methods=["POST"])
def agent_decide_welcome():
    """Get the agent's welcome/resume message for a document."""
    data = json_body()
    document_id = data.get("document_id")
    if not document_id:
        return jsonify({"error": "No document_id"}), 400
    try:
        action = agent_engine.decide_welcome(document_id)
        return jsonify(action.to_dict())
    except Exception as e:
        logging.exception("Error in agent welcome")
        return jsonify({"error": str(e)}), 500


@agent_bp.route("/api/agent/decide/focus-drop", methods=["POST"])
def agent_decide_focus_drop():
    """Get the agent's suggestion when focus drops."""
    data = json_body()
    try:
        action = agent_engine.decide_focus_drop(
            data.get("document_id", ""),
            data.get("section_id", ""),
            data.get("content_type", "text"),
        )
        return jsonify(action.to_dict())
    except Exception as e:
        logging.exception("Error in agent focus drop")
        return jsonify({"error": str(e)}), 500


@agent_bp.route("/api/agent/decide/section-complete", methods=["POST"])
def agent_decide_section_complete():
    """Get the agent's suggestion after a section is read."""
    data = json_body()
    try:
        action = agent_engine.decide_section_complete(data.get("document_id", ""), data.get("section_id", ""))
        return jsonify(action.to_dict())
    except Exception as e:
        logging.exception("Error in agent section complete")
        return jsonify({"error": str(e)}), 500


@agent_bp.route("/api/agent/decide/quiz-result", methods=["POST"])
def agent_decide_quiz_result():
    """Get the agent's suggestion after a quiz."""
    data = json_body()
    try:
        action = agent_engine.decide_quiz_result(
            data.get("document_id", ""),
            data.get("section_id", ""),
            data.get("score", 0),
            data.get("total", 0),
            data.get("weak_concepts", []),
        )
        return jsonify(action.to_dict())
    except Exception as e:
        logging.exception("Error in agent quiz result")
        return jsonify({"error": str(e)}), 500


@agent_bp.route("/api/agent/decide/distraction-return", methods=["POST"])
def agent_decide_distraction_return():
    """Get the agent's message when student returns from distraction."""
    data = json_body()
    try:
        action = agent_engine.decide_distraction_return(
            data.get("document_id", ""),
            data.get("section_id", ""),
            data.get("section_title", ""),
        )
        return jsonify(action.to_dict())
    except Exception as e:
        logging.exception("Error in agent distraction return")
        return jsonify({"error": str(e)}), 500
