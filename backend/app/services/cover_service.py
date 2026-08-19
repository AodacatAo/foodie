"""餐厅封面：URL 下载 + 本地自动生成兜底。

自动生成：菜系主题渐变背景 + emoji + 店名，保证每个餐厅都有封面图。
"""
from pathlib import Path
import time

import httpx

from ..config import settings

# 菜系 → emoji（无匹配用默认）
CUISINE_EMOJI = {
    "川菜": "🌶️", "湘菜": "🌶️", "火锅": "🍲", "烧烤": "🍢", "日料": "🍣", "寿司": "🍣",
    "韩料": "🥘", "烤肉": "🥩", "面食": "🍜", "面馆": "🍜", "小吃": "🥟", "甜品": "🍰",
    "奶茶": "🧋", "咖啡": "☕", "西餐": "🍝", "意面": "🍝", "法餐": "🥐", "淮扬菜": "🥢",
    "粤菜": "🍤", "江浙菜": "🥢", "海鲜": "🦞", "清真": "🥙", "汉堡": "🍔", "披萨": "🍕",
    "自助": "🍱", "素食": "🥗", "早餐": "🥛", "本帮菜": "🦀", "东北菜": "🥘", "西北菜": "🍢",
}

# 菜名关键词 → emoji
DISH_EMOJI_KEYWORDS = [
    ("抓饭", "🍚"), ("饭", "🍚"), ("面", "🍜"), ("粉", "🍜"), ("饺", "🥟"), ("包", "🥟"),
    ("羊", "🍖"), ("牛", "🥩"), ("猪", "🥓"), ("鸡", "🍗"), ("鸭", "🍗"), ("鹅", "🍗"),
    ("鱼", "🐟"), ("虾", "🦐"), ("蟹", "🦀"), ("贝", "🦪"), ("海鲜", "🦞"),
    ("汤", "🍲"), ("锅", "🍲"), ("菜", "🥬"), ("蔬", "🥗"), ("沙拉", "🥗"),
    ("茶", "🍵"), ("奶茶", "🧋"), ("咖啡", "☕"), ("果汁", "🧃"), ("酒", "🍷"),
    ("甜品", "🍰"), ("蛋糕", "🍰"), ("冰淇淋", "🍦"), ("果", "🍎"), ("饼", "🥞"),
    ("烤", "🔥"), ("串", "🍢"), ("肉", "🥩"),
]


def _dish_emoji(name: str) -> str:
    for kw, emoji in DISH_EMOJI_KEYWORDS:
        if kw in name:
            return emoji
    return "🍽️"


def generate_dish_image(target: Path, name: str) -> bool:
    """生成推荐菜图片（渐变 + 菜名 emoji + 菜名）。"""
    return _generate_text_image(
        target, name, emoji=_dish_emoji(name), palette_index=hash(name) % len(PALETTE)
    )


def _generate_text_image(
    target: Path, title: str, emoji: str, palette_index: int = 0, subtitle: str | None = None
) -> bool:
    """通用文本图生成（餐厅封面 / 推荐菜共用）。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    try:
        W, H = 800, 450
        c1, c2 = PALETTE[palette_index % len(PALETTE)]
        img = Image.new("RGB", (W, H))
        for y in range(H):
            t = y / H
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            ImageDraw.Draw(img).line([(0, y), (W, y)], fill=(r, g, b))
        draw = ImageDraw.Draw(img)

        font_path = next((p for p in _FONT_CANDIDATES if Path(p).exists()), None)
        font_big = ImageFont.truetype(font_path, 52) if font_path else ImageFont.load_default()
        font_small = ImageFont.truetype(font_path, 26) if font_path else ImageFont.load_default()

        # emoji
        try:
            if Path(_EMOJI_FONT).exists():
                font_emoji = ImageFont.truetype(_EMOJI_FONT, 110)
                bbox = draw.textbbox((0, 0), emoji, font=font_emoji)
                ew, eh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text(((W - ew) / 2 - bbox[0], 60 - bbox[1]), emoji, font=font_emoji)
        except Exception:
            pass

        if subtitle:
            draw.rounded_rectangle((28, 26, 28 + len(subtitle) * 28 + 24, 66), radius=20, fill=(255, 255, 255))
            draw.text((40, 32), subtitle, font=font_small, fill=c1)

        lines = _wrap_text(title, 10)
        total_h = len(lines) * 64
        y = (H - total_h) / 2 + (70 if Path(_EMOJI_FONT).exists() else 0)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_big)
            w = bbox[2] - bbox[0]
            draw.text(((W - w) / 2 - bbox[0], y - bbox[1]), line, font=font_big, fill=(255, 255, 255))
            y += 64

        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, "JPEG", quality=88)
        return True
    except Exception:
        return False

# 主题渐变调色板（菜系哈希选择）
PALETTE = [
    ((229, 83, 60), (255, 170, 130)),   # 暖橙红
    ((216, 67, 21), (255, 171, 145)),   # 深橘
    ((198, 40, 40), (255, 138, 128)),   # 红
    ((255, 143, 0), (255, 213, 79)),    # 橙黄
    ((46, 125, 50), (139, 195, 74)),    # 绿
    ((21, 101, 192), (100, 181, 246)),  # 蓝
    ((69, 39, 160), (149, 117, 205)),   # 紫
    ((0, 105, 92), (72, 201, 176)),     # 青
]

_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
]
_EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"


def download_cover_url(url: str, target: Path) -> bool:
    """下载图片到 target（带重试）；成功返回 True。"""
    headers = {"User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )}
    for attempt in range(3):
        try:
            resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            if len(resp.content) < 1024:
                raise ValueError("内容过小")
            target.write_bytes(resp.content)
            return True
        except Exception:
            if attempt == 2:
                return False
            time.sleep(1.5 * (attempt + 1))
    return False


def normalize_image(path: Path) -> bool:
    """把任意格式图片统一转成 JPEG（webp 等 → jpg），返回是否成功。"""
    try:
        from PIL import Image

        img = Image.open(path)
        img = img.convert("RGB")
        img.save(path.with_suffix(".jpg"), "JPEG", quality=85)
        if path.suffix != ".jpg":
            path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def generate_restaurant_cover(target: Path, name: str, cuisine: str | None) -> bool:
    """本地生成封面图（渐变 + emoji + 店名）；成功返回 True。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    try:
        W, H = 800, 450
        c1, c2 = PALETTE[hash(cuisine or name) % len(PALETTE)]
        img = Image.new("RGB", (W, H))
        # 对角线性渐变
        for y in range(H):
            t = y / H
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            ImageDraw.Draw(img).line([(0, y), (W, y)], fill=(r, g, b))
        draw = ImageDraw.Draw(img)

        font_path = next((p for p in _FONT_CANDIDATES if Path(p).exists()), None)
        if font_path:
            font_big = ImageFont.truetype(font_path, 52)
            font_small = ImageFont.truetype(font_path, 26)
        else:
            font_big = font_small = ImageFont.load_default()

        # emoji（Apple Color Emoji 渲染，失败则跳过）
        emoji = CUISINE_EMOJI.get(cuisine or "", "🍽️")
        try:
            if Path(_EMOJI_FONT).exists():
                font_emoji = ImageFont.truetype(_EMOJI_FONT, 110)
                bbox = draw.textbbox((0, 0), emoji, font=font_emoji)
                ew, eh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text(((W - ew) / 2 - bbox[0], 60 - bbox[1]), emoji, font=font_emoji)
        except Exception:
            pass

        # 菜系小徽章（左上）
        if cuisine:
            draw.rounded_rectangle((28, 26, 28 + len(cuisine) * 28 + 24, 66), radius=20, fill=(255, 255, 255))
            draw.text((40, 32), cuisine, font=font_small, fill=c1)

        # 店名（居中，超长换行）
        lines = _wrap_text(name, 10)
        total_h = len(lines) * 64
        y = (H - total_h) / 2 + (70 if Path(_EMOJI_FONT).exists() else 0)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_big)
            w = bbox[2] - bbox[0]
            draw.text(((W - w) / 2 - bbox[0], y - bbox[1]), line, font=font_big, fill=(255, 255, 255))
            y += 64

        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, "JPEG", quality=88)
        return True
    except Exception:
        return False


def _wrap_text(text: str, max_chars: int) -> list[str]:
    lines = []
    for i in range(0, len(text), max_chars):
        lines.append(text[i:i + max_chars])
    return lines or [""]


def ensure_restaurant_cover(restaurant) -> None:
    """保证餐厅有封面：URL 下载 → 本地生成兜底；更新 cover_image 相对路径。"""
    if restaurant.cover_image and not restaurant.cover_image.startswith("http"):
        return  # 已是本地封面
    media_sub = settings.media_dir / "restaurants"
    target = media_sub / f"{restaurant.id}.jpg"
    ok = False
    if restaurant.cover_image and restaurant.cover_image.startswith("http"):
        ok = download_cover_url(restaurant.cover_image, target)
    if not ok:
        ok = generate_restaurant_cover(target, restaurant.name, restaurant.cuisine)
    if ok and target.exists():
        restaurant.cover_image = f"restaurants/{restaurant.id}.jpg"
