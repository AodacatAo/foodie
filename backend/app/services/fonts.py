"""中文字体与 emoji 字体选择（PIL 合成图片用，分享卡片等）。

本机 macOS：PingFang / Apple Color Emoji；容器（NAS 镜像）：wqy-microhei / Noto Color Emoji。
"""
from pathlib import Path

_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # 容器（NAS 镜像）中文字体
]
_EMOJI_FONT_CANDIDATES = [
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",  # 容器（NAS 镜像）emoji 字体
]


def pick_font(size: int):
    """选择中文字体：本机 PingFang → 容器 wqy-microhei → PIL 默认。"""
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    font_path = next((p for p in _FONT_CANDIDATES if Path(p).exists()), None)
    return ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()


def pick_emoji_font_path() -> str | None:
    """返回可用的 emoji 字体路径（无则 None）。"""
    return next((p for p in _EMOJI_FONT_CANDIDATES if Path(p).exists()), None)
