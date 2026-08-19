#!/usr/bin/env python3
"""风控冷却自动重试：每 10 分钟探测一次，解除后立即抓取并走完整导入管线。

用法: backend/.venv/bin/python scripts/retry_import.py "<小红书链接>"
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

NOTE_URL = sys.argv[1] if len(sys.argv) > 1 else ""
INTERVAL_SEC = 600  # 10 分钟
MAX_ATTEMPTS = 7  # 最多等 ~70 分钟


def fetch_once(url: str) -> bool:
    from app.services.xhs_client import make_fetcher

    try:
        payload = make_fetcher().fetch_note(url)
        print(f"  ✅ 抓取成功: {payload.title}（作者 {payload.author}，{len(payload.image_urls)} 图）")
        return True
    except Exception as exc:
        msg = str(exc)[:120]
        print(f"  ⏳ 仍被拦截: {msg}")
        return False


def run_pipeline(url: str) -> None:
    from app.database import SessionLocal, init_db
    from app.models import ImportTask
    from app.services.import_pipeline import pipeline

    init_db()
    with SessionLocal() as db:
        task = ImportTask(kind="xhs_url", url=url, status="pending")
        db.add(task)
        db.commit()
        db.refresh(task)
        tid = task.id

    import asyncio

    asyncio.run(pipeline.run(tid))

    with SessionLocal() as db:
        from app.models import Recipe

        t = db.get(ImportTask, tid)
        print(f"  任务 #{tid} 状态: {t.status}")
        if t.status == "success" and t.recipe_id:
            r = db.get(Recipe, t.recipe_id)
            print(f"  📝 草稿已生成: 「{r.title}」 食材 {len(r.ingredients)} 项 / 步骤 {len(r.steps)} 步")
            print(f"  前端打开: http://127.0.0.1:8080/#/recipe/{r.id} （确认后发布）")
        else:
            print(f"  失败原因: {t.error}")


def main() -> None:
    if not NOTE_URL:
        print("用法: retry_import.py <小红书链接>")
        sys.exit(1)
    print(f"目标链接: {NOTE_URL[:120]}")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[第 {attempt}/{MAX_ATTEMPTS} 次尝试] {time.strftime('%H:%M:%S')}")
        if fetch_once(NOTE_URL):
            run_pipeline(NOTE_URL)
            print("完成 ✅")
            return
        if attempt < MAX_ATTEMPTS:
            print(f"  等待 {INTERVAL_SEC // 60} 分钟后重试…")
            time.sleep(INTERVAL_SEC)
    print("超时未解除风控，可稍后手动重跑本脚本，或换网络后重试")


if __name__ == "__main__":
    main()
