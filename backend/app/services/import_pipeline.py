"""导入管线：单向数据流，任何一步失败有明确断点。

manual 类型：原始文本 → LLM 提炼（可选）→ 规则提取兜底 → 草稿入库
xhs_url 类型：链接 → Playwright 抓取 → 图片下载 → OCR → LLM → 草稿入库
"""
import asyncio
import json
import re

from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import ImportTask, Recipe
from ..schemas import RefinedRecipe
from . import llm_service

_STEP_RE = re.compile(
    r"^(?:\d{1,2}[.、)．]|[一二三四五六七八九十百]+[、.．]|"
    r"步骤\s*[一二三四五六七八九十\d]+|Step\s*\d+|"
    r"[①②③④⑤⑥⑦⑧⑨⑩]+)"
)
_IMG_MARK_RE = re.compile(r"\[图(\d+)\]")


def _split_steps(text: str) -> list[dict]:
    """规则提取：按步骤标记分行；无标记时按空行分段。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    steps: list[dict] = []
    cur: dict | None = None
    for line in lines:
        if _STEP_RE.match(line):
            cur = {"order": len(steps) + 1, "title": None, "description": line}
            steps.append(cur)
        elif cur:
            cur["description"] += "\n" + line
    if not steps:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        steps = [
            {"order": i + 1, "title": None, "description": p}
            for i, p in enumerate(paragraphs)
        ]
    return steps


def _naive_extract(text: str, title_hint: str | None) -> dict:
    steps = _split_steps(text)
    return {
        "title": title_hint or (text.strip().splitlines()[0][:40] if text.strip() else None),
        "ingredients": [],
        "steps": steps,
        "tags": [],
        "cooking_time_min": None,
        "servings": None,
    }


def _save_llm_output(task_id: int, refined: RefinedRecipe | None) -> str | None:
    if refined is None:
        return None
    path = settings.snapshot_dir / f"llm_task_{task_id}.json"
    path.write_text(json.dumps(refined.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _map_step_images(steps: list[dict], note_id: str) -> list[dict]:
    """把 LLM 标注的 [图N] 映射为步骤配图（media/<note_id>/N.jpg）。"""
    media_sub = settings.media_dir / note_id
    out: list[dict] = []
    for s in steps:
        desc = s.get("description") or ""
        nums = [int(n) for n in _IMG_MARK_RE.findall(desc)]
        desc_clean = _IMG_MARK_RE.sub("", desc).strip()
        s["description"] = desc_clean
        for n in nums:
            img = media_sub / f"{n}.jpg"
            if img.exists():
                s["image"] = f"{note_id}/{n}.jpg"
                break
        out.append(s)
    return out


class ImportPipeline:
    async def run(self, task_id: int) -> None:
        with SessionLocal() as db:
            task = db.get(ImportTask, task_id)
            if not task or task.status not in ("pending", "running"):
                return
            task.status = "running"
            db.commit()
        try:
            if task.kind == "manual":
                await self._run_manual(task)
            elif task.kind == "xhs_url":
                await self._run_xhs(task)
            else:
                raise ValueError(f"未知导入类型: {task.kind}")
        except Exception as exc:  # noqa: BLE001 —— 管线兜底，任务转 failed
            with SessionLocal() as db:
                t = db.get(ImportTask, task_id)
                if t:
                    t.status = "failed"
                    t.error = f"{type(exc).__name__}: {exc}"
                    db.commit()

    # ---------- manual ----------

    async def _run_manual(self, task: ImportTask) -> None:
        text = task.source_text or ""
        refined = await llm_service.refine_recipe(text)
        llm_path = _save_llm_output(task.id, refined)

        if refined:
            data = {
                "title": refined.title or task.title or "未命名菜谱",
                "ingredients": [dict(i) for i in refined.ingredients],
                "steps": [dict(s) for s in refined.steps],
                "tags": refined.tags,
                "cooking_time_min": refined.cooking_time_min,
                "servings": refined.servings,
            }
            description = (refined.notes or "").strip() or None
        else:
            data = _naive_extract(text, task.title)
            description = None

        with SessionLocal() as db:
            t = db.get(ImportTask, task.id)
            if not t:
                return
            recipe = Recipe(
                title=data["title"] or "未命名菜谱",
                description=description or (text[:3000] if text else None),
                ingredients=data["ingredients"],
                steps=data["steps"],
                tags=data["tags"],
                cooking_time_min=data.get("cooking_time_min"),
                servings=data.get("servings"),
                status="draft",
                ingredients_text=" ".join(
                    f"{i.get('name', '')} {i.get('amount', '')} {i.get('note', '')}"
                    for i in data["ingredients"]
                ),
                steps_text=" ".join(
                    f"{s.get('title', '')} {s.get('description', '')}" for s in data["steps"]
                ),
                tags_text=" ".join(data["tags"]),
            )
            db.add(recipe)
            db.flush()
            t.recipe_id = recipe.id
            t.status = "success"
            t.llm_output_path = llm_path
            db.commit()

    # ---------- xhs_url ----------

    async def _run_xhs(self, task: ImportTask) -> None:
        import httpx

        from .ocr_service import recognize_images
        from .xhs_client import make_fetcher

        url = task.url or ""
        fetcher = make_fetcher()

        # 1) 抓取（同步 Playwright，放入线程避免阻塞事件循环）
        payload = await asyncio.to_thread(fetcher.fetch_note, url)
        is_video = bool(payload.video_url)

        # 2) 快照落盘
        snapshot_path = settings.snapshot_dir / f"note_{payload.note_id}.json"
        snapshot_path.write_text(
            json.dumps(payload.raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 3) 下载图片 → media/<note_id>/N.jpg
        media_sub = settings.media_dir / payload.note_id
        media_sub.mkdir(parents=True, exist_ok=True)
        image_paths: list = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            )
        }
        async with httpx.AsyncClient(
            timeout=30, headers=headers, follow_redirects=True
        ) as client:
            for i, img_url in enumerate(payload.image_urls[:30], start=1):
                target = media_sub / f"{i}.jpg"
                try:
                    resp = await client.get(img_url)
                    resp.raise_for_status()
                    target.write_bytes(resp.content)
                    image_paths.append(target)
                except Exception:
                    continue

        # 4) OCR（图文菜谱核心；视频笔记跳过——步骤来自语音转写，封面图不参与步骤配图）
        ocr_results = recognize_images(image_paths) if (image_paths and not is_video) else []
        ocr_text = "\n".join(
            f"[图片{i['index'] + 1}]\n{i['text']}" for i in ocr_results if i["text"]
        )
        ocr_path = None
        if ocr_text:
            ocr_path = settings.snapshot_dir / f"ocr_{task.id}.txt"
            ocr_path.write_text(ocr_text, encoding="utf-8")

        # 4.5) 视频笔记：下载视频 → 语音转写
        transcript_path = None
        transcript_text = ""
        video_rel_path = None
        if payload.video_url:
            transcript_text, video_rel_path = await self._download_and_transcribe(task, payload)
            if transcript_text:
                transcript_path = settings.snapshot_dir / f"transcript_{task.id}.txt"
                transcript_path.write_text(transcript_text, encoding="utf-8")

        # 4.6) 封面（视频笔记：视频封面图）
        cover = None
        if payload.video_url and payload.cover_image and not image_paths:
            cover_local = await self._download_cover(task, payload)
            if cover_local:
                cover = cover_local

        # 5) LLM 提炼（正文 + OCR 文本 + 视频转写）
        combined = payload.desc or ""
        if ocr_text:
            combined += "\n\n【图片OCR识别内容，图片顺序即步骤顺序】\n" + ocr_text
        if transcript_text:
            combined += "\n\n【视频语音转写内容（视频里口述的做法）】\n" + transcript_text
        refined = await llm_service.refine_recipe(combined or payload.title)
        llm_path = _save_llm_output(task.id, refined)

        if refined:
            steps = [dict(s) for s in refined.steps]
            if not is_video:
                steps = _map_step_images(steps, payload.note_id)
            data = {
                "title": refined.title or payload.title or "未命名菜谱",
                "ingredients": [dict(i) for i in refined.ingredients],
                "steps": steps,
                "tags": refined.tags,
                "cooking_time_min": refined.cooking_time_min,
                "servings": refined.servings,
            }
            description = (refined.notes or "").strip() or None
        else:
            steps = _split_steps(combined)
            data = {
                "title": payload.title or "未命名菜谱",
                "ingredients": [],
                "steps": steps,
                "tags": [],
                "cooking_time_min": None,
                "servings": None,
            }
            description = None

        if not cover:
            cover = f"{payload.note_id}/1.jpg" if image_paths else None

        with SessionLocal() as db:
            t = db.get(ImportTask, task.id)
            if not t:
                return
            recipe = Recipe(
                title=data["title"],
                author=payload.author or None,
                source_url=url,
                note_id=payload.note_id,
                cover_image=cover,
                description=description or (payload.desc[:3000] if payload.desc else None),
                ingredients=data["ingredients"],
                steps=data["steps"],
                tags=data["tags"],
                cooking_time_min=data.get("cooking_time_min"),
                servings=data.get("servings"),
                video_path=video_rel_path,
                status="draft",
                ingredients_text=" ".join(
                    f"{i.get('name', '')} {i.get('amount', '')} {i.get('note', '')}"
                    for i in data["ingredients"]
                ),
                steps_text=" ".join(
                    f"{s.get('title', '')} {s.get('description', '')}" for s in data["steps"]
                ),
                tags_text=" ".join(data["tags"]),
            )
            db.add(recipe)
            db.flush()
            t.recipe_id = recipe.id
            t.status = "success"
            t.snapshot_path = str(snapshot_path)
            t.ocr_text_path = str(ocr_path) if ocr_path else None
            t.llm_output_path = llm_path
            t.transcript_path = str(transcript_path) if transcript_path else None
            db.commit()

    # ---------- 视频辅助 ----------

    async def _download_and_transcribe(
        self, task: ImportTask, payload
    ) -> tuple[str, str | None]:
        """下载视频到 media/<note_id>/video.mp4，转写语音；返回 (转写文本, 视频相对路径)。"""
        import httpx

        from .transcribe_service import transcribe_video

        media_sub = settings.media_dir / payload.note_id
        media_sub.mkdir(parents=True, exist_ok=True)
        video_path = media_sub / "video.mp4"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Referer": f"https://www.xiaohongshu.com/explore/{payload.note_id}",
        }

        # 下载（httpx 失败时降级为 Playwright 浏览器会话下载）
        content = None
        try:
            async with httpx.AsyncClient(
                timeout=60, headers=headers, follow_redirects=True
            ) as client:
                resp = await client.get(payload.video_url)
                resp.raise_for_status()
                content = resp.content
        except Exception:
            content = await self._download_via_browser(payload)
        if not content:
            return "", None
        video_path.write_bytes(content)

        # 转写（耗时操作放入线程）
        transcript = await asyncio.to_thread(transcribe_video, video_path)
        return transcript, f"{payload.note_id}/video.mp4"

    async def _download_via_browser(self, payload) -> bytes | None:
        """用登录态浏览器会话下载视频（绕过防盗链/签名限制）。"""
        try:
            from playwright.sync_api import sync_playwright

            from .xhs_client import CHROME_UA
        except ImportError:
            return None

        def _run() -> bytes | None:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(settings.data_dir / "xhs_profile"),
                    channel="chrome",
                    headless=True,
                    ignore_default_args=["--enable-automation"],
                    user_agent=CHROME_UA,
                )
                resp = context.request.get(
                    payload.video_url,
                    headers={"Referer": f"https://www.xiaohongshu.com/explore/{payload.note_id}"},
                    timeout=60000,
                )
                context.close()
                if resp.ok:
                    return resp.body()
                return None

        return await asyncio.to_thread(_run)

    async def _download_cover(self, task: ImportTask, payload) -> str | None:
        """下载视频封面 → media/<note_id>/cover.jpg；返回相对路径或 None。"""
        import httpx

        media_sub = settings.media_dir / payload.note_id
        media_sub.mkdir(parents=True, exist_ok=True)
        target = media_sub / "cover.jpg"
        headers = {"User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        )}
        try:
            async with httpx.AsyncClient(
                timeout=30, headers=headers, follow_redirects=True
            ) as client:
                resp = await client.get(payload.cover_image)
                resp.raise_for_status()
                target.write_bytes(resp.content)
            return f"{payload.note_id}/cover.jpg"
        except Exception:
            return None


pipeline = ImportPipeline()
