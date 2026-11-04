"""Agent decision engine — determines what to show and when to intervene.

This is NOT an LLM call. It's deterministic logic that reads from the DB
and returns structured decisions.
"""
from database import SessionLocal, DocumentSection, SectionProgress, Document
from datetime import datetime


class AgentAction:
    """Represents a decision the agent makes."""
    def __init__(self, action_type: str, message: str, data: dict = None, buttons: list = None):
        self.action_type = action_type  # welcome, section_complete, focus_drop, quiz_result, prerequisite, distraction_return, break_suggest
        self.message = message
        self.data = data or {}
        self.buttons = buttons or []

    def to_dict(self):
        return {
            "type": self.action_type,
            "message": self.message,
            "data": self.data,
            "buttons": self.buttons,
        }


def get_section_progress_map(document_id: str) -> dict:
    """Get progress status for all sections of a document."""
    db = SessionLocal()
    sections = db.query(DocumentSection).filter(
        DocumentSection.document_id == document_id
    ).order_by(DocumentSection.section_order).all()

    progress_map = {}
    for section in sections:
        prog = db.query(SectionProgress).filter(
            SectionProgress.section_id == section.id,
            SectionProgress.document_id == document_id,
        ).first()

        progress_map[section.id] = {
            "section_id": section.id,
            "title": section.title,
            "order": section.section_order,
            "status": prog.status if prog else "not_started",
            "quiz_score": prog.quiz_score if prog else None,
            "concepts": section.concepts or [],
            "prerequisites": section.prerequisites or [],
        }

    db.close()
    return progress_map


def get_next_section(document_id: str, current_section_id: str = None) -> dict:
    """Determine the next section the student should study."""
    progress = get_section_progress_map(document_id)

    if not progress:
        return None

    sections_list = sorted(progress.values(), key=lambda s: s["order"])

    # If no current section, find first unmastered section
    if not current_section_id:
        for s in sections_list:
            if s["status"] not in ("mastered", "tested"):
                return s
        # All mastered — return first for review
        return sections_list[0] if sections_list else None

    # Find current position and get next unmastered
    current_order = None
    for s in sections_list:
        if s["section_id"] == current_section_id:
            current_order = s["order"]
            break

    if current_order is None:
        return sections_list[0] if sections_list else None

    # Look for next unmastered section after current
    for s in sections_list:
        if s["order"] > current_order and s["status"] not in ("mastered", "tested"):
            return s

    # All remaining are done — loop back to first unmastered
    for s in sections_list:
        if s["status"] not in ("mastered", "tested"):
            return s

    return None


def check_prerequisites(document_id: str, section_id: str) -> list:
    """Check if prerequisites for a section are met. Returns list of unmet prerequisites."""
    progress = get_section_progress_map(document_id)
    section = progress.get(section_id)

    if not section or not section["prerequisites"]:
        return []

    unmet = []
    for prereq_concept in section["prerequisites"]:
        # Check if any section that covers this concept is mastered
        concept_mastered = False
        for s in progress.values():
            if prereq_concept in (s.get("concepts") or []):
                if s["status"] in ("tested", "mastered"):
                    concept_mastered = True
                    break
        if not concept_mastered:
            unmet.append(prereq_concept)

    return unmet


def decide_welcome(document_id: str) -> AgentAction:
    """Generate welcome message when student opens a document."""
    progress = get_section_progress_map(document_id)
    sections = sorted(progress.values(), key=lambda s: s["order"])

    total = len(sections)
    mastered = sum(1 for s in sections if s["status"] in ("mastered", "tested"))

    if mastered == 0:
        # First time
        first = sections[0] if sections else None
        return AgentAction(
            action_type="welcome",
            message=f"I've organized your material into {total} sections. Let's start with \"{first['title']}\"." if first else "Ready to study.",
            data={
                "total_sections": total,
                "mastered": 0,
                "next_section_id": first["section_id"] if first else None,
                "next_section_title": first["title"] if first else None,
            },
            buttons=[
                {"label": "Start studying", "action": "start_section", "section_id": first["section_id"] if first else None}
            ],
        )
    else:
        # Returning student
        next_section = get_next_section(document_id)
        if next_section:
            # Check prerequisites
            unmet = check_prerequisites(document_id, next_section["section_id"])
            if unmet:
                return AgentAction(
                    action_type="prerequisite",
                    message=f"Welcome back. You've mastered {mastered}/{total} sections. Next up: \"{next_section['title']}\", but it needs {', '.join(unmet)}. Want a quick review first?",
                    data={
                        "total_sections": total,
                        "mastered": mastered,
                        "next_section_id": next_section["section_id"],
                        "unmet_prerequisites": unmet,
                    },
                    buttons=[
                        {"label": "Review prerequisites", "action": "review_prerequisites"},
                        {"label": "Continue anyway", "action": "start_section", "section_id": next_section["section_id"]},
                    ],
                )
            else:
                return AgentAction(
                    action_type="welcome",
                    message=f"Welcome back. {mastered}/{total} sections mastered. Ready for \"{next_section['title']}\"?",
                    data={
                        "total_sections": total,
                        "mastered": mastered,
                        "next_section_id": next_section["section_id"],
                        "next_section_title": next_section["title"],
                    },
                    buttons=[
                        {"label": "Continue", "action": "start_section", "section_id": next_section["section_id"]},
                        {"label": "Review previous", "action": "review_previous"},
                    ],
                )
        else:
            return AgentAction(
                action_type="welcome",
                message=f"All {total} sections mastered. Want to review any section?",
                data={"total_sections": total, "mastered": mastered},
                buttons=[
                    {"label": "Review from start", "action": "start_section", "section_id": sections[0]["section_id"] if sections else None}
                ],
            )


def decide_focus_drop(document_id: str, section_id: str, current_content_type: str) -> AgentAction:
    """Decide what to do when focus drops."""
    if current_content_type == "text":
        return AgentAction(
            action_type="focus_drop",
            message="This section is getting dense. Want to try flashcards instead?",
            data={"section_id": section_id, "suggested_type": "flipcard"},
            buttons=[
                {"label": "Switch to flashcards", "action": "switch_content", "content_type": "flipcard"},
                {"label": "Keep reading", "action": "dismiss"},
            ],
        )
    elif current_content_type == "flipcard":
        return AgentAction(
            action_type="focus_drop",
            message="Let's test what you've learned with a quick quiz.",
            data={"section_id": section_id, "suggested_type": "quiz"},
            buttons=[
                {"label": "Take quiz", "action": "switch_content", "content_type": "quiz"},
                {"label": "Keep going", "action": "dismiss"},
            ],
        )
    else:
        return AgentAction(
            action_type="focus_drop",
            message="Let's try something different. How about a mind map?",
            data={"section_id": section_id, "suggested_type": "mindmap"},
            buttons=[
                {"label": "Show mind map", "action": "switch_content", "content_type": "mindmap"},
                {"label": "Keep going", "action": "dismiss"},
            ],
        )


def decide_section_complete(document_id: str, section_id: str) -> AgentAction:
    """Decide what happens after a section is read."""
    return AgentAction(
        action_type="section_complete",
        message="You've read through this section. Let me check what stuck.",
        data={"section_id": section_id},
        buttons=[
            {"label": "Take quiz", "action": "switch_content", "content_type": "quiz"},
            {"label": "Next section", "action": "next_section"},
        ],
    )


def decide_quiz_result(document_id: str, section_id: str, score: float, total: int, weak_concepts: list) -> AgentAction:
    """Decide what to do after a quiz."""
    correct = int(score * total)
    progress = get_section_progress_map(document_id)
    next_section = get_next_section(document_id, section_id)

    if score >= 0.7:
        # Good score — mark as tested, move on
        msg = f"{correct}/{total} correct. Great work!"
        if weak_concepts:
            msg += f" {', '.join(weak_concepts)} could use a review."

        buttons = []
        if next_section:
            buttons.append({"label": "Next section", "action": "start_section", "section_id": next_section["section_id"]})
        if weak_concepts:
            buttons.append({"label": "Review weak concepts", "action": "switch_content", "content_type": "flipcard"})

        return AgentAction(
            action_type="quiz_result",
            message=msg,
            data={"score": score, "correct": correct, "total": total, "weak_concepts": weak_concepts,
                  "next_section_id": next_section["section_id"] if next_section else None},
            buttons=buttons or [{"label": "Continue", "action": "dismiss"}],
        )
    else:
        # Low score — review needed
        return AgentAction(
            action_type="quiz_result",
            message=f"{correct}/{total}. Let's review with flashcards before moving on.",
            data={"score": score, "correct": correct, "total": total, "weak_concepts": weak_concepts},
            buttons=[
                {"label": "Review with flashcards", "action": "switch_content", "content_type": "flipcard"},
                {"label": "Re-read section", "action": "switch_content", "content_type": "text"},
            ],
        )


def decide_distraction_return(document_id: str, section_id: str, section_title: str) -> AgentAction:
    """Decide what to show when student returns from a distraction."""
    return AgentAction(
        action_type="distraction_return",
        message=f"You were reading \"{section_title}\". Pick up where you left off.",
        data={"section_id": section_id},
        buttons=[
            {"label": "Continue", "action": "dismiss"},
        ],
    )


def update_section_progress(document_id: str, section_id: str, status: str, quiz_score: float = None):
    """Update the progress of a section."""
    db = SessionLocal()
    prog = db.query(SectionProgress).filter(
        SectionProgress.section_id == section_id,
        SectionProgress.document_id == document_id,
    ).first()

    if prog:
        prog.status = status
        if quiz_score is not None:
            prog.quiz_score = max(prog.quiz_score or 0, quiz_score)
        prog.last_accessed = datetime.utcnow()
    else:
        prog = SectionProgress(
            document_id=document_id,
            section_id=section_id,
            status=status,
            quiz_score=quiz_score,
            last_accessed=datetime.utcnow(),
        )
        db.add(prog)

    db.commit()
    db.close()
