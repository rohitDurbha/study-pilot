"""Helpers shared by the route blueprints.

The model helpers wrap llm.py so every route asks for text the same way, and the
content cache stores generated flashcards, quizzes, mind maps and mini games so
the same section is not sent to the model twice.
"""

import database
import llm
from database import GeneratedContent
from json_reply import extract_json, json_body

__all__ = [
    "DEFAULT_MAX_TOKENS",
    "ask_llm",
    "ask_llm_with_pdf",
    "extract_json",
    "get_cached_content",
    "json_body",
    "save_content_cache",
]

DEFAULT_MAX_TOKENS = 4096


def ask_llm(prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """Send a text prompt to the configured providers (Groq first, then Gemini)."""
    return llm.generate_text(prompt, max_tokens=max_tokens)


def ask_llm_with_pdf(pdf_bytes: bytes, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """Send a PDF and a prompt. Groq gets the extracted text, Gemini reads the PDF itself."""
    return llm.generate_text(prompt, pdf_bytes=pdf_bytes, max_tokens=max_tokens)


def get_cached_content(document_id: str, content_type: str, section_id: str = None):
    """Check if we already generated this content type for this document/section."""
    if not document_id:
        return None
    db = database.SessionLocal()
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
    db = database.SessionLocal()
    db.add(GeneratedContent(
        document_id=document_id,
        section_id=section_id,
        content_type=content_type,
        content_json=content_json,
    ))
    db.commit()
    db.close()
