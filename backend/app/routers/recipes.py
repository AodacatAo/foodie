"""菜谱 CRUD + 标签。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import RecipeCreate, RecipeListOut, RecipeOut, RecipeUpdate
from ..services import recipe_service

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


@router.get("", response_model=RecipeListOut)
def list_recipes(
    q: str | None = Query(default=None, description="关键词（FTS 全文搜索）"),
    tag: str | None = None,
    status: str | None = Query(default="published", description="draft/published，留空为全部"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    total, items = recipe_service.list_recipes(
        db, q=q, tag=tag, status=status, page=page, page_size=page_size
    )
    return {"total": total, "items": items}


@router.get("/tags", response_model=list[str])
def list_tags(db: Session = Depends(get_db)):
    return recipe_service.list_tags(db)


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = recipe_service.get_recipe(db, recipe_id)
    if not recipe:
        raise HTTPException(404, "菜谱不存在")
    return recipe


@router.post("", response_model=RecipeOut, status_code=201)
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db)):
    return recipe_service.create_recipe(db, payload)


@router.put("/{recipe_id}", response_model=RecipeOut)
def update_recipe(recipe_id: int, payload: RecipeUpdate, db: Session = Depends(get_db)):
    recipe = recipe_service.update_recipe(db, recipe_id, payload)
    if not recipe:
        raise HTTPException(404, "菜谱不存在")
    return recipe


@router.post("/{recipe_id}/publish", response_model=RecipeOut)
def publish_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = recipe_service.publish_recipe(db, recipe_id)
    if not recipe:
        raise HTTPException(404, "菜谱不存在")
    return recipe


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)):
    if not recipe_service.delete_recipe(db, recipe_id):
        raise HTTPException(404, "菜谱不存在")
