"""导入接口：手动录入（M1 可用）+ 小红书链接（M2）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ImportTask
from ..schemas import ImportTaskOut, ManualImportIn, XhsImportIn
from ..tasks.queue import enqueue

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("/manual", response_model=ImportTaskOut, status_code=201)
def submit_manual(payload: ManualImportIn, db: Session = Depends(get_db)):
    """手动粘贴笔记内容（M1 兜底通道），走同一提炼管线。"""
    if not payload.text.strip():
        raise HTTPException(400, "笔记内容不能为空")
    task = ImportTask(
        kind="manual",
        title=payload.title,
        source_text=payload.text.strip(),
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    enqueue(task.id)
    return task


@router.post("", response_model=ImportTaskOut, status_code=201)
def submit_url(payload: XhsImportIn, db: Session = Depends(get_db)):
    """小红书链接导入：创建任务并进入抓取管线（Playwright → OCR → LLM → 草稿）。"""
    url = payload.url.strip()
    if "xiaohongshu.com" not in url and "xhslink" not in url:
        raise HTTPException(400, "请粘贴小红书链接（xiaohongshu.com 或 xhslink.com/xhslink.cn）")
    task = ImportTask(kind="xhs_url", url=url, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    enqueue(task.id)
    return task


@router.get("/{task_id}", response_model=ImportTaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(ImportTask, task_id)
    if not task:
        raise HTTPException(404, "导入任务不存在")
    return task
