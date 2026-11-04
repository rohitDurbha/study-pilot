"""Document processing — splits PDF into structured sections with concepts."""
import json
import re
import uuid
import base64
import logging

import anthropic
import os
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"


def extract_json_from_response(text: str):
    cleaned = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned, flags=re.MULTILINE)
    return json.loads(cleaned.strip())


def process_document(pdf_bytes: bytes, filename: str) -> dict:
    """Process a PDF into structured sections with concepts and prerequisites.

    Returns:
    {
        "title": "Document Title",
        "summary": "Brief overall summary",
        "sections": [
            {
                "id": "section-1",
                "title": "Section Title",
                "content": "Markdown content...",
                "concepts": ["concept-1", "concept-2"],
                "prerequisites": [],
                "estimated_read_min": 3
            },
            ...
        ],
        "knowledge_graph": {
            "concepts": [
                {"id": "concept-1", "name": "...", "description": "...", "importance": 5, "prerequisites": []}
            ]
        }
    }
    """
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    prompt = """You are an expert educator. Analyze this document and break it into structured study sections.

For each section:
1. Give it a clear title
2. Write a well-structured Markdown summary (use ## headings, bullet points, highlights)
3. List the key concepts covered
4. Note which concepts from earlier sections are prerequisites
5. Estimate reading time in minutes

Also extract a knowledge graph of all concepts with their prerequisite relationships.

Return ONLY valid JSON in this exact format:
{
  "title": "Document Title",
  "summary": "A 2-3 sentence overview of the entire document",
  "sections": [
    {
      "title": "Section Title",
      "content": "## Section Title\\n\\nMarkdown content with proper formatting...\\n\\n- Key point 1\\n- Key point 2",
      "concepts": ["concept-name-1", "concept-name-2"],
      "prerequisites": [],
      "estimated_read_min": 3
    },
    {
      "title": "Next Section",
      "content": "## Next Section\\n\\nMore content...",
      "concepts": ["concept-name-3"],
      "prerequisites": ["concept-name-1"],
      "estimated_read_min": 4
    }
  ],
  "knowledge_graph": {
    "concepts": [
      {
        "id": "concept-name-1",
        "name": "Concept Name",
        "description": "Brief description",
        "importance": 5,
        "prerequisites": []
      }
    ]
  }
}

Rules:
- IMPORTANT: Scale sections to document size. Short documents (1-3 pages) get 2-3 sections max. Medium (4-10 pages) get 3-5 sections. Long (10+ pages) get 5-8 sections. Never create more sections than makes sense for the content.
- Each section should be substantial — at least 3-5 minutes of reading. Don't split thin topics into separate sections.
- Content should be detailed enough to study from, not just a summary
- If there are diagrams or images, describe what they show
- Concepts should use kebab-case IDs
- Prerequisites reference concept IDs from the same list
- Write for a college-level audience"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=8192,
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

    result = extract_json_from_response(message.content[0].text.strip())

    # Add IDs to sections
    for i, section in enumerate(result.get("sections", [])):
        section["id"] = f"section-{i + 1}"
        section["order"] = i + 1

    return result


def process_text_document(text: str, filename: str) -> dict:
    """Process a plain text or markdown document into structured sections."""

    if len(text) > 30000:
        text = text[:30000]

    prompt = f"""You are an expert educator. Analyze this text and break it into structured study sections.

Text:
\"\"\"
{text}
\"\"\"

For each section:
1. Give it a clear title
2. Write a well-structured Markdown summary
3. List the key concepts covered
4. Note prerequisites from earlier sections
5. Estimate reading time

Also extract a knowledge graph of concepts.

Return ONLY valid JSON in this format:
{{
  "title": "Document Title",
  "summary": "2-3 sentence overview",
  "sections": [
    {{
      "title": "Section Title",
      "content": "## Section Title\\n\\nMarkdown content...",
      "concepts": ["concept-1"],
      "prerequisites": [],
      "estimated_read_min": 3
    }}
  ],
  "knowledge_graph": {{
    "concepts": [
      {{
        "id": "concept-1",
        "name": "Name",
        "description": "Brief description",
        "importance": 5,
        "prerequisites": []
      }}
    ]
  }}
}}

Scale sections to content length: short text gets 2-3 sections, medium gets 3-5, long gets 5-8. Each section should be substantial. Use kebab-case for concept IDs."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    result = extract_json_from_response(message.content[0].text.strip())

    for i, section in enumerate(result.get("sections", [])):
        section["id"] = f"section-{i + 1}"
        section["order"] = i + 1

    return result
