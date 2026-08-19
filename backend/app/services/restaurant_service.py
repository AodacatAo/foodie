"""餐厅服务：CRUD + FTS 搜索 + 就餐记录 + 常用位置。"""
import re
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import FTS_TOKENIZER
from ..models import Restaurant, UserLocation, VisitLog
from ..schemas import RestaurantCreate, RestaurantUpdate, UserLocationCreate, VisitLogCreate
from .cover_service import ensure_restaurant_cover


def _fts_texts(name: str, cuisine: str | None, address: str | None, tags: list[str]) -> tuple[str, str, str, str]:
    return name, cuisine or "", address or "", " ".join(tags)


def _search_variants(q: str) -> list[str]:
    """生成搜索变体：原词 + 去分店后缀 + 繁简转换（解决繁简混合店名如「頂及冒菜(红庙店)」）。"""
    variants: list[str] = []

    def add(s: str) -> None:
        s = (s or "").strip()
        if s and s not in variants:
            variants.append(s)

    add(q)
    base = re.sub(r"[（(].*?[)）]", "", q)
    base = re.sub(r"(分店|店)$", "", base)
    add(base)
    # 渐进去尾：无括号输入时逐步去掉结尾分店名（红庙店/新街口店…）
    if len(base) >= 5:
        for n in (3, 2):
            if len(base) - n >= 3:
                add(base[:-n])
    try:
        from zhconv import convert

        for s in list(variants):
            add(convert(s, "zh-cn"))
            add(convert(s, "zh-tw"))
    except ImportError:
        pass
    return variants


def search_restaurant_ids(db: Session, q: str) -> list[int] | None:
    """FTS 检索餐厅 id 列表；返回 None 表示不过滤。

    策略：FTS 短语匹配 →（空结果或异常）→ LIKE 兜底（含繁简/去括号变体）。
    """
    q = q.strip()
    if not q:
        return None
    variants = _search_variants(q)
    if FTS_TOKENIZER == "trigram" and len(q) >= 3:
        try:
            rows = db.execute(
                text("SELECT rowid FROM restaurants_fts WHERE restaurants_fts MATCH :q"),
                {"q": f'"{q}"'},
            ).fetchall()
            if rows:  # 空结果不直接返回，继续走 LIKE 兜底（否则带括号/繁简差异的店名会漏）
                return [r[0] for r in rows]
        except Exception:
            pass
    if FTS_TOKENIZER != "trigram":
        chars = " AND ".join(f'"{c}"' for c in q)
        try:
            rows = db.execute(
                text("SELECT rowid FROM restaurants_fts WHERE restaurants_fts MATCH :q"),
                {"q": chars},
            ).fetchall()
            if rows:
                return [r[0] for r in rows]
        except Exception:
            pass
    clauses = []
    params: dict[str, str] = {}
    for i, v in enumerate(variants):
        like = f"%{v}%"
        clauses.append(
            f"(name LIKE :l{i} OR cuisine LIKE :l{i} OR address LIKE :l{i} OR tags_text LIKE :l{i})"
        )
        params[f"l{i}"] = like
    rows = db.execute(
        text("SELECT id FROM restaurants WHERE " + " OR ".join(clauses)), params
    ).fetchall()
    return [r[0] for r in rows]


def list_restaurants(
    db: Session,
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 500,
) -> tuple[int, list[Restaurant]]:
    query = db.query(Restaurant)
    if status:
        query = query.filter(Restaurant.status == status)
    ids = search_restaurant_ids(db, q) if q else None
    if ids is not None:
        query = query.filter(Restaurant.id.in_(ids))
    total = query.count()
    items = (
        query.order_by(Restaurant.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, items


def get_restaurant(db: Session, restaurant_id: int) -> Restaurant | None:
    return db.get(Restaurant, restaurant_id)


def create_restaurant(db: Session, data: RestaurantCreate) -> Restaurant:
    name, cuisine_t, address_t, tags_t = _fts_texts(data.name, data.cuisine, data.address, data.tags)
    restaurant = Restaurant(
        name=data.name,
        cuisine=data.cuisine,
        address=data.address,
        lat=data.lat,
        lng=data.lng,
        price_per_person=data.price_per_person,
        rating=data.rating,
        cover_image=data.cover_image,
        source_url=data.source_url,
        source_shop_id=data.source_shop_id,
        source_platform=data.source_platform,
        tags=data.tags,
        recommended_dishes=[dict(d) for d in data.recommended_dishes],
        status=data.status,
        name_text=name,
        cuisine_text=cuisine_t,
        address_text=address_t,
        tags_text=tags_t,
    )
    db.add(restaurant)
    db.flush()  # 拿到 id 用于封面文件名
    ensure_restaurant_cover(restaurant)  # URL 下载或本地生成兜底
    db.commit()
    db.refresh(restaurant)
    return restaurant


def update_restaurant(db: Session, restaurant_id: int, data: RestaurantUpdate) -> Restaurant | None:
    restaurant = db.get(Restaurant, restaurant_id)
    if not restaurant:
        return None
    fields = data.model_dump(exclude_unset=True)
    if "recommended_dishes" in fields and fields["recommended_dishes"] is not None:
        fields["recommended_dishes"] = [dict(d) for d in fields["recommended_dishes"]]
    for key, value in fields.items():
        setattr(restaurant, key, value)
    name, cuisine_t, address_t, tags_t = _fts_texts(
        restaurant.name, restaurant.cuisine, restaurant.address, restaurant.tags or []
    )
    restaurant.name_text = name
    restaurant.cuisine_text = cuisine_t
    restaurant.address_text = address_t
    restaurant.tags_text = tags_t
    if "cover_image" in fields:
        ensure_restaurant_cover(restaurant)
    db.commit()
    db.refresh(restaurant)
    return restaurant


def delete_restaurant(db: Session, restaurant_id: int) -> bool:
    restaurant = db.get(Restaurant, restaurant_id)
    if not restaurant:
        return False
    db.delete(restaurant)  # visit_logs 由 FK ON DELETE CASCADE 清理
    db.commit()
    return True


def publish_restaurant(db: Session, restaurant_id: int) -> Restaurant | None:
    restaurant = db.get(Restaurant, restaurant_id)
    if not restaurant:
        return None
    restaurant.status = "published"
    db.commit()
    db.refresh(restaurant)
    return restaurant


def set_my_rating(db: Session, restaurant_id: int, my_rating: float | None) -> Restaurant | None:
    restaurant = db.get(Restaurant, restaurant_id)
    if not restaurant:
        return None
    restaurant.my_rating = round(my_rating, 1) if my_rating is not None else None
    db.commit()
    db.refresh(restaurant)
    return restaurant


def list_tags(db: Session) -> list[str]:
    rows = db.query(Restaurant.tags).all()
    tags: set[str] = set()
    for (row,) in rows:
        if isinstance(row, list):
            tags.update(t for t in row if isinstance(t, str) and t.strip())
    return sorted(tags)


# ---------- 就餐记录 ----------

def add_visit(db: Session, restaurant_id: int, data: VisitLogCreate) -> VisitLog:
    restaurant = db.get(Restaurant, restaurant_id)
    if not restaurant:
        raise ValueError("餐厅不存在")
    visited_at = data.visited_at or datetime.now(timezone.utc)
    visit = VisitLog(
        restaurant_id=restaurant_id,
        visited_at=visited_at,
        note=data.note,
        photos=data.photos or [],
        rating=data.rating,
        cost_per_person=data.cost_per_person,
    )
    db.add(visit)
    # 冗余聚合同步更新
    restaurant.visit_count = (restaurant.visit_count or 0) + 1
    restaurant.last_visited_at = visited_at
    db.commit()
    db.refresh(visit)
    return visit


def list_visits(db: Session, restaurant_id: int) -> list[VisitLog]:
    return (
        db.query(VisitLog)
        .filter(VisitLog.restaurant_id == restaurant_id)
        .order_by(VisitLog.visited_at.desc(), VisitLog.id.desc())
        .all()
    )


def update_visit(db: Session, visit_id: int, data: VisitLogCreate) -> VisitLog | None:
    """编辑就餐记录（日期/备注/照片）。"""
    visit = db.get(VisitLog, visit_id)
    if not visit:
        return None
    if data.visited_at is not None:
        visit.visited_at = data.visited_at
    if data.note is not None:
        visit.note = data.note
    if data.photos is not None:
        visit.photos = data.photos
    db.commit()
    db.refresh(visit)
    return visit


def delete_visit(db: Session, visit_id: int) -> bool:
    visit = db.get(VisitLog, visit_id)
    if not visit:
        return False
    restaurant = db.get(Restaurant, visit.restaurant_id)
    db.delete(visit)
    if restaurant:
        restaurant.visit_count = max(0, (restaurant.visit_count or 1) - 1)
        # last_visited_at 回退到最近一条记录（如有）
        last = (
            db.query(VisitLog)
            .filter(VisitLog.restaurant_id == restaurant.id)
            .order_by(VisitLog.visited_at.desc())
            .first()
        )
        restaurant.last_visited_at = last.visited_at if last else None
    db.commit()
    return True


# ---------- 常用位置 ----------

def list_locations(db: Session) -> list[UserLocation]:
    return db.query(UserLocation).order_by(UserLocation.id).all()


def create_location(db: Session, data: UserLocationCreate) -> UserLocation:
    loc = UserLocation(name=data.name, lat=data.lat, lng=data.lng)
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


def delete_location(db: Session, location_id: int) -> bool:
    loc = db.get(UserLocation, location_id)
    if not loc:
        return False
    db.delete(loc)
    db.commit()
    return True
