"""菜谱服务：CRUD + FTS 全文搜索。"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import FTS_TOKENIZER
from ..models import ImportTask, Recipe
from ..schemas import RecipeCreate, RecipeUpdate


def _fts_texts(ingredients: list[dict], steps: list[dict], tags: list[str]) -> tuple[str, str, str]:
    ing_text = " ".join(
        f"{i.get('name', '')} {i.get('amount', '')} {i.get('note', '')}" for i in ingredients
    )
    step_text = " ".join(
        f"{s.get('title', '')} {s.get('description', '')}" for s in steps
    )
    tags_text = " ".join(tags)
    return ing_text, step_text, tags_text


def normalize_steps(steps: list[dict]) -> list[dict]:
    """按 order 排序并重新编号 1..n。"""
    ordered = sorted(steps, key=lambda s: (s.get("order", 0) or 0, 0))
    return [dict(s, order=i + 1) for i, s in enumerate(ordered)]


def search_recipe_ids(db: Session, q: str) -> list[int] | None:
    """FTS 检索 recipe id 列表；返回 None 表示不做过滤。"""
    q = q.strip()
    if not q:
        return None
    if FTS_TOKENIZER == "trigram":
        # trigram 天然支持中文子串匹配；<3 字符的查询匹配不到，走 LIKE 兜底
        if len(q) >= 3:
            try:
                rows = db.execute(
                    text("SELECT rowid FROM recipes_fts WHERE recipes_fts MATCH :q"),
                    {"q": f'"{q}"'},
                ).fetchall()
                return [r[0] for r in rows]
            except Exception:
                pass
    else:
        # unicode61：按单字 AND 匹配（近似子串）
        chars = " AND ".join(f'"{c}"' for c in q)
        try:
            rows = db.execute(
                text("SELECT rowid FROM recipes_fts WHERE recipes_fts MATCH :q"),
                {"q": chars},
            ).fetchall()
            if rows:
                return [r[0] for r in rows]
        except Exception:
            pass
    # LIKE 兜底（短查询 / 分词器异常）
    like = f"%{q}%"
    rows = db.execute(
        text(
            "SELECT id FROM recipes WHERE title LIKE :l OR description LIKE :l "
            "OR ingredients_text LIKE :l OR steps_text LIKE :l OR tags_text LIKE :l"
        ),
        {"l": like},
    ).fetchall()
    return [r[0] for r in rows]


def list_recipes(
    db: Session,
    q: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[Recipe]]:
    query = db.query(Recipe)
    if status:
        query = query.filter(Recipe.status == status)
    if tag:
        query = query.filter(Recipe.tags_text.like(f"%{tag}%"))
    ids = search_recipe_ids(db, q) if q else None
    if ids is not None:
        query = query.filter(Recipe.id.in_(ids))
    total = query.count()
    items = (
        query.order_by(Recipe.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, items


def get_recipe(db: Session, recipe_id: int) -> Recipe | None:
    return db.get(Recipe, recipe_id)


def create_recipe(db: Session, data: RecipeCreate) -> Recipe:
    ing_text, step_text, tags_text = _fts_texts(
        [i.model_dump() for i in data.ingredients],
        [s.model_dump() for s in data.steps],
        data.tags,
    )
    recipe = Recipe(
        title=data.title,
        author=data.author,
        source_url=data.source_url,
        note_id=data.note_id,
        cover_image=data.cover_image,
        description=data.description,
        cooking_time_min=data.cooking_time_min,
        servings=data.servings,
        ingredients=[i.model_dump() for i in data.ingredients],
        steps=normalize_steps([s.model_dump() for s in data.steps]),
        tags=data.tags,
        status=data.status,
        ingredients_text=ing_text,
        steps_text=step_text,
        tags_text=tags_text,
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def update_recipe(db: Session, recipe_id: int, data: RecipeUpdate) -> Recipe | None:
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        return None
    fields = data.model_dump(exclude_unset=True)
    steps = fields.get("steps")
    ingredients = fields.get("ingredients")
    tags = fields.get("tags")
    if ingredients is not None:
        fields["ingredients"] = [dict(i) for i in ingredients]
    if steps is not None:
        fields["steps"] = normalize_steps([dict(s) for s in steps])
    for key, value in fields.items():
        setattr(recipe, key, value)
    if ingredients is not None or steps is not None or tags is not None:
        ing_text, step_text, tags_text = _fts_texts(
            recipe.ingredients or [], recipe.steps or [], recipe.tags or []
        )
        recipe.ingredients_text = ing_text
        recipe.steps_text = step_text
        recipe.tags_text = tags_text
    db.commit()
    db.refresh(recipe)
    return recipe


def delete_recipe(db: Session, recipe_id: int) -> bool:
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        return False
    # 解除导入任务对菜谱的引用（外键约束，避免删除失败）
    db.query(ImportTask).filter(ImportTask.recipe_id == recipe_id).update(
        {ImportTask.recipe_id: None}
    )
    db.delete(recipe)
    db.commit()
    return True


def publish_recipe(db: Session, recipe_id: int) -> Recipe | None:
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        return None
    recipe.status = "published"
    db.commit()
    db.refresh(recipe)
    return recipe


def list_tags(db: Session) -> list[str]:
    rows = db.query(Recipe.tags).all()
    tags: set[str] = set()
    for (row,) in rows:
        if isinstance(row, list):
            tags.update(t for t in row if isinstance(t, str) and t.strip())
    return sorted(tags)


def set_on_menu(db: Session, recipe_id: int, on_menu: bool) -> Recipe | None:
    """上架/下架到菜单。上架时记录 menu_at。"""
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        return None
    recipe.on_menu = on_menu
    if on_menu:
        from datetime import datetime, timezone
        recipe.menu_at = datetime.now(timezone.utc)
    else:
        recipe.menu_want = False
        recipe.menu_at = None
    db.commit()
    db.refresh(recipe)
    return recipe


def toggle_want(db: Session, recipe_id: int) -> Recipe | None:
    """切换「今天想吃」勾选（仅对已上架的菜有意义）。"""
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        return None
    recipe.menu_want = not recipe.menu_want
    db.commit()
    db.refresh(recipe)
    return recipe



def set_menu_price(db: Session, recipe_id: int, price: float | None) -> Recipe | None:
    """设置/清除菜单价格。"""
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        return None
    recipe.menu_price = price
    db.commit()
    db.refresh(recipe)
    return recipe



def set_order_qty(db: Session, recipe_id: int, qty: int) -> Recipe | None:
    """设置点单份数。"""
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        return None
    recipe.menu_qty = qty
    recipe.menu_want = qty > 0  # 兼容旧字段语义
    db.commit()
    db.refresh(recipe)
    return recipe



def set_menu_category(db: Session, recipe_id: int, category: str | None) -> Recipe | None:
    """设置菜单分类。"""
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        return None
    recipe.menu_category = category
    db.commit()
    db.refresh(recipe)
    return recipe
