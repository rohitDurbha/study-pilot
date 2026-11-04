"""Knowledge graph extraction using Claude."""
import json
import re
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


def extract_knowledge_graph(summary_text: str) -> dict:
    """Extract concepts and prerequisite relationships from a document summary."""

    prompt = f"""You are an expert educator. Analyze this study material and extract a knowledge graph.

Document:
\"\"\"
{summary_text}
\"\"\"

Extract:
1. All key concepts (terms, ideas, theories) from this document
2. For each concept, identify which other concepts are prerequisites (must be understood first)
3. Rate each concept's importance (1-5, where 5 is most critical to understand)

Return ONLY valid JSON in this exact format:
{{
  "concepts": [
    {{
      "id": "concept-1",
      "name": "Operating System",
      "description": "Brief one-line description",
      "importance": 5,
      "prerequisites": []
    }},
    {{
      "id": "concept-2",
      "name": "Process Scheduling",
      "description": "How OS decides which process runs next",
      "importance": 4,
      "prerequisites": ["concept-1"]
    }}
  ]
}}

Rules:
- Extract 8-20 concepts depending on document complexity
- Prerequisites reference concept IDs from the same list
- A concept can have zero or more prerequisites
- Order concepts roughly by learning sequence"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    result = extract_json_from_response(message.content[0].text.strip())
    return result
