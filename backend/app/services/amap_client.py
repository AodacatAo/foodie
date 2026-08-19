"""高德地图 POI 搜索客户端（Web 服务 API）。

用途：按店名搜索餐厅 → 名称/地址/坐标/分类（解决"输入店名自动加店"）。
配置：.env 中 AMAP_KEY=你的高德 Web服务 Key。
"""
import json
from dataclasses import dataclass, field

import httpx

from ..config import settings

AMAP_SEARCH_URL = "https://restapi.amap.com/v3/place/text"
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"


@dataclass
class Poi:
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    category: str | None = None  # 如 餐饮服务;中餐厅
    poi_id: str | None = None


class AmapError(Exception):
    pass


def _get_amap_key() -> str:
    key = settings.amap_key
    if not key:
        raise AmapError("未配置 AMAP_KEY（在 .env 中填写高德 Web服务 Key）")
    return key


def search_pois(keyword: str, city: str = "南京", limit: int = 10) -> list[Poi]:
    """按关键词搜索 POI（高德 place/text 接口）。"""
    key = _get_amap_key()
    resp = httpx.get(
        AMAP_SEARCH_URL,
        params={
            "key": key,
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "offset": limit,
            "page": 1,
            "extensions": "base",
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("status") != "1":
        raise AmapError(f"高德搜索失败: {data.get('info', '未知错误')}")
    pois: list[Poi] = []
    for item in data.get("pois") or []:
        loc = (item.get("location") or "").split(",")  # "lng,lat"
        try:
            lng, lat = float(loc[0]), float(loc[1])
        except (IndexError, ValueError):
            lng = lat = None
        pois.append(
            Poi(
                name=item.get("name") or "",
                address=item.get("address") or None,
                lat=lat,
                lng=lng,
                category=item.get("type") or None,
                poi_id=item.get("id") or None,
            )
        )
    return pois


def geocode_address(address: str, city: str = "南京") -> tuple[float, float] | None:
    """地址转坐标（手动录入时可选填经纬度）。"""
    key = _get_amap_key()
    resp = httpx.get(
        AMAP_GEOCODE_URL,
        params={"key": key, "address": address, "city": city},
        timeout=15,
    )
    data = resp.json()
    if data.get("status") != "1":
        return None
    geocodes = data.get("geocodes") or []
    if not geocodes:
        return None
    loc = (geocodes[0].get("location") or "").split(",")
    try:
        return float(loc[1]), float(loc[0])  # (lat, lng)
    except (IndexError, ValueError):
        return None
