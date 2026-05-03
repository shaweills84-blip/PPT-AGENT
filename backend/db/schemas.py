from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: int
    filename: str
    chunk_count: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    document_id: int
    prompt: str
    rag_strategy: Optional[str] = "basic"


class TaskOut(BaseModel):
    id: int
    document_id: int
    prompt: str
    rag_strategy: str
    status: str
    result_path: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
