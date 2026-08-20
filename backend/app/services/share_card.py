"""菜谱分享卡片：PIL 合成竖向长图（标题/封面/食材/步骤+配图/页脚）。

输出 media/share/{recipe_id}-{时间戳}.png（新内容=新 URL，沿用 immutable 缓存策略），
同菜谱旧卡片自动清理。中文渲染依赖 cover_service.pick_font（本机 PingFang / 容器 wqy-microhei）。
"""
import time

from ..config import settings
from .cover_service import pick_font

CARD_W = 750
PAD = 40
BRAND = (229, 83, 60)
BRAND_SOFT = (255, 244, 239)
INK = (47, 42, 36)
MUTED = (148, 136, 122)
LINE = (238, 230, 220)
BG = (255, 253, 248)
WHITE = (255, 255, 255)


def _wrap(text: str, font, max_w: float) -> list[str]:
    """按实际像素宽度换行（保留显式换行符）。"""
    lines: list[str] = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if font.getlength(cur + ch) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    lines.append(cur)
    return lines


def _section_bar(draw, y: int, title: str, font, inner: int) -> None:
    draw.text((PAD, y), title, font=font, fill=BRAND)
    tw = font.getlength(title)
    draw.line((PAD + tw + 14, y + int(font.size * 0.62), PAD + inner, y + int(font.size * 0.62)),
              fill=LINE, width=2)


def generate_share_card(recipe) -> str | None:
    """生成分享长图，返回 media/ 下相对路径；失败返回 None。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    f_title = pick_font(46)
    f_meta = pick_font(23)
    f_section = pick_font(30)
    f_body = pick_font(25)
    f_note = pick_font(21)
    f_foot = pick_font(19)
    if not all((f_title, f_meta, f_section, f_body, f_note, f_foot)):
        return None

    inner = CARD_W - PAD * 2

    # ---- 素材准备 ----
    cover = None
    if recipe.cover_image:
        p = settings.media_dir / recipe.cover_image
        if p.exists():
            try:
                img = Image.open(p)
                img.load()
                cover = img.convert("RGB")
            except Exception:
                cover = None
    step_imgs: dict[str, object] = {}
    for s in recipe.steps or []:
        if s.get("image"):
            p = settings.media_dir / s["image"]
            if p.exists():
                try:
                    img = Image.open(p)
                    img.load()
                    step_imgs[s["image"]] = img.convert("RGB")
                except Exception:
                    pass

    title_lines = _wrap(recipe.title or "未命名菜谱", f_title, inner)
    meta_parts = []
    if recipe.cooking_time_min:
        meta_parts.append(f"⏱ {recipe.cooking_time_min} 分钟")
    if recipe.servings:
        meta_parts.append(f"🍽 {recipe.servings}")
    if recipe.tags:
        meta_parts.append(" · ".join(recipe.tags))
    meta_text = "   ".join(meta_parts) or None

    # ---- 块列表 (height, draw_fn)；draw_fn 在 canvas 存在后才被调用 ----
    GAP = 18
    blocks: list[tuple[int, object]] = []

    header_h = 34 + len(title_lines) * 58 + (36 if meta_text else 0) + 22

    def draw_header(draw, y):
        draw.text((PAD, y), "🍜 食集 · 家宴菜谱", font=f_foot, fill=MUTED)
        ty = y + 34
        for line in title_lines:
            draw.text((PAD, ty), line, font=f_title, fill=INK)
            ty += 58
        if meta_text:
            draw.text((PAD, ty), meta_text, font=f_meta, fill=MUTED)
            ty += 36
        draw.line((PAD, ty + 10, PAD + inner, ty + 10), fill=LINE, width=2)

    blocks.append((header_h, draw_header))

    if cover:
        w, h = cover.size
        cover_h = int(inner * h / w)
        cover_resized = cover.resize((inner, cover_h), Image.LANCZOS)

        def draw_cover(_draw, y):
            canvas.paste(cover_resized, (PAD, y))

        blocks.append((cover_h, draw_cover))

    # 食材块
    ing_rows = []
    for ing in recipe.ingredients or []:
        name = ing.get("name") or ""
        amount = ing.get("amount") or ""
        note = ing.get("note") or ""
        head = f"{name}  {amount}".strip()
        lines = _wrap(head, f_body, inner - 56)
        note_lines = _wrap(note, f_note, inner - 56) if note else []
        ing_rows.append((lines, note_lines))
    ing_h = 46 + sum(len(l) * 36 + (len(n) * 30 if n else 0) + 10 for l, n in ing_rows) if ing_rows else 0

    def draw_ingredients(draw, y):
        yy = y
        _section_bar(draw, yy, "食材", f_section, inner)
        yy += 48
        for lines, note_lines in ing_rows:
            for line in lines:
                draw.ellipse((PAD + 2, yy + 12, PAD + 12, yy + 22), fill=BRAND_SOFT, outline=BRAND)
                draw.text((PAD + 26, yy), line, font=f_body, fill=INK)
                yy += 36
            for nline in note_lines:
                draw.text((PAD + 26, yy), nline, font=f_note, fill=MUTED)
                yy += 30
            yy += 10

    if ing_rows:
        blocks.append((ing_h, draw_ingredients))

    # 步骤块
    step_rows = []
    for i, s in enumerate(recipe.steps or [], start=1):
        desc_lines = _wrap(s.get("description") or "", f_body, inner - 64)
        step_rows.append((i, desc_lines, step_imgs.get(s.get("image"))))
    steps_h = 0
    if step_rows:
        steps_h = 46
        for _i, desc_lines, img in step_rows:
            steps_h += max(len(desc_lines) * 38, 40) + 8
            if img:
                w, h = img.size
                steps_h += int((inner - 64) * h / w) + 14

    def draw_steps(draw, y):
        yy = y
        _section_bar(draw, yy, "步骤", f_section, inner)
        yy += 50
        for i, desc_lines, img in step_rows:
            draw.ellipse((PAD, yy + 2, PAD + 36, yy + 38), fill=BRAND)
            draw.text((PAD + 11, yy + 4), str(i), font=f_body, fill=WHITE)
            ly = yy
            for line in desc_lines:
                draw.text((PAD + 52, ly), line, font=f_body, fill=INK)
                ly += 38
            yy = max(ly + 8, yy + 46)
            if img:
                w, h = img.size
                ih = int((inner - 64) * h / w)
                resized = img.resize((inner - 64, ih), Image.LANCZOS)
                canvas.paste(resized, (PAD + 52, yy))
                yy += ih + 14

    if step_rows:
        blocks.append((steps_h, draw_steps))

    # 页脚
    foot_h = 92

    def draw_footer(draw, y):
        draw.line((PAD, y, PAD + inner, y), fill=LINE, width=2)
        draw.text((PAD, y + 26), "来自「食集」· 记录家的味道", font=f_body, fill=BRAND)
        date_text = time.strftime("%Y-%m-%d")
        draw.text((PAD + inner - f_foot.getlength(date_text), y + 32), date_text, font=f_foot, fill=MUTED)

    blocks.append((foot_h, draw_footer))

    # ---- 合成 ----
    total_h = sum(h + GAP for h, _fn in blocks) + PAD
    canvas = Image.new("RGB", (CARD_W, total_h), BG)
    draw = ImageDraw.Draw(canvas)
    y = 0
    for h, fn in blocks:
        fn(draw, y)
        y += h + GAP

    share_dir = settings.media_dir / "share"
    share_dir.mkdir(parents=True, exist_ok=True)
    target = share_dir / f"{recipe.id}-{int(time.time())}.png"
    canvas.save(target, "PNG", optimize=True)
    for old in share_dir.glob(f"{recipe.id}-*.png"):
        if old != target:
            old.unlink(missing_ok=True)
    return f"share/{target.name}"
