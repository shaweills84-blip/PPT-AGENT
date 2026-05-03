from sqlalchemy.orm import Session
from db.models import User, Document, Task, ChatSession
from db.schemas import UserCreate, TaskCreate
import hashlib


# ========== User ==========

def create_user(db: Session, user: UserCreate) -> User:
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    db_user = User(email=user.email, password_hash=password_hash)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user:
        return None
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user.password_hash != password_hash:
        return None
    return user


# ========== Document ==========

def create_document(db: Session, user_id: int, filename: str,
                    stored_path: str) -> Document:
    doc = Document(
        user_id=user_id,
        filename=filename,
        stored_path=stored_path,
        status="uploading"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def update_document_status(db: Session, doc_id: int, status: str,
                           chunk_count: int = None):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc:
        doc.status = status
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        db.commit()


def get_user_documents(db: Session, user_id: int) -> list[Document]:
    return db.query(Document).filter(
        Document.user_id == user_id
    ).order_by(Document.created_at.desc()).all()


def get_document(db: Session, doc_id: int) -> Document | None:
    return db.query(Document).filter(Document.id == doc_id).first()


def delete_document(db: Session, doc_id: int):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc:
        db.delete(doc)
        db.commit()


# ========== Task ==========

def create_task(db: Session, user_id: int, task: TaskCreate) -> Task:
    db_task = Task(
        user_id=user_id,
        document_id=task.document_id,
        prompt=task.prompt,
        rag_strategy=task.rag_strategy or "basic",
        status="pending"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def update_task_status(db: Session, task_id: int, status: str,
                       result_path: str = None, error_msg: str = None):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.status = status
        if result_path:
            task.result_path = result_path
        if error_msg:
            task.error_msg = error_msg
        db.commit()


def get_task(db: Session, task_id: int) -> Task | None:
    return db.query(Task).filter(Task.id == task_id).first()


def get_user_tasks(db: Session, user_id: int) -> list[Task]:
    return db.query(Task).filter(
        Task.user_id == user_id
    ).order_by(Task.created_at.desc()).all()


# ========== ChatSession ==========

def create_chat_session(db: Session, session_id: str, user_id: int,
                        document_id: int, rag_strategy: str = "basic",
                        user_preferences: str = "") -> ChatSession:
    s = ChatSession(
        session_id=session_id,
        user_id=user_id,
        document_id=document_id,
        rag_strategy=rag_strategy,
        user_preferences=user_preferences,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def get_chat_session(db: Session, session_id: str) -> ChatSession | None:
    return db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()


def update_chat_session(db: Session, session_id: str, **kwargs):
    s = get_chat_session(db, session_id)
    if not s:
        return
    for key, value in kwargs.items():
        if hasattr(s, key):
            setattr(s, key, value)
    db.commit()


def list_user_chat_sessions(db: Session, user_id: int) -> list[ChatSession]:
    return db.query(ChatSession).filter(
        ChatSession.user_id == user_id
    ).order_by(ChatSession.updated_at.desc()).all()


def delete_chat_session(db: Session, session_id: str):
    s = get_chat_session(db, session_id)
    if s:
        db.delete(s)
        db.commit()
