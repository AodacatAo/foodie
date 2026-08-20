"""打印版菜单 PDF：reportlab + 中文字体 + 首页二维码（扫码直达点餐页）。

字体策略：容器 wqy-microhei（TrueType）→ reportlab 内置 CID 字体 STSong-Light
（跨平台可用，PingFang 等 CFF 字体 reportlab 不支持）→ Helvetica 兜底。
A4 双栏排版，按分类分节，超长自动分页。
"""
import io

PDF_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]

BRAND = (229 / 255, 83 / 255, 60 / 255)
INK = (0.16, 0.14, 0.12)
MUTED = (0.45, 0.42, 0.38)
LINE = (0.9, 0.87, 0.82)

ROWS_PER_COLUMN = 18  # 每栏条目数上限（留出分类头与页边距空间）


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


def build_menu_pdf(recipes, origin: str) -> bytes:
    """把上架菜品排版成 A4 PDF，返回字节。origin 用于二维码指向 {origin}/#/order。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.utils import ImageReader
    import qrcode

    font_name = _register_cjk_font()

    # 分组：按分类聚合（无分类归「其他」），保持菜单页顺序
    groups: dict[str, list] = {}
    for r in recipes:
        cat = r.menu_category or "其他"
        groups.setdefault(cat, []).append(r)

    qr_png = io.BytesIO()
    qr_target = f"{(origin or '').rstrip('/')}/#/order"
    try:
        qrcode.make(qr_target, box_size=4, border=1).save(qr_png, "PNG")
        qr_reader = ImageReader(qr_png)
    except Exception:
        qr_reader = None

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    W, H = A4  # 595.27 x 841.89
    M = 48  # 页边距

    def new_page(title: str):
        # 页头
        c.setFillColorRGB(*BRAND)
        c.setFont(font_name, 26)
        c.drawString(M, H - 58, title)
        from datetime import datetime
        c.setFillColorRGB(*MUTED)
        c.setFont(font_name, 10)
        c.drawString(M, H - 74, datetime.now().strftime("食集菜单 · %Y-%m-%d · 手机扫码直接点餐"))
        c.setStrokeColorRGB(*LINE)
        c.setLineWidth(1)
        c.line(M, H - 86, W - M, H - 86)
        # 页脚二维码 + 说明
        if qr_reader:
            c.drawImage(qr_reader, W - M - 66, 30, 66, 66, mask="auto")
            c.setFillColorRGB(*MUTED)
            c.setFont(font_name, 9)
            c.drawString(W - M - 66, 20, "扫码点餐")

    # 行布局：双栏
    col_w = (W - M * 2 - 24) / 2
    row_h = 26
    top_y = H - 112
    bottom_y = 74

    page_items = []  # 当前页待绘 (category, recipes)
    def flush_pages():
        nonlocal page_items
        for chunk_start in range(0, len(page_items), ROWS_PER_COLUMN * 2):
            new_page("🍜 食集菜单")
            chunk = page_items[chunk_start:chunk_start + ROWS_PER_COLUMN * 2]
            half = len(chunk) // 2 if len(chunk) > 1 else 1
            left, right = chunk[:half], chunk[half:]
            _draw_column(c, left, M, top_y, col_w, row_h, font_name)
            _draw_column(c, right, M + col_w + 24, top_y, col_w, row_h, font_name)
            c.showPage()
        page_items = []

    # 累积条目（按分类逐条加入，超页自动截断重排）
    for cat, items in groups.items():
        for r in items:
            page_items.append((cat, r))
            if len(page_items) == ROWS_PER_COLUMN * 2:
                flush_pages()
    if page_items:
        flush_pages()

    c.save()
    return buf.getvalue()


def _draw_column(c, entries, x, top_y, col_w, row_h, font_name):
    """在 (x, top_y) 起自上而下绘制一栏条目。"""
    y = top_y
    last_cat = None
    for cat, r in entries:
        if cat != last_cat:
            y -= row_h
            c.setFillColorRGB(*BRAND)
            c.setFont(font_name, 13)
            c.drawString(x, y, f"▍{cat}")
            y -= row_h * 0.6
            last_cat = cat
        y -= row_h
        c.setFillColorRGB(*INK)
        c.setFont(font_name, 11)
        name = r.title[:14]
        c.drawString(x + 8, y, name)
        price = f"¥{r.menu_price:g}" if r.menu_price is not None else "时价"
        c.setFillColorRGB(*BRAND)
        c.drawRightString(x + col_w - 8, y, price)
