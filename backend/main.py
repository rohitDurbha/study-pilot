import uuid
import re
import json
import os
import logging
import base64

import anthropic
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Setup
logging.basicConfig(level=logging.DEBUG)
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"


def ask_claude(prompt: str, max_tokens: int = 4096) -> str:
    """Send a text-only prompt to Claude."""
    message = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def ask_claude_with_pdf(pdf_bytes: bytes, prompt: str, max_tokens: int = 4096) -> str:
    """Send a PDF document + prompt to Claude. Claude sees the full PDF natively."""
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    message = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )
    return message.content[0].text.strip()


def extract_json(text: str):
    """Robustly extract JSON from Claude's response, stripping markdown fences."""
    cleaned = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "Empty file uploaded"}), 400

    try:
        file_bytes = file.read()

        if not file_bytes:
            return jsonify({"error": "Empty file"}), 400

        filename = file.filename or "untitled"
        is_pdf = filename.lower().endswith('.pdf') and file_bytes[:4] == b'%PDF'

        # Process document into structured sections
        from document_processor import process_document, process_text_document

        if is_pdf:
            result = process_document(file_bytes, filename)
        else:
            # Text or Markdown file — read as text
            try:
                text_content = file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                text_content = file_bytes.decode('latin-1')
            result = process_text_document(text_content, filename)

        doc_id = f"doc-{uuid.uuid4()}"

        # Save document to DB
        db = SessionLocal()
        doc = Document(
            id=doc_id,
            filename=file.filename,
            summary=result.get("summary", ""),
            concepts=[c["id"] for c in result.get("knowledge_graph", {}).get("concepts", [])],
            knowledge_graph=result.get("knowledge_graph"),
        )
        db.add(doc)

        # Save sections
        sections_data = []
        for section in result.get("sections", []):
            sec = DocumentSection(
                id=section["id"],
                document_id=doc_id,
                title=section["title"],
                content=section["content"],
                concepts=section.get("concepts", []),
                prerequisites=section.get("prerequisites", []),
                section_order=section.get("order", 0),
                estimated_read_min=section.get("estimated_read_min", 3),
            )
            db.add(sec)

            # Initialize progress as not_started
            prog = SectionProgress(
                document_id=doc_id,
                section_id=section["id"],
                status="not_started",
            )
            db.add(prog)

            sections_data.append({
                "id": section["id"],
                "title": section["title"],
                "content": section["content"],
                "concepts": section.get("concepts", []),
                "prerequisites": section.get("prerequisites", []),
                "order": section.get("order", 0),
                "estimated_read_min": section.get("estimated_read_min", 3),
                "status": "not_started",
            })

        db.commit()
        db.close()

        # Index document for RAG pipeline (async-safe, non-blocking for response)
        try:
            from rag_pipeline import embed_and_store
            chunk_count = embed_and_store(doc_id, sections_data)
            logging.info(f"RAG: Indexed {chunk_count} chunks for document {doc_id}")
        except Exception as rag_err:
            logging.warning(f"RAG indexing failed (non-fatal): {rag_err}")

        return jsonify({
            "id": doc_id,
            "type": "sectioned",
            "data": {
                "title": result.get("title", file.filename.rsplit('.', 1)[0]),
                "summary": result.get("summary", ""),
                "sections": sections_data,
                "knowledge_graph": result.get("knowledge_graph"),
            }
        }), 200

    except Exception as e:
        logging.exception("Error processing upload")
        return jsonify({"error": "Server error", "details": str(e)}), 500


def get_cached_content(document_id: str, content_type: str, section_id: str = None):
    """Check if we already generated this content type for this document/section."""
    if not document_id:
        return None
    db = SessionLocal()
    query = db.query(GeneratedContent).filter(
        GeneratedContent.document_id == document_id,
        GeneratedContent.content_type == content_type,
    )
    if section_id:
        query = query.filter(GeneratedContent.section_id == section_id)
    cached = query.order_by(GeneratedContent.created_at.desc()).first()
    db.close()
    return cached.content_json if cached else None


def save_content_cache(document_id: str, content_type: str, content_json, section_id: str = None):
    """Save generated content to cache."""
    if not document_id:
        return
    db = SessionLocal()
    db.add(GeneratedContent(
        document_id=document_id,
        section_id=section_id,
        content_type=content_type,
        content_json=content_json,
    ))
    db.commit()
    db.close()


@app.route("/generate-flashcards", methods=["POST"])
def generate_flashcards():
    try:
        data = request.get_json()
        summarized_text = data.get("text")
        document_id = data.get("document_id")
        section_id = data.get("section_id")
        if not summarized_text:
            return jsonify({"error": "No text provided"}), 400

        cached = get_cached_content(document_id, "flipcard", section_id)
        if cached:
            return jsonify(cached)

        prompt = f"""You are creating flashcards for a student studying this material.

Content:
\"\"\"
{summarized_text}
\"\"\"

Create 5-7 flashcards focused on KEY DEFINITIONS and TERMINOLOGY.
- Front: A specific term, concept name, or "What is...?" question
- Back: A clear, concise definition or explanation (1-2 sentences max)
- Focus on terms the student needs to memorize
- Do NOT create questions about relationships between concepts (save that for quizzes)

Return as a raw JSON array only:
[{{"front": "...", "back": "..."}}]"""

        raw = ask_claude(prompt)
        cards = extract_json(raw)

        result = {
            "id": f"flashcard-{uuid.uuid4()}",
            "type": "flipcard",
            "data": {
                "title": "Key Terms",
                "cards": [
                    {"id": str(i + 1), "front": c["front"], "back": c["back"]}
                    for i, c in enumerate(cards)
                ]
            }
        }
        save_content_cache(document_id, "flipcard", result, section_id)
        return jsonify(result)

    except Exception as e:
        logging.exception("Error generating flashcards")
        return jsonify({"error": str(e)}), 500


@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    try:
        data = request.get_json()
        summarized_text = data.get("text")
        document_id = data.get("document_id")
        section_id = data.get("section_id")
        if not summarized_text:
            return jsonify({"error": "No text provided"}), 400

        cached = get_cached_content(document_id, "quiz", section_id)
        if cached:
            return jsonify(cached)

        prompt = f"""You are creating a comprehension quiz for a student.

Content:
\"\"\"
{summarized_text}
\"\"\"

Create 5-7 multiple choice questions that test UNDERSTANDING and APPLICATION, not just recall.
- Ask "Why does X happen?" not "What is X?"
- Ask "In scenario Y, what would happen?" not "Define Y"
- Ask "What is the relationship between X and Y?"
- Include one question that requires comparing two concepts
- Make wrong options plausible, not obviously wrong

Each question needs: question, options (4), correctOptionIndex (0-3), explanation

Return as a raw JSON array only:
[{{"question": "...", "options": ["...", "...", "...", "..."], "correctOptionIndex": 2, "explanation": "..."}}]"""

        raw = ask_claude(prompt)
        questions = extract_json(raw)

        result = {
            "id": f"quiz-{uuid.uuid4()}",
            "type": "quiz",
            "data": {
                "title": "Generated Quiz",
                "description": "Quiz to test your understanding!",
                "questions": [
                    {
                        "id": f"q{i + 1}",
                        "question": q["question"],
                        "options": q["options"],
                        "correctOptionIndex": q["correctOptionIndex"],
                        "explanation": q["explanation"]
                    }
                    for i, q in enumerate(questions)
                ]
            }
        }
        save_content_cache(document_id, "quiz", result, section_id)
        return jsonify(result)

    except Exception as e:
        logging.exception("Error generating quiz")
        return jsonify({"error": str(e)}), 500


@app.route("/generate-mindmap", methods=["POST"])
def generate_mindmap():
    try:
        data = request.get_json()
        summarized_text = data.get("text")
        document_id = data.get("document_id")
        section_id = data.get("section_id")
        if not summarized_text:
            return jsonify({"error": "No text provided"}), 400

        cached = get_cached_content(document_id, "mindmap", section_id)
        if cached:
            return jsonify(cached)

        prompt = f"""Given the following summarized content:

\"\"\"
{summarized_text}
\"\"\"

Create a mindmap in JSON format:
- A 'root' node with a string 'title'
- 'children' as an array of subtopics
- Each child can have its own children

Return ONLY valid JSON in this exact format, no explanation:
{{
  "id": "mindmap-id",
  "type": "mindmap",
  "data": {{
    "title": "Mind Map Title",
    "root": {{
      "title": "Root Topic",
      "children": [
        {{
          "title": "Subtopic 1",
          "children": [...]
        }}
      ]
    }}
  }}
}}"""

        raw = ask_claude(prompt)
        mindmap_data = extract_json(raw)

        save_content_cache(document_id, "mindmap", mindmap_data, section_id)
        return jsonify(mindmap_data)

    except Exception as e:
        logging.exception("Error generating mindmap")
        return jsonify({"error": str(e)}), 500


@app.route("/generate-mini-game", methods=["POST"])
def generate_mini_game():
    try:
        data = request.get_json()
        summarized_text = data.get("text")
        document_id = data.get("document_id")
        section_id = data.get("section_id")
        if not summarized_text:
            return jsonify({"error": "No text provided"}), 400

        cached = get_cached_content(document_id, "mini-game", section_id)
        if cached:
            return jsonify(cached)

        prompt = f"""You are a smart learning assistant.

Given the following summarized learning content:

\"\"\"
{summarized_text}
\"\"\"

Create a drag-and-drop mini-game with 4-5 pairs.
Each pair has a 'task' (keyword/term) and 'solution' (matching definition).

Return ONLY valid JSON in this exact format, no explanation:
{{
  "id": "mini-game-id",
  "type": "mini-game",
  "data": {{
    "title": "Mini Game Title",
    "challenges": [
      {{
        "task": "Operating System",
        "solution": "Acts as an intermediary between user and hardware",
        "uiType": "drag-drop"
      }}
    ]
  }}
}}"""

        raw = ask_claude(prompt)
        mini_game_data = extract_json(raw)

        save_content_cache(document_id, "mini-game", mini_game_data, section_id)
        return jsonify(mini_game_data)

    except Exception as e:
        logging.exception("Error generating mini-game")
        return jsonify({"error": str(e)}), 500


## ── Session & Analytics Endpoints ──

from database import SessionLocal, Document, DocumentSection, SectionProgress, StudySession, FocusEvent, QuizAttempt, ContentTransition, DistractionEvent, ChatMessage, GeneratedContent
from agent_engine import decide_welcome, decide_focus_drop, decide_section_complete, decide_quiz_result, decide_distraction_return, update_section_progress, get_next_section, get_section_progress_map
from knowledge_graph import extract_knowledge_graph
from study_agent import chat_with_agent, chat_with_agent_rag, generate_distraction_recap
from datetime import datetime


@app.route("/api/documents", methods=["POST"])
def create_document():
    """Store a processed document with its summary and knowledge graph."""
    try:
        data = request.get_json()
        doc_id = data.get("id", f"doc-{uuid.uuid4()}")
        filename = data.get("filename", "untitled")
        summary = data.get("summary", "")

        # Extract knowledge graph from summary
        kg = None
        try:
            kg = extract_knowledge_graph(summary)
        except Exception as e:
            logging.warning(f"Knowledge graph extraction failed: {e}")

        db = SessionLocal()
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


@app.route("/api/documents/<doc_id>/graph", methods=["GET"])
def get_knowledge_graph(doc_id):
    """Get the knowledge graph for a document."""
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    db.close()

    if not doc:
        return jsonify({"error": "Document not found"}), 404

    return jsonify({
        "document_id": doc_id,
        "concepts": doc.concepts or [],
        "knowledge_graph": doc.knowledge_graph,
    })


@app.route("/api/documents", methods=["GET"])
def list_documents():
    """List all documents."""
    db = SessionLocal()
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


@app.route("/api/documents/<doc_id>/rename", methods=["POST"])
def rename_document(doc_id):
    """Rename a document."""
    try:
        data = request.get_json()
        new_name = data.get("name", "").strip()
        if not new_name:
            return jsonify({"error": "Name cannot be empty"}), 400

        db = SessionLocal()
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


@app.route("/api/documents/latest", methods=["GET"])
def get_latest_document():
    """Get the most recent document with its summary."""
    db = SessionLocal()
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


@app.route("/api/sessions/latest", methods=["GET"])
def get_latest_session():
    """Get the most recent active session."""
    db = SessionLocal()
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


@app.route("/api/sessions", methods=["POST"])
def create_session():
    """Start a new study session."""
    try:
        data = request.get_json()
        session_id = f"session-{uuid.uuid4()}"
        document_id = data.get("document_id")

        db = SessionLocal()
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


@app.route("/api/sessions/<session_id>/focus", methods=["POST"])
def record_focus_events(session_id):
    """Record a batch of focus events."""
    try:
        data = request.get_json()
        events = data.get("events", [])

        db = SessionLocal()
        for event in events:
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


@app.route("/api/sessions/<session_id>/distraction", methods=["POST"])
def record_distraction(session_id):
    """Record a distraction event."""
    try:
        data = request.get_json()

        db = SessionLocal()
        de = DistractionEvent(
            session_id=session_id,
            started_at=datetime.utcnow(),
            duration_sec=data.get("duration_sec", 0),
        )
        db.add(de)

        # Update session distraction count
        session = db.query(StudySession).filter(StudySession.id == session_id).first()
        if session:
            session.distraction_count = (session.distraction_count or 0) + 1
        db.commit()
        db.close()

        return jsonify({"ok": True})

    except Exception as e:
        logging.exception("Error recording distraction")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/<session_id>/end", methods=["POST"])
def end_session(session_id):
    """End a study session and generate analytics."""
    try:
        db = SessionLocal()
        session = db.query(StudySession).filter(StudySession.id == session_id).first()
        if not session:
            db.close()
            return jsonify({"error": "Session not found"}), 404

        session.ended_at = datetime.utcnow()

        # Calculate analytics
        focus_events = db.query(FocusEvent).filter(FocusEvent.session_id == session_id).all()
        distractions = db.query(DistractionEvent).filter(DistractionEvent.session_id == session_id).all()
        transitions = db.query(ContentTransition).filter(ContentTransition.session_id == session_id).all()

        scores = [fe.focus_score for fe in focus_events if fe.focus_score is not None]
        avg_focus = sum(scores) / len(scores) if scores else 0

        duration_sec = (session.ended_at - session.started_at).total_seconds() if session.started_at else 0
        total_distraction_sec = sum(d.duration_sec or 0 for d in distractions)
        focused_time_sec = duration_sec - total_distraction_sec

        # Focus per content type
        focus_by_type = {}
        for fe in focus_events:
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


@app.route("/api/sessions/<session_id>/analytics", methods=["GET"])
def get_session_analytics(session_id):
    """Get analytics for a session."""
    db = SessionLocal()
    session = db.query(StudySession).filter(StudySession.id == session_id).first()
    db.close()

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(session.session_summary or {"status": "session still active"})


## ── Agent Endpoints ──

@app.route("/api/agent/chat", methods=["POST"])
def agent_chat():
    """Chat with the study agent. Supports both full-context and RAG pipelines."""
    try:
        data = request.get_json()
        user_message = data.get("message", "")
        session_id = data.get("sessionId")
        context = data.get("context", {})
        pipeline = data.get("pipeline", "full_context")  # "rag" or "full_context"

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        # Load history from DB if session exists
        conversation_history = []
        document_id = None
        if session_id:
            db = SessionLocal()
            msgs = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at).all()
            conversation_history = [{"role": m.role, "content": m.content} for m in msgs]

            # Get document_id from session
            session = db.query(StudySession).filter(StudySession.id == session_id).first()
            if session:
                document_id = session.document_id

            # Save user message
            db.add(ChatMessage(session_id=session_id, role="user", content=user_message))
            db.commit()
            db.close()

        sources = []

        if pipeline == "rag" and document_id:
            # RAG pipeline
            result = chat_with_agent_rag(
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
            # Full context pipeline (original)
            response_text = chat_with_agent(
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

        # Save assistant response
        if session_id:
            db = SessionLocal()
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


@app.route("/api/agent/history/<session_id>", methods=["GET"])
def get_chat_history(session_id):
    """Load chat history for a session."""
    db = SessionLocal()
    msgs = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).all()
    db.close()

    return jsonify({
        "messages": [{"role": m.role, "content": m.content} for m in msgs]
    })


@app.route("/api/agent/recap", methods=["POST"])
def agent_recap():
    """Generate a distraction recovery recap."""
    try:
        data = request.get_json()

        recap = generate_distraction_recap(
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


## ── TTS Endpoint ──

@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    """Generate natural-sounding speech from text using Edge TTS."""
    try:
        import asyncio
        import edge_tts
        import tempfile

        data = request.get_json()
        text = data.get("text", "")
        voice = data.get("voice", "en-US-JennyNeural")  # Soft, warm voice

        if not text:
            return jsonify({"error": "No text provided"}), 400

        # Truncate if too long
        if len(text) > 8000:
            text = text[:8000]

        # Generate audio — Edge TTS respects newlines as pauses
        async def generate():
            communicate = edge_tts.Communicate(text, voice, rate="-10%", pitch="-2Hz", volume="-10%")
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", dir=os.path.join(os.path.dirname(__file__), "static"))
            await communicate.save(tmp.name)
            return tmp.name

        # Run async in sync context
        loop = asyncio.new_event_loop()
        filepath = loop.run_until_complete(generate())
        loop.close()

        filename = os.path.basename(filepath)
        return jsonify({"url": f"/static/{filename}"})

    except Exception as e:
        logging.exception("Error generating TTS")
        return jsonify({"error": str(e)}), 500


## ── Serve static audio files ──
import os as _os
_static_dir = _os.path.join(_os.path.dirname(__file__), "static")
_os.makedirs(_static_dir, exist_ok=True)

@app.route("/static/<path:filename>")
def serve_static(filename):
    from flask import send_from_directory
    return send_from_directory(_static_dir, filename)


## ── Agent Decision Endpoints ──

@app.route("/api/agent/decide/welcome", methods=["POST"])
def agent_decide_welcome():
    """Get the agent's welcome/resume message for a document."""
    try:
        data = request.get_json()
        document_id = data.get("document_id")
        if not document_id:
            return jsonify({"error": "No document_id"}), 400

        action = decide_welcome(document_id)
        return jsonify(action.to_dict())
    except Exception as e:
        logging.exception("Error in agent welcome")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/decide/focus-drop", methods=["POST"])
def agent_decide_focus_drop():
    """Get the agent's suggestion when focus drops."""
    try:
        data = request.get_json()
        action = decide_focus_drop(
            data.get("document_id", ""),
            data.get("section_id", ""),
            data.get("content_type", "text"),
        )
        return jsonify(action.to_dict())
    except Exception as e:
        logging.exception("Error in agent focus drop")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/decide/section-complete", methods=["POST"])
def agent_decide_section_complete():
    """Get the agent's suggestion after a section is read."""
    try:
        data = request.get_json()
        action = decide_section_complete(data.get("document_id", ""), data.get("section_id", ""))
        return jsonify(action.to_dict())
    except Exception as e:
        logging.exception("Error in agent section complete")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/decide/quiz-result", methods=["POST"])
def agent_decide_quiz_result():
    """Get the agent's suggestion after a quiz."""
    try:
        data = request.get_json()
        action = decide_quiz_result(
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


@app.route("/api/agent/decide/distraction-return", methods=["POST"])
def agent_decide_distraction_return():
    """Get the agent's message when student returns from distraction."""
    try:
        data = request.get_json()
        action = decide_distraction_return(
            data.get("document_id", ""),
            data.get("section_id", ""),
            data.get("section_title", ""),
        )
        return jsonify(action.to_dict())
    except Exception as e:
        logging.exception("Error in agent distraction return")
        return jsonify({"error": str(e)}), 500


## ── Section Progress Endpoints ──

@app.route("/api/sections/<document_id>", methods=["GET"])
def get_sections(document_id):
    """Get all sections with progress for a document."""
    db = SessionLocal()
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


@app.route("/api/sections/<document_id>/<section_id>/progress", methods=["POST"])
def update_progress(document_id, section_id):
    """Update the progress of a section."""
    try:
        data = request.get_json()
        status = data.get("status", "in_progress")
        quiz_score = data.get("quiz_score")

        update_section_progress(document_id, section_id, status, quiz_score)

        return jsonify({"ok": True})
    except Exception as e:
        logging.exception("Error updating progress")
        return jsonify({"error": str(e)}), 500


## ── RAG Evaluation Endpoints ──

@app.route("/api/eval/generate-tests/<document_id>", methods=["POST"])
def eval_generate_tests(document_id):
    """Generate test cases for a document."""
    try:
        from eval_harness import generate_test_set
        cases = generate_test_set(document_id)
        return jsonify({"count": len(cases), "test_cases": cases})
    except Exception as e:
        logging.exception("Error generating test cases")
        return jsonify({"error": str(e)}), 500


@app.route("/api/eval/run/<document_id>", methods=["POST"])
def eval_run(document_id):
    """Run full RAG vs Full-Context evaluation."""
    try:
        from eval_harness import generate_test_set, run_evaluation
        # Generate test cases if none exist
        db = SessionLocal()
        from database import EvalTestCase
        count = db.query(EvalTestCase).filter(EvalTestCase.document_id == document_id).count()
        db.close()
        if count == 0:
            generate_test_set(document_id)

        result = run_evaluation(document_id)
        return jsonify(result)
    except Exception as e:
        logging.exception("Error running evaluation")
        return jsonify({"error": str(e)}), 500


@app.route("/api/eval/runs/<document_id>", methods=["GET"])
def eval_list_runs(document_id):
    """List all eval runs for a document."""
    from eval_harness import get_eval_runs
    return jsonify({"runs": get_eval_runs(document_id)})


@app.route("/api/eval/detail/<int:run_id>", methods=["GET"])
def eval_run_detail(run_id):
    """Get detailed results for a specific eval run."""
    from eval_harness import get_eval_run_detail
    return jsonify(get_eval_run_detail(run_id))


@app.route("/api/rag/reindex/<document_id>", methods=["POST"])
def rag_reindex(document_id):
    """Re-index an existing document for RAG (for docs uploaded before RAG was added)."""
    try:
        from rag_pipeline import embed_and_store
        db = SessionLocal()
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

        chunk_count = embed_and_store(document_id, sections_data)
        return jsonify({"chunks_indexed": chunk_count, "sections": len(sections_data)})
    except Exception as e:
        logging.exception("Error re-indexing")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5005)
