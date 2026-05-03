from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="user")
    tasks = relationship("Task", back_populates="user")
    sessions = relationship("ChatSession", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(256), nullable=False)
    stored_path = Column(String(512), nullable=False)
    chunk_count = Column(Integer, default=0)
    status = Column(
        Enum("uploading", "ready", "failed"),
        default="uploading"
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="documents")
    tasks = relationship("Task", back_populates="document")
    sessions = relationship("ChatSession", back_populates="document")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    rag_strategy = Column(String(50), default="basic")
    status = Column(
        Enum("pending", "running", "done", "failed"),
        default="pending"
    )
    result_path = Column(String(512), nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tasks")
    document = relationship("Document", back_populates="tasks")
    session = relationship("ChatSession", back_populates="task", uselist=False)


class ChatSession(Base):
    """对话持久化表 —— ConversationManager 的热缓存 + 此表做冷存储"""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(16), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    rag_strategy = Column(String(50), default="basic")

    messages = Column(Text, default="[]")
    clarified = Column(Text, default="{}")
    retrieval_cache = Column(Text, default="{}")
    ppt_draft = Column(Text, nullable=True)

    stage = Column(
        Enum("clarifying", "confirmed", "generating", "done"),
        default="clarifying"
    )
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    user_preferences = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    document = relationship("Document", back_populates="sessions")
    task = relationship("Task", back_populates="session", uselist=False)
