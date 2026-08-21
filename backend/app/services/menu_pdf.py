"""打印版菜单 PDF（v2 · 品牌化）：reportlab + 中文字体 + 末页二维码。

设计语言对齐线上「食集风」：
- 品牌渐变头（圆角渐变带 via clip + 白色圆标「食」+ 大标题 + 日期胶囊 + 统计胶囊）
- 分类头 = 品牌色胶囊 + 细线；条目 = 卡片式（圆角描边、菜名 + meta + 品牌价）
- 双栏排版，按分类分节，超长自动分页；末页右下角二维码框「扫码点餐」
字体策略：容器 wqy-microhei（TrueType）→ reportlab 内置 CID STSong-Light → Helvetica 兜底。
"""
import io
from datetime import datetime

PDF_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]

BRAND = (229 / 255, 83 / 255, 60 / 255)
BRAND_DEEP = (201 / 255, 68 / 255, 46 / 255)
BRAND_LIGHT = (240 / 255, 112 / 255, 79 / 255)
CARD_BG = (255 / 255, 252 / 255, 248 / 255)
INK = (0.16, 0.14, 0.12)
MUTED = (0.58, 0.52, 0.45)
LINE = (0.93, 0.89, 0.83)
WHITE = (1, 1, 1)

ENTRIES_PER_COLUMN = 7   # 每栏条目数上限（含分类头所需空间）
CARD_H = 46
CARD_GAP = 8
SEC_H = 30
COL_GAP = 22


def _register_cjk_font() -> str:
    """注册中文字体，返回字体名。TTF（容器 wqy）优先，其次内置 CID，最后 Helvetica。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    for path in PDF_FONT_CANDIDATES:
        try:
            pdfmetrics.registerFont(TTFont("ShiJi", path, subfontIndex=0))
            return "ShiJi"
        except Exception:
            continue
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        return "Helvetica"


def _gradient_band(c, x, y, w, h, c1, c2, r, steps=60):
    """圆角品牌渐变带：roundRect 裁剪 + 细条纹渐变。"""
    c.saveState()
    path = c.beginPath()
    path.roundRect(x, y, w, h, r)
    c.clipPath(path, stroke=0)
    for i in range(steps):
        t = i / max(steps - 1, 1)
        col = tuple(c1[k] + (c2[k] - c1[k]) * t for k in range(3))
        c.setFillColorRGB(*col)
        c.rect(x - 1, y + h - (i + 1) * h / steps, w + 2, h / steps + 0.6, stroke=0, fill=1)
    c.restoreState()
    c.setStrokeColorRGB(*LINE)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, r, stroke=1, fill=0)


def _pill(c, x, y, w, h, r, fill=None, stroke=None, alpha=None, text=None, font=None, size=9.5, tcolor=None):
    """圆角胶囊：可填充/描边，可附带文字。"""
    if fill is not None:
        c.saveState()
        if alpha is not None:
            c.setFillAlpha(alpha)
        c.setFillColorRGB(*fill)
        c.roundRect(x, y, w, h, r, stroke=0, fill=1)
        c.restoreState()
    if stroke is not None:
        c.saveState()
        c.setStrokeColorRGB(*stroke)
        c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, r, stroke=1, fill=0)
        c.restoreState()
    if text:
        c.setFillColorRGB(*(tcolor or (0, 0, 0)))
        c.setFont(font, size)
        c.drawString(x + 10, y + (h - size) / 2 - 1, text)


def build_menu_pdf(recipes, origin: str) -> bytes:
    """把上架菜品排版成 A4 品牌化 PDF，返回字节。origin 用于二维码指向 {origin}/#/order。

（分类顺序由调用方传入时已按预设顺序排好；本函数双栏均分条目。）"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.utils import ImageReader
    import qrcode

    font_name = _register_cjk_font()
    W, H = A4  # 595.27 x 841.89
    M = 36
    INNER_W = W - M * 2

    groups: dict[str, list] = {}
    for r in recipes:
        cat = r.menu_category or "其他"
        groups.setdefault(cat, []).append(r)
    items = [(cat, r) for cat, rs in groups.items() for r in rs]
    if not items:
        items = []

    qr_img = None
    try:
        qr_buf = io.BytesIO()
        qrcode.make(f"{(origin or '').rstrip('/')}/#/order", box_size=6, border=1).save(qr_buf, "PNG")
        qr_img = ImageReader(qr_buf)
    except Exception:
        qr_img = None

    now = datetime.now()
    date_text = now.strftime("%Y年%m月%d日 | %H:%M")
    total = len(recipes)
    cat_count = len(groups)

    # 分页：每页 N 条（左右两栏各 ENTRIES_PER_COLUMN）
    per_page = ENTRIES_PER_COLUMN * 2
    pages = [items[i:i + per_page] for i in range(0, len(items), per_page)] or [[]]
    n_pages = len(pages)

    col_w = (INNER_W - COL_GAP) / 2
    top_y = H - M - 116 - 52  # 品牌带(116) + 统计行(≈40) 之下
    bottom_y = 128
    entry_h = CARD_H

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)

    for page_no, chunk in enumerate(pages, start=1):
        # ---- 品牌渐变头 ----
        bh = 116
        band_y = H - M - bh
        _gradient_band(c, M, band_y, INNER_W, bh, BRAND_LIGHT, BRAND_DEEP, 18)
        # 品牌标：白圆 + 食
        cx, cy = M + 36, band_y + 62
        c.setFillColorRGB(*WHITE)
        c.circle(cx, cy, 21, stroke=0, fill=1)
        c.setFillColorRGB(*BRAND_DEEP)
        c.setFont(font_name, 20)
        c.drawCentredString(cx - 0.5, cy - 7.5, "食")
        # 标题
        c.setFillColorRGB(*WHITE)
        c.setFont(font_name, 27)
        c.drawString(cx + 34, cy + 5, "食集菜单")
        c.setFont(font_name, 10.5)
        c.drawString(cx + 35, cy - 17, "家的味道 / 用心记录每一餐")
        # 日期胶囊
        dw = 150
        _pill(c, W - M - dw, cy - 13, dw, 26, 13, fill=WHITE, alpha=0.9,
              text=date_text, font=font_name, size=10, tcolor=BRAND_DEEP)
        # 统计胶囊行
        sy = band_y - 26
        sx = M
        for s in (f"共 {total} 道菜", f"{cat_count} 个分类", "手机扫码直接点餐"):
            sw = 26 + len(s) * 10.2
            _pill(c, sx, sy, sw, 24, 12, fill=(255 / 255, 249 / 255, 243 / 255), stroke=LINE,
                  text=s, font=font_name, size=9.5, tcolor=BRAND_DEEP)
            sx += sw + 8

        # ---- 双栏条目 ----
        # 小菜单（单栏放得下）整页单栏全宽列表，阅读顺序自然；大菜单双栏均衡
        if total <= ENTRIES_PER_COLUMN:
            _draw_column(c, chunk, M, top_y, INNER_W, font_name, entry_h)
        else:
            half = len(chunk) // 2 + len(chunk) % 2
            left, right = chunk[:half], chunk[half:]
            _draw_column(c, left, M, top_y, col_w, font_name, entry_h)
            _draw_column(c, right, M + col_w + COL_GAP, top_y, col_w, font_name, entry_h)

        # ---- 页脚 ----
        c.setStrokeColorRGB(*LINE)
        c.setLineWidth(0.7)
        c.line(M, bottom_y - 10, W - M, bottom_y - 10)
        c.setFillColorRGB(*MUTED)
        c.setFont(font_name, 8)
        c.drawString(M, bottom_y - 24, "食集 | 家的味道")
        c.drawRightString(W - M - 100, bottom_y - 24, f"第 {page_no} / {n_pages} 页")

        # ---- 末页二维码 ----
        if page_no == n_pages and qr_img:
            qs = 68
            qx, qy = W - M - qs, bottom_y - qs - 4
            c.setFillColorRGB(*WHITE)
            c.setStrokeColorRGB(*LINE)
            c.setLineWidth(0.7)
            c.roundRect(qx - 9, qy - 9, qs + 18, qs + 18, 12, stroke=1, fill=1)
            c.drawImage(qr_img, qx, qy, qs, qs, mask="auto")
            c.setFillColorRGB(*BRAND_DEEP)
            c.setFont(font_name, 8)
            c.drawCentredString(qx + qs / 2, qy - 16, "扫码点餐")

        if page_no < n_pages:
            c.showPage()

    c.save()
    return buf.getvalue()


def _draw_column(c, entries, x, top_y, col_w, font_name, entry_h):
    """在 (x, top_y) 起自上而下绘制一栏：分类头胶囊 + 卡片条目。"""
    y = top_y
    last_cat = None
    for cat, r in entries:
        if cat != last_cat:
            y -= SEC_H
            cw = 24 + len(cat) * 16
            _pill(c, x, y, cw, 24, 12, fill=BRAND, text=cat, font=font_name, size=11, tcolor=WHITE)
            c.setStrokeColorRGB(*LINE)
            c.setLineWidth(0.8)
            c.line(x + cw + 10, y + 12, x + col_w, y + 12)
            y -= 12
            last_cat = cat
        y -= entry_h
        # 卡片
        c.setFillColorRGB(*CARD_BG)
        c.setStrokeColorRGB(*LINE)
        c.setLineWidth(0.7)
        c.roundRect(x, y, col_w, entry_h, 10, stroke=1, fill=1)
        # 菜名
        c.setFillColorRGB(*INK)
        c.setFont(font_name, 11.5)
        c.drawString(x + 11, y + 26, r.title[:12])
        # meta
        meta = []
        if r.cooking_time_min:
            meta.append(f"{r.cooking_time_min}分钟")
        if r.servings:
            meta.append(r.servings)
        if meta:
            c.setFillColorRGB(*MUTED)
            c.setFont(font_name, 8.5)
            c.drawString(x + 11, y + 13, " | ".join(meta))
        # 价格
        if r.menu_price is not None:
            c.setFillColorRGB(*BRAND_DEEP)
            c.setFont(font_name, 14)
            c.drawRightString(x + col_w - 11, y + 15, f"¥{r.menu_price:g}")
        else:
            c.setFillColorRGB(*MUTED)
            c.setFont(font_name, 9.5)
            c.drawRightString(x + col_w - 11, y + 16, "时价")
        y -= CARD_GAP
