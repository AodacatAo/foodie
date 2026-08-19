"""点单落单：下单快照、订单列表、删除。"""
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Order, Recipe
from ..schemas import OrderCreate, OrderListOut, OrderOut
from ..services import wechat_notify

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    """下单：把当前菜单上「已点（份数>0）」的菜快照成订单，并清空点单状态。"""
    wanted = (
        db.query(Recipe)
        .filter(Recipe.on_menu.is_(True), Recipe.menu_qty > 0)
        .order_by(Recipe.id)
        .all()
    )
    if not wanted:
        raise HTTPException(400, "购物车是空的，先点几道菜吧")

    items = [
        {
            "recipe_id": r.id,
            "title": r.title,
            "price": r.menu_price,
            "qty": r.menu_qty,
        }
        for r in wanted
    ]
    total = round(sum((i["price"] or 0) * i["qty"] for i in items), 1)

    order = Order(person=(payload.person or "").strip()[:50] or None, items=items, total=total)
    db.add(order)
    # 清空点单状态（购物车）
    for r in wanted:
        r.menu_qty = 0
        r.menu_want = False
    db.commit()
    db.refresh(order)

    # 异步微信通知（不阻塞下单响应；失败仅记日志）
    detail = "、".join(f"{i['title']}×{i['qty']}" for i in items)
    text = f"📋 新订单：{order.person or '家人'} 点了 {len(items)} 道菜 · 合计 ¥{total}\n{detail}"
    threading.Thread(target=wechat_notify.send_wechat_text, args=(text,), daemon=True).start()

    return order


@router.get("", response_model=OrderListOut)
def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Order)
    total = query.count()
    items = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": items}


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    db.delete(order)
    db.commit()
