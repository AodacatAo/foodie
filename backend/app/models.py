"""ORM 模型。"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(500))
    note_id: Mapped[str | None] = mapped_column(String(64), index=True)
    cover_image: Mapped[str | None] = mapped_column(String(500))  # 相对 media_dir 的路径
    video_path: Mapped[str | None] = mapped_column(String(500))  # 视频文件相对路径（视频笔记）
    description: Mapped[str | None] = mapped_column(Text)
    cooking_time_min: Mapped[int | None] = mapped_column()
    servings: Mapped[str | None] = mapped_column(String(50))
    ingredients: Mapped[list] = mapped_column(JSON, default=list)  # [{name, amount, note}]
    steps: Mapped[list] = mapped_column(JSON, default=list)  # [{order, title, description, image}]
    tags: Mapped[list] = mapped_column(JSON, default=list)  # [str]
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft/published
    # 菜单/点餐模块
    on_menu: Mapped[bool] = mapped_column(Boolean, default=False)  # 已上架到菜单
    menu_want: Mapped[bool] = mapped_column(Boolean, default=False)  # 今天想吃（勾选置顶）
    menu_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 上架时间
    menu_price: Mapped[float | None] = mapped_column()  # 菜单价格（元）
    menu_qty: Mapped[int] = mapped_column(default=0)  # 已废弃（购物车改为前端本地存储），列保留兼容旧数据
    menu_category: Mapped[str | None] = mapped_column(String(50))  # 菜单分类（热菜/凉菜/汤…）
    # FTS 冗余文本列（触发器自动同步）
    ingredients_text: Mapped[str] = mapped_column(Text, default="")
    steps_text: Mapped[str] = mapped_column(Text, default="")
    tags_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class ImportTask(Base):
    __tablename__ = "import_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # manual | xhs_url
    url: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending / running / success / failed / needs_review
    source_text: Mapped[str | None] = mapped_column(Text)  # 原始文本（正文 / OCR 拼接）
    snapshot_path: Mapped[str | None] = mapped_column(String(500))
    ocr_text_path: Mapped[str | None] = mapped_column(String(500))
    llm_output_path: Mapped[str | None] = mapped_column(String(500))
    transcript_path: Mapped[str | None] = mapped_column(String(500))
    error: Mapped[str | None] = mapped_column(Text)
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    recipe = relationship("Recipe", foreign_keys=[recipe_id])


# ---------- 模块二：餐厅库已移除（2026-08）----------
# Restaurant / VisitLog / UserLocation 模型已随模块删除；线上旧表数据保留不动。
# ---------- 模块三：菜单点餐 ----------

class Order(Base):
    """点单落单记录：下单时快照菜单点单明细。"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    person: Mapped[str | None] = mapped_column(String(50))  # 下单人（可选）
    items: Mapped[list] = mapped_column(JSON, default=list)  # [{recipe_id, title, price, qty}]
    total: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending/making/served
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
