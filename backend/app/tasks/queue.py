"""进程内 asyncio 后台任务队列（v1 不引入 Celery/Redis）。"""
import asyncio

from ..database import SessionLocal
from ..models import ImportTask
from ..services.import_pipeline import pipeline

_queue: asyncio.Queue[int] = asyncio.Queue()
_worker_task: asyncio.Task | None = None


def enqueue(task_id: int) -> None:
    _queue.put_nowait(task_id)


async def _worker() -> None:
    while True:
        task_id = await _queue.get()
        try:
            await pipeline.run(task_id)
        except Exception:
            pass  # pipeline.run 已兜底，任务状态不会卡死
        finally:
            _queue.task_done()


async def start_worker() -> None:
    global _worker_task
    # 重启后清理上次未完成任务
    with SessionLocal() as db:
        stale = (
            db.query(ImportTask)
            .filter(ImportTask.status.in_(["pending", "running"]))
            .all()
        )
        for t in stale:
            t.status = "failed"
            t.error = "服务重启中断，请重新导入"
        db.commit()
    _worker_task = asyncio.create_task(_worker(), name="import-worker")


async def stop_worker() -> None:
    if _worker_task:
        _worker_task.cancel()
