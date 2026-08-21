"""Pydantic 模型（API 出入参 + LLM 输出校验共用）。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Ingredient(BaseModel):
    name: str
    amount: str | None = None
    note: str | None = None


class Step(BaseModel):
    order: int
    title: str | None = None
    description: str = ""
    image: str | None = None


class RecipeCreate(BaseModel):
    title: str
    author: str | None = None
    source_url: str | None = None
    note_id: str | None = None
    cover_image: str | None = None
    description: str | None = None
    cooking_time_min: int | None = None
    servings: str | None = None
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"


class RecipeUpdate(BaseModel):
    title: str | None = None
    author: str | None = None
    source_url: str | None = None
    cover_image: str | None = None
    description: str | None = None
    cooking_time_min: int | None = None
    servings: str | None = None
    ingredients: list[Ingredient] | None = None
    steps: list[Step] | None = None
    tags: list[str] | None = None
    status: str | None = None


class RecipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str | None = None
    source_url: str | None = None
    note_id: str | None = None
    cover_image: str | None = None
    video_path: str | None = None
    description: str | None = None
    cooking_time_min: int | None = None
    servings: str | None = None
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str
    on_menu: bool = False
    menu_want: bool = False
    menu_at: datetime | None = None
    menu_price: float | None = None
    menu_category: str | None = None
    created_at: datetime
    updated_at: datetime


class RecipeListOut(BaseModel):
    total: int
    items: list[RecipeOut]


# ---- LLM 提炼输出（schema 强校验）----

class RefinedIngredient(BaseModel):
    name: str
    amount: str | None = None
    note: str | None = None


class RefinedStep(BaseModel):
    order: int = 0
    title: str | None = None
    description: str = ""


class RefinedRecipe(BaseModel):
    title: str | None = None
    ingredients: list[RefinedIngredient] = Field(default_factory=list)
    steps: list[RefinedStep] = Field(default_factory=list)
    cooking_time_min: int | None = None
    servings: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


# ---- 导入任务 ----

class ManualImportIn(BaseModel):
    title: str | None = None
    text: str = Field(min_length=1)


class XhsImportIn(BaseModel):
    url: str = Field(min_length=1)


class ImportTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    url: str | None = None
    title: str | None = None
    status: str
    error: str | None = None
    recipe_id: int | None = None
    created_at: datetime
    updated_at: datetime


# ---- 模块二：餐厅库已移除（2026-08），相关 schema 一并删除 ----

# ---- 模块三：菜单点餐 ----

class OrderItemIn(BaseModel):
    recipe_id: int
    qty: int = Field(default=1, ge=1, le=99)


class OrderCreate(BaseModel):
    person: str | None = None
    # 本机购物车明细（前端 localStorage，服务端按当前菜单校验；价格以服务端为准）
    items: list[OrderItemIn] = Field(default_factory=list, max_length=50)


class OrderStatusBody(BaseModel):
    status: str  # pending / making / served


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person: str | None = None
    items: list[dict] = Field(default_factory=list)
    total: float = 0.0
    status: str = "pending"
    created_at: datetime


class OrderListOut(BaseModel):
    total: int
    items: list[OrderOut]
