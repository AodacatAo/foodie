"""餐厅路由：CRUD + 搜索 + 就餐记录。"""
import shutil
import time

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..schemas import (
    RatingUpdate,
    RestaurantCreate,
    RestaurantListOut,
    RestaurantOut,
    RestaurantUpdate,
    VisitLogCreate,
    VisitLogOut,
)
from ..services import restaurant_service
from ..services.amap_client import AmapError, Poi, search_pois
from ..services.cover_service import download_cover_url, generate_dish_image, normalize_image
from ..services.dianping_client import (
    DianpingFetchError,
    ShopPayload,
    fetch_dishes,
    fetch_shop,
    search_shops,
)

router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])


@router.get("", response_model=RestaurantListOut)
def list_restaurants(
    q: str | None = Query(default=None, description="关键词（FTS 全文搜索）"),
    status: str | None = Query(default="published", description="draft/published，留空为全部"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    total, items = restaurant_service.list_restaurants(
        db, q=q, status=status, page=page, page_size=page_size
    )
    return {"total": total, "items": items}


@router.get("/tags", response_model=list[str])
def list_tags(db: Session = Depends(get_db)):
    return restaurant_service.list_tags(db)


@router.post("/search-shops", response_model=list[ShopPayload])
def search_restaurant_shops(payload: dict, db: Session = Depends(get_db)):
    """按店名搜索餐厅（Bing → 大众点评 → 信息+封面+坐标）。"""
    keyword = (payload.get("keyword") or "").strip()
    if not keyword:
        raise HTTPException(400, "请输入店名关键词")
    try:
        return search_shops(keyword)
    except DianpingFetchError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/search-poi", response_model=list[Poi])
def search_poi(payload: dict, db: Session = Depends(get_db)):
    """按店名搜索 POI（高德）：名称/地址/坐标/分类。"""
    keyword = (payload.get("keyword") or "").strip()
    city = (payload.get("city") or "南京").strip()
    if not keyword:
        raise HTTPException(400, "请输入店名关键词")
    try:
        return search_pois(keyword, city)
    except AmapError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sync-info", response_model=ShopPayload)
def sync_dianping_info(payload: dict, db: Session = Depends(get_db)):
    """从大众点评链接抓取店铺信息（用于录入预填）。"""
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "请提供大众点评链接")
    try:
        return fetch_shop(url)
    except DianpingFetchError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{restaurant_id}", response_model=RestaurantOut)
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db)):
    restaurant = restaurant_service.get_restaurant(db, restaurant_id)
    if not restaurant:
        raise HTTPException(404, "餐厅不存在")
    return restaurant


@router.post("", response_model=RestaurantOut, status_code=201)
def create_restaurant(payload: RestaurantCreate, db: Session = Depends(get_db)):
    return restaurant_service.create_restaurant(db, payload)


@router.put("/{restaurant_id}", response_model=RestaurantOut)
def update_restaurant(restaurant_id: int, payload: RestaurantUpdate, db: Session = Depends(get_db)):
    restaurant = restaurant_service.update_restaurant(db, restaurant_id, payload)
    if not restaurant:
        raise HTTPException(404, "餐厅不存在")
    return restaurant


@router.post("/{restaurant_id}/publish", response_model=RestaurantOut)
def publish_restaurant(restaurant_id: int, db: Session = Depends(get_db)):
    restaurant = restaurant_service.publish_restaurant(db, restaurant_id)
    if not restaurant:
        raise HTTPException(404, "餐厅不存在")
    return restaurant


@router.post("/{restaurant_id}/sync-dishes", response_model=RestaurantOut)
def sync_recommended_dishes(restaurant_id: int, db: Session = Depends(get_db)):
    """从大众点评自动抓取推荐菜（菜名 + 生成图片），写入餐厅。"""
    restaurant = restaurant_service.get_restaurant(db, restaurant_id)
    if not restaurant:
        raise HTTPException(404, "餐厅不存在")
    if not restaurant.source_shop_id:
        raise HTTPException(400, "该餐厅没有大众点评店铺 ID，无法同步推荐菜")
    names = fetch_dishes(restaurant.source_shop_id)
    if not names:
        raise HTTPException(404, "未获取到推荐菜（点评页面可能未收录）")
    dishes = []
    media_sub = settings.media_dir / "dishes" / str(restaurant_id)
    # 清理旧推荐菜图片（内容可换，新同步生成带时间戳的新文件名/新 URL）
    shutil.rmtree(media_sub, ignore_errors=True)
    for i, dish in enumerate(names[:3], start=1):
        target = media_sub / f"{i}-{int(time.time())}.jpg"
        ok = download_cover_url(dish["image_url"], target)  # 真实 CDN 图片
        if ok:
            normalize_image(target)  # webp 等转标准 jpg
        else:
            generate_dish_image(target, dish["name"])  # 兜底生成
        dishes.append({"name": dish["name"], "image": f"dishes/{restaurant_id}/{target.name}"})
    restaurant.recommended_dishes = dishes
    db.commit()
    db.refresh(restaurant)
    return restaurant


@router.post("/{restaurant_id}/rating", response_model=RestaurantOut)
def set_my_rating(restaurant_id: int, payload: RatingUpdate, db: Session = Depends(get_db)):
    """快速打分（0-5，0.1 精度）。"""
    restaurant = restaurant_service.set_my_rating(db, restaurant_id, payload.my_rating)
    if not restaurant:
        raise HTTPException(404, "餐厅不存在")
    return restaurant


@router.post("/upload", status_code=201)
async def upload_image(file: UploadFile = File(...)):
    """通用图片上传 → media/uploads/{uuid}{ext}，返回相对路径。"""
    import uuid

    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        raise HTTPException(400, "仅支持 jpg/png/webp/gif 图片")
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 15MB")
    upload_dir = settings.media_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(content)
    return {"path": f"uploads/{path.name}"}


@router.delete("/{restaurant_id}", status_code=204)
def delete_restaurant(restaurant_id: int, db: Session = Depends(get_db)):
    if not restaurant_service.delete_restaurant(db, restaurant_id):
        raise HTTPException(404, "餐厅不存在")


# ---------- 就餐记录 ----------

@router.get("/{restaurant_id}/visits", response_model=list[VisitLogOut])
def list_visits(restaurant_id: int, db: Session = Depends(get_db)):
    if not restaurant_service.get_restaurant(db, restaurant_id):
        raise HTTPException(404, "餐厅不存在")
    return restaurant_service.list_visits(db, restaurant_id)


@router.post("/{restaurant_id}/visits", response_model=VisitLogOut, status_code=201)
def add_visit(restaurant_id: int, payload: VisitLogCreate, db: Session = Depends(get_db)):
    try:
        return restaurant_service.add_visit(db, restaurant_id, payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/visits/{visit_id}", response_model=VisitLogOut)
def update_visit(visit_id: int, payload: VisitLogCreate, db: Session = Depends(get_db)):
    """编辑就餐记录（日期/备注/照片）。"""
    visit = restaurant_service.update_visit(db, visit_id, payload)
    if not visit:
        raise HTTPException(404, "记录不存在")
    return visit


@router.delete("/visits/{visit_id}", status_code=204)
def delete_visit(visit_id: int, db: Session = Depends(get_db)):
    if not restaurant_service.delete_visit(db, visit_id):
        raise HTTPException(404, "记录不存在")
