"""Upload and study content generation routes.

These routes turn an uploaded file into sections and generate flashcards,
quizzes, mind maps and mini games for a document or one of its sections.
"""

import logging
import uuid

from flask import Blueprint, jsonify, request

import database
from database import Document, DocumentSection, SectionProgress
from routes.common import ask_llm, extract_json, get_cached_content, save_content_cache
from web_config import UploadRejected, classify_upload

generation_bp = Blueprint("generation", __name__)


@generation_bp.route("/upload", methods=["POST"])
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
        try:
            is_pdf = classify_upload(filename, file_bytes) == "pdf"
        except UploadRejected as rejected:
            return jsonify({"error": str(rejected)}), 415

        # Process document into structured sections
        from document_processor import process_document, process_text_document

        if is_pdf:
            result = process_document(file_bytes, filename)
        else:
            # Text or Markdown file — read as text
            text_content = file_bytes.decode('utf-8')
            result = process_text_document(text_content, filename)

        doc_id = f"doc-{uuid.uuid4()}"

        # Save document to DB
        db = database.SessionLocal()
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



@generation_bp.route("/generate-flashcards", methods=["POST"])
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

        raw = ask_llm(prompt)
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


@generation_bp.route("/generate-quiz", methods=["POST"])
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

        raw = ask_llm(prompt)
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


@generation_bp.route("/generate-mindmap", methods=["POST"])
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

        raw = ask_llm(prompt)
        mindmap_data = extract_json(raw)

        save_content_cache(document_id, "mindmap", mindmap_data, section_id)
        return jsonify(mindmap_data)

    except Exception as e:
        logging.exception("Error generating mindmap")
        return jsonify({"error": str(e)}), 500


@generation_bp.route("/generate-mini-game", methods=["POST"])
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

        raw = ask_llm(prompt)
        mini_game_data = extract_json(raw)

        save_content_cache(document_id, "mini-game", mini_game_data, section_id)
        return jsonify(mini_game_data)

    except Exception as e:
        logging.exception("Error generating mini-game")
        return jsonify({"error": str(e)}), 500
