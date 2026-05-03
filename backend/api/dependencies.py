from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from db.session import get_db
from db.crud import get_user_by_email, create_user
from db.schemas import UserCreate


def get_current_user(authorization: str = Header(None),
                     db: Session = Depends(get_db)):
    """简化认证：用 email 做 Bearer token，新用户自动创建"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")

    parts = authorization.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=401, detail="认证格式错误")

    email = parts[1]
    user = get_user_by_email(db, email)

    if not user:
        user = create_user(db, UserCreate(email=email, password="demo"))

    return user
