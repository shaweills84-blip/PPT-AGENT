import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import User
from db.schemas import TaskOut
from db.crud import get_task, get_user_tasks
from api.dependencies import get_current_user

router = APIRouter(tags=["任务管理"])


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task_status(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = get_task(db, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("/tasks/{task_id}/download")
async def download_pptx(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = get_task(db, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    if task.status != "done" or not task.result_path:
        raise HTTPException(400, "任务未完成或生成失败")
    if not os.path.exists(task.result_path):
        raise HTTPException(404, "文件不存在")

    return FileResponse(
        task.result_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"ppt_{task_id}.pptx",
    )
