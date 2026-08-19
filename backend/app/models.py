"""ORM 模型。"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
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


# ---------- 模块二：餐厅库 ----------

class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    cuisine: Mapped[str | None] = mapped_column(String(100))  # 菜系
    address: Mapped[str | None] = mapped_column(String(300))
    lat: Mapped[float | None] = mapped_column()  # 纬度
    lng: Mapped[float | None] = mapped_column()  # 经度
    price_per_person: Mapped[int | None] = mapped_column()  # 人均（元）
    rating: Mapped[float | None] = mapped_column()  # 平台评分（0-5）
    my_rating: Mapped[float | None] = mapped_column()  # 我的评分（0-5，0.1 精度）
    cover_image: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_shop_id: Mapped[str | None] = mapped_column(String(64))
    source_platform: Mapped[str | None] = mapped_column(String(20))  # dianping/meituan/manual
    tags: Mapped[list] = mapped_column(JSON, default=list)
    recommended_dishes: Mapped[list] = mapped_column(JSON, default=list)  # [{name, image}]
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft/published
    visit_count: Mapped[int] = mapped_column(default=0)  # 冗余聚合
    last_visited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # FTS 冗余文本列（触发器自动同步）
    name_text: Mapped[str] = mapped_column(Text, default="")
    cuisine_text: Mapped[str] = mapped_column(Text, default="")
    address_text: Mapped[str] = mapped_column(Text, default="")
    tags_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    visits = relationship(
        "VisitLog", back_populates="restaurant", cascade="all, delete-orphan", passive_deletes=True
    )


class VisitLog(Base):
    __tablename__ = "visit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)  # 就餐日期
    note: Mapped[str | None] = mapped_column(Text)  # 备注
    photos: Mapped[list] = mapped_column(JSON, default=list)  # 照片相对路径列表
    rating: Mapped[int | None] = mapped_column()  # 个人打分 1-5（保留兼容）
    cost_per_person: Mapped[int | None] = mapped_column()  # 实付人均（保留兼容）
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    restaurant = relationship("Restaurant", back_populates="visits")


class UserLocation(Base):
    __tablename__ = "user_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))  # 家 / 公司
    lat: Mapped[float] = mapped_column()
    lng: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
