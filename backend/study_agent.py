"""Agentic study assistant — the brain of StudyBuddy."""
import json
import anthropic
import os
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"


def build_agent_context(
    document_title: str,
    summary_text: str,
    focus_score: int,
    current_content_type: str,
    distraction_count: int,
    session_duration_min: int,
    knowledge_graph: dict = None,
    quiz_performance: dict = None,
) -> str:
    """Build the context string the agent sees."""

    context = f"""You are StudyBuddy, an AI study assistant. You are currently helping a student study.

CURRENT SESSION STATE:
- Document: "{document_title}"
- Current content format: {current_content_type}
- Student's focus score: {focus_score}% (0=not focused, 100=deeply focused)
- Session duration: {session_duration_min} minutes
- Distractions this session: {distraction_count}

DOCUMENT SUMMARY:
{summary_text[:3000]}
"""

    if knowledge_graph and knowledge_graph.get("concepts"):
        concepts = knowledge_graph["concepts"]
        concept_names = [c["name"] for c in concepts[:15]]
        context += f"\nKEY CONCEPTS IN THIS DOCUMENT:\n{', '.join(concept_names)}\n"

    if quiz_performance:
        context += f"\nQUIZ PERFORMANCE:\n"
        context += f"- Questions answered: {quiz_performance.get('total', 0)}\n"
        context += f"- Correct: {quiz_performance.get('correct', 0)}\n"
        if quiz_performance.get('weak_concepts'):
            context += f"- Weak areas: {', '.join(quiz_performance['weak_concepts'])}\n"

    context += """
YOUR ROLE:
- Help the student understand the material
- Answer questions about the document
- If their focus is low, keep responses short and engaging
- If they just returned from a distraction, briefly recap where they were
- Never mention focus scores or tracking directly — be natural
- Be concise. Students don't want walls of text.
"""

    return context


def chat_with_agent(
    user_message: str,
    conversation_history: list,
    document_title: str = "",
    summary_text: str = "",
    focus_score: int = 75,
    current_content_type: str = "text",
    distraction_count: int = 0,
    session_duration_min: int = 0,
    knowledge_graph: dict = None,
    quiz_performance: dict = None,
) -> str:
    """Send a message to the study agent and get a response."""

    system_prompt = build_agent_context(
        document_title=document_title,
        summary_text=summary_text,
        focus_score=focus_score,
        current_content_type=current_content_type,
        distraction_count=distraction_count,
        session_duration_min=session_duration_min,
        knowledge_graph=knowledge_graph,
        quiz_performance=quiz_performance,
    )

    # Build messages from history
    messages = []
    for entry in conversation_history:
        messages.append({
            "role": entry["role"],
            "content": entry["content"],
        })

    # Add current message
    messages.append({
        "role": "user",
        "content": user_message,
    })

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text.strip()


def chat_with_agent_rag(
    user_message: str,
    conversation_history: list,
    document_id: str,
    document_title: str = "",
    focus_score: int = 75,
    current_content_type: str = "text",
    distraction_count: int = 0,
    session_duration_min: int = 0,
    knowledge_graph: dict = None,
    quiz_performance: dict = None,
) -> dict:
    """Chat using RAG pipeline — retrieves relevant chunks before answering."""
    from rag_pipeline import retrieve_chunks, build_rag_prompt

    # Retrieve relevant chunks
    chunks = retrieve_chunks(document_id, user_message, top_k=5)
    rag_context = build_rag_prompt(user_message, chunks)

    system_prompt = f"""You are StudyBuddy, an AI study assistant.

CURRENT SESSION STATE:
- Document: "{document_title}"
- Content format: {current_content_type}
- Focus score: {focus_score}%
- Session: {session_duration_min} minutes
- Distractions: {distraction_count}

{rag_context}

YOUR ROLE:
- Answer using ONLY the retrieved context above
- Cite sources with [1], [2], etc.
- Be concise and helpful
- If their focus is low, keep responses short and engaging
- Never mention focus scores directly — be natural
"""

    if knowledge_graph and knowledge_graph.get("concepts"):
        concepts = knowledge_graph["concepts"]
        concept_names = [c["name"] for c in concepts[:15]]
        system_prompt += f"\nKEY CONCEPTS: {', '.join(concept_names)}\n"

    if quiz_performance:
        system_prompt += f"\nQUIZ: {quiz_performance.get('correct', 0)}/{quiz_performance.get('total', 0)} correct\n"

    messages = [{"role": e["role"], "content": e["content"]} for e in conversation_history]
    messages.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )

    return {
        "response": response.content[0].text.strip(),
        "sources": [
            {
                "text": c["text"][:200],
                "section_id": c["section_id"],
                "section_title": c["section_title"],
                "score": c["score"],
            }
            for c in chunks
        ],
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }


def generate_distraction_recap(
    document_title: str,
    summary_text: str,
    last_content_type: str,
    last_section_context: str = "",
    absence_duration_sec: int = 0,
) -> str:
    """Generate a brief recap for when the student returns from a distraction."""

    prompt = f"""A student was studying "{document_title}" in {last_content_type} mode.
They left for {absence_duration_sec} seconds and just came back.

Document summary (what they were studying):
{summary_text[:2000]}

{f'They were last reading about: {last_section_context}' if last_section_context else ''}

Write a 2-3 sentence recap of where they were and what comes next.
Be warm but brief. Don't mention the distraction duration or make them feel guilty.
Just help them pick up where they left off."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()
