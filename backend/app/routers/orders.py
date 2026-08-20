"""点单落单：下单快照、订单列表、状态流转、删除。"""
import threading

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Order, Recipe
from ..config import settings
from ..schemas import OrderCreate, OrderListOut, OrderOut, OrderStatusBody

router = APIRouter(prefix="/api/orders", tags=["orders"])

ORDER_STATUS_FLOW = {
    "pending": "已下单",
    "making": "制作中",
    "served": "已上菜",
}


def _notify_wechat(text: str) -> None:
    """异步推送到独立 wechat-notify 服务；失败仅记日志，不阻塞业务。"""
    if not settings.wechat_notify_url:
        return
    headers = {"Authorization": f"Bearer {settings.notify_token}"} if settings.notify_token else {}

    def _run():
        try:
            with httpx.Client(timeout=15) as client:
                client.post(settings.wechat_notify_url, json={"text": text}, headers=headers)
        except Exception as e:
            print(f"[order-notify] 推送失败: {e}")

    threading.Thread(target=_run, daemon=True).start()


@router.post("", response_model=OrderOut, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    """下单：前端提交本机购物车明细，服务端按当前菜单校验、以服务端价格快照落单。

    购物车存在各设备本地（localStorage），因此不再清空服务端点单状态；
    重复提交同一道菜会合并份数，下架/不存在的菜会被拒绝。
    """
    qty_by_id: dict[int, int] = {}
    for it in payload.items:
        qty_by_id[it.recipe_id] = min(99, qty_by_id.get(it.recipe_id, 0) + it.qty)
    if not qty_by_id:
        raise HTTPException(400, "购物车是空的，先点几道菜吧")

    recipes = db.query(Recipe).filter(Recipe.id.in_(qty_by_id.keys())).all()
    by_id = {r.id: r for r in recipes}
    missing = [rid for rid in qty_by_id if rid not in by_id]
    if missing:
        raise HTTPException(400, "有菜品不存在或已被删除，请刷新菜单")
    off_menu = [r.title for r in recipes if not r.on_menu]
    if off_menu:
        raise HTTPException(400, f"已不在菜单上：{'、'.join(off_menu)}")

    items = [
        {
            "recipe_id": rid,
            "title": by_id[rid].title,
            "price": by_id[rid].menu_price,
            "qty": qty_by_id[rid],
        }
        for rid in sorted(qty_by_id)
    ]
    total = round(sum((i["price"] or 0) * i["qty"] for i in items), 1)

    order = Order(person=(payload.person or "").strip()[:50] or None, items=items, total=total)
    db.add(order)
    db.commit()
    db.refresh(order)

    detail = "、".join(f"{i['title']}×{i['qty']}" for i in items)
    _notify_wechat(f"📋 新订单：{order.person or '家人'} 点了 {len(items)} 道菜 · 合计 ¥{total}\n{detail}")

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


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    return order


@router.post("/{order_id}/status", response_model=OrderOut)
def set_order_status(order_id: int, payload: OrderStatusBody, db: Session = Depends(get_db)):
    """流转订单状态（pending → making → served）；上菜时微信通知。"""
    if payload.status not in ORDER_STATUS_FLOW:
        raise HTTPException(400, "非法状态（pending/making/served）")
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    order.status = payload.status
    db.commit()
    db.refresh(order)
    if payload.status == "served":
        detail = "、".join(f"{i['title']}×{i['qty']}" for i in (order.items or []))
        _notify_wechat(f"🔔 上菜啦！{order.person or '家人'} 点的 {len(order.items or [])} 道菜好了\n{detail}")
    return order


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    db.delete(order)
    db.commit()
