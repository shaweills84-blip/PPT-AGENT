import os
import shutil
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import User
from db.schemas import DocumentOut
from db.crud import create_document, update_document_status, get_user_documents, delete_document as crud_delete_document
from api.dependencies import get_current_user
from core.config import settings
from rag.retriever import get_retriever

router = APIRouter(prefix="/documents", tags=["文档管理"])


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed = {".pdf", ".docx", ".doc", ".txt"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"不支持的文件类型: {ext}，可选: {allowed}")

    stored_filename = f"{user.id}_{file.filename}"
    stored_path = os.path.join(settings.upload_dir, stored_filename)
    with open(stored_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = create_document(db, user.id, file.filename, stored_path)

    # 同步索引，生产环境建议改后台任务
    try:
        retriever = get_retriever(settings.default_rag_strategy)
        chunk_count = retriever.index_document(doc.id, stored_path)
        update_document_status(db, doc.id, "ready", chunk_count)
        doc.status = "ready"
        doc.chunk_count = chunk_count
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        with open("error.log", "w") as f:
            f.write(error_detail)
        update_document_status(db, doc.id, "failed")
        raise HTTPException(500, f"文档索引失败: {type(e).__name__}: {str(e)}\n详情见 backend/error.log")

    return doc


@router.get("/", response_model=list[DocumentOut])
async def list_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_documents(db, user.id)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from db.crud import get_document
    doc = get_document(db, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(404, "文档不存在")

    try:
        retriever = get_retriever(settings.default_rag_strategy)
        retriever.delete_document(doc_id)
    except Exception:
        pass

    if os.path.exists(doc.stored_path):
        os.remove(doc.stored_path)

    crud_delete_document(db, doc_id)
    return {"message": "删除成功"}
