"""FTS 搜索接口。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import RecipeListOut
from ..services import recipe_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=RecipeListOut)
def search(
    q: str = Query(min_length=1),
    status: str | None = Query(default="published"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    total, items = recipe_service.list_recipes(
        db, q=q, status=status, page=page, page_size=page_size
    )
    return {"total": total, "items": items}
