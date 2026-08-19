#!/usr/bin/env python3
"""回填所有餐厅的推荐菜（大众点评自动抓取真实菜名 + CDN 图片）。

用法: backend/.venv/bin/python scripts/backfill_dishes.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal, init_db
from app.models import Restaurant
from app.services.cover_service import download_cover_url, generate_dish_image, normalize_image
from app.services.dianping_client import fetch_dishes


def main() -> None:
    init_db()
    with SessionLocal() as db:
        shops = db.query(Restaurant).filter(Restaurant.source_shop_id.isnot(None)).all()
        print(f"待处理餐厅: {len(shops)} 家")
        for r in shops:
            print(f"  [{r.id}] {r.name} ...", end=" ", flush=True)
            try:
                dishes_data = fetch_dishes(r.source_shop_id)
            except Exception as e:
                print(f"❌ 抓取失败: {str(e)[:60]}")
                continue
            if not dishes_data:
                print("⚠️ 无推荐菜数据")
                continue
            dishes = []
            media_sub = ROOT / "backend" / "data" / "media" / "dishes" / str(r.id)
            for i, dish in enumerate(dishes_data[:3], start=1):
                target = media_sub / f"{i}.jpg"
                ok = download_cover_url(dish["image_url"], target)
                if ok:
                    normalize_image(target)
                else:
                    generate_dish_image(target, dish["name"])
                dishes.append({"name": dish["name"], "image": f"dishes/{r.id}/{i}.jpg"})
            r.recommended_dishes = dishes
            db.commit()
            status = []
            for i, d in enumerate(dishes, start=1):
                f = media_sub / f"{i}.jpg"
                status.append(("真图" if f.exists() and f.stat().st_size > 5000 else "生成") if f.exists() else "缺")
            print(f"✅ {[(d['name'], s) for d, s in zip(dishes, status)]}")
    print("回填完成")


if __name__ == "__main__":
    main()
