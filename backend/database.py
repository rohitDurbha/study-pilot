import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DB_PATH = os.path.join(os.path.dirname(__file__), "studybuddy.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    summary = Column(Text)  # Full document summary (kept for agent context)
    concepts = Column(JSON)
    knowledge_graph = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("StudySession", back_populates="document")
    sections = relationship("DocumentSection", back_populates="document", order_by="DocumentSection.section_order")


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"))
    title = Column(String)
    content = Column(Text)  # Markdown content for this section
    concepts = Column(JSON)  # Concept IDs covered
    prerequisites = Column(JSON)  # Section IDs or concept IDs needed first
    section_order = Column(Integer)
    estimated_read_min = Column(Float, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="sections")
    progress = relationship("SectionProgress", back_populates="section")


class SectionProgress(Base):
    __tablename__ = "section_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("documents.id"))
    section_id = Column(String, ForeignKey("document_sections.id"))
    status = Column(String, default="not_started")  # not_started, in_progress, read, tested, mastered
    quiz_score = Column(Float, nullable=True)
    time_spent_sec = Column(Float, default=0)
    last_accessed = Column(DateTime, nullable=True)

    section = relationship("DocumentSection", back_populates="progress")


class StudySession(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"))
    current_section_id = Column(String, nullable=True)  # Where the student is right now
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    total_focus_time_sec = Column(Float, default=0)
    avg_focus_score = Column(Float, default=0)
    distraction_count = Column(Integer, default=0)
    content_switches = Column(Integer, default=0)
    session_summary = Column(JSON)

    document = relationship("Document", back_populates="sessions")
    focus_events = relationship("FocusEvent", back_populates="session")
    quiz_attempts = relationship("QuizAttempt", back_populates="session")
    transitions = relationship("ContentTransition", back_populates="session")
    distractions = relationship("DistractionEvent", back_populates="session")


class FocusEvent(Base):
    __tablename__ = "focus_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    focus_score = Column(Float)
    content_type = Column(String)
    section_id = Column(String, nullable=True)

    session = relationship("StudySession", back_populates="focus_events")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    section_id = Column(String, nullable=True)
    question_text = Column(Text)
    user_answer = Column(String)
    is_correct = Column(Integer)
    time_spent_ms = Column(Integer)
    concept = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("StudySession", back_populates="quiz_attempts")


class ContentTransition(Base):
    __tablename__ = "content_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    from_type = Column(String)
    to_type = Column(String)
    reason = Column(String)
    focus_before = Column(Float)
    focus_after = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("StudySession", back_populates="transitions")


class DistractionEvent(Base):
    __tablename__ = "distraction_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    started_at = Column(DateTime)
    duration_sec = Column(Float)

    session = relationship("StudySession", back_populates="distractions")


class GeneratedContent(Base):
    __tablename__ = "generated_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("documents.id"))
    section_id = Column(String, nullable=True)  # Per-section content
    content_type = Column(String)
    content_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalTestCase(Base):
    __tablename__ = "eval_test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("documents.id"))
    section_id = Column(String)
    question = Column(Text)
    ground_truth = Column(Text)
    source_chunk_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("documents.id"))
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # running | completed | failed
    summary = Column(JSON)


class EvalResult(Base):
    __tablename__ = "eval_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("eval_runs.id"))
    test_case_id = Column(Integer, ForeignKey("eval_test_cases.id"))
    pipeline = Column(String)  # "rag" or "full_context"
    answer = Column(Text)
    accuracy_score = Column(Float)
    relevance_score = Column(Float)
    groundedness_score = Column(Float)
    latency_ms = Column(Integer)
    token_count = Column(Integer)
    retrieved_chunks = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


# Create all tables
Base.metadata.create_all(engine)
