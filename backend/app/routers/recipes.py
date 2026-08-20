"""菜谱 CRUD + 标签 + 菜单点餐 + 分享卡片 + 打印菜单 PDF。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Recipe
from ..schemas import RecipeCreate, RecipeListOut, RecipeOut, RecipeUpdate
from ..services import recipe_service
from ..services.menu_pdf import build_menu_pdf
from ..services.share_card import generate_share_card

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


@router.get("/menu.pdf")
def menu_pdf(origin: str = "", db: Session = Depends(get_db)):
    """打印版菜单 PDF（上架菜品，A4 双栏 + 扫码点餐二维码）。"""
    recipes = (
        db.query(Recipe)
        .filter(Recipe.on_menu.is_(True))
        .order_by(Recipe.menu_category, Recipe.id)
        .all()
    )
    if not recipes:
        raise HTTPException(404, "菜单是空的，先上架几道菜")
    pdf_bytes = build_menu_pdf(recipes, origin)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="shiji-menu.pdf"'},
    )


@router.post("/{recipe_id}/share-card")
def make_share_card(recipe_id: int, db: Session = Depends(get_db)):
    """生成菜谱分享长图，返回 {path}（media/ 下相对路径）。"""
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(404, "菜谱不存在")
    path = generate_share_card(recipe)
    if not path:
        raise HTTPException(500, "分享卡片生成失败（图片组件不可用）")
    return {"path": path}


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


# ---- 菜单/点餐模块 ----

@router.post("/{recipe_id}/menu", response_model=RecipeOut)
def put_on_menu(recipe_id: int, db: Session = Depends(get_db)):
    """上架到菜单。"""
    recipe = recipe_service.set_on_menu(db, recipe_id, True)
    if not recipe:
        raise HTTPException(404, "菜谱不存在")
    return recipe


@router.delete("/{recipe_id}/menu", response_model=RecipeOut)
def take_off_menu(recipe_id: int, db: Session = Depends(get_db)):
    """从菜单下架。"""
    recipe = recipe_service.set_on_menu(db, recipe_id, False)
    if not recipe:
        raise HTTPException(404, "菜谱不存在")
    return recipe


@router.post("/{recipe_id}/want", response_model=RecipeOut)
def toggle_want(recipe_id: int, db: Session = Depends(get_db)):
    """切换「今天想吃」勾选。"""
    recipe = recipe_service.toggle_want(db, recipe_id)
    if not recipe:
        raise HTTPException(404, "菜谱不存在")
    return recipe


class MenuPriceBody(BaseModel):
    price: float | None = None


@router.post("/{recipe_id}/menu-price", response_model=RecipeOut)
def set_menu_price(recipe_id: int, body: MenuPriceBody, db: Session = Depends(get_db)):
    """设置菜单价格（元）。price 为 null 清除价格。"""
    price = body.price
    if price is not None:
        if price < 0 or price > 99999:
            raise HTTPException(400, "价格需在 0-99999 之间")
        price = round(price * 10) / 10  # 保留 1 位小数
    recipe = recipe_service.set_menu_price(db, recipe_id, price)
    if not recipe:
        raise HTTPException(404, "菜谱不存在")
    return recipe


class MenuCategoryBody(BaseModel):
    category: str | None = None


@router.post("/{recipe_id}/menu-category", response_model=RecipeOut)
def set_menu_category(recipe_id: int, body: MenuCategoryBody, db: Session = Depends(get_db)):
    """设置菜单分类（如 热菜/凉菜/汤）。category 为 null 或空串清除。"""
    cat = (body.category or "").strip()[:50] or None
    recipe = recipe_service.set_menu_category(db, recipe_id, cat)
    if not recipe:
        raise HTTPException(404, "菜谱不存在")
    return recipe
