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


# ---- 模块二：餐厅库 ----

class DishItem(BaseModel):
    name: str
    image: str | None = None


class RestaurantCreate(BaseModel):
    name: str
    cuisine: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    price_per_person: int | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    my_rating: float | None = Field(default=None, ge=0, le=5)
    cover_image: str | None = None
    source_url: str | None = None
    source_shop_id: str | None = None
    source_platform: str | None = None
    tags: list[str] = Field(default_factory=list)
    recommended_dishes: list[DishItem] = Field(default_factory=list)
    status: str = "published"


class RestaurantUpdate(BaseModel):
    name: str | None = None
    cuisine: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    price_per_person: int | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    my_rating: float | None = Field(default=None, ge=0, le=5)
    cover_image: str | None = None
    source_url: str | None = None
    source_shop_id: str | None = None
    source_platform: str | None = None
    tags: list[str] | None = None
    recommended_dishes: list[DishItem] | None = None
    status: str | None = None


class RatingUpdate(BaseModel):
    my_rating: float | None = Field(default=None, ge=0, le=5)


class RestaurantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cuisine: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    price_per_person: int | None = None
    rating: float | None = None
    my_rating: float | None = None
    cover_image: str | None = None
    source_url: str | None = None
    source_shop_id: str | None = None
    source_platform: str | None = None
    tags: list[str] = Field(default_factory=list)
    recommended_dishes: list[DishItem] = Field(default_factory=list)
    status: str
    visit_count: int = 0
    last_visited_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RestaurantListOut(BaseModel):
    total: int
    items: list[RestaurantOut]


class VisitLogCreate(BaseModel):
    visited_at: datetime | None = None  # 就餐日期，默认现在
    note: str | None = None
    photos: list[str] = Field(default_factory=list)  # 已上传图片的相对路径
    rating: int | None = Field(default=None, ge=1, le=5)  # 兼容字段
    cost_per_person: int | None = Field(default=None, ge=0)


class VisitLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int
    visited_at: datetime
    note: str | None = None
    photos: list[str] = Field(default_factory=list)
    rating: int | None = None
    cost_per_person: int | None = None
    created_at: datetime


class UserLocationCreate(BaseModel):
    name: str
    lat: float
    lng: float


class UserLocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    lat: float
    lng: float
    created_at: datetime
