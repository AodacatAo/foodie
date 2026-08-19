"""大众点评抓取客户端（优化版：纯 HTTP 为主，速度 ~1-2s）。

- 搜索：Bing 纯 HTTP → 提取点评 /shop/ 链接（带内存缓存）
- 店铺信息：m.dianping.com 纯 HTTP（匿名即可：封面/店名/评分/人均/菜系/地址）
- 坐标：www.dianping.com 纯 HTTP + 登录 cookie（cookie 用 Playwright 提取并缓存 15 分钟）
- Playwright 仅作为兜底（HTTP 被拦时）
- 搜不到时自动尝试多关键词变体：繁简转换（zhconv）+ 去分店后缀
"""
import json
import os
import re
import time
import urllib.parse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from ..config import settings

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": CHROME_UA}

_search_cache: dict[str, tuple[float, list]] = {}
_cookie_cache: dict = {"ts": 0.0, "header": None}
_CACHE_TTL = 86400  # 搜索结果缓存 24 小时（引擎命中不稳定，命中后长期复用）
_COOKIE_TTL = 900  # cookie 缓存 15 分钟


@dataclass
class ShopPayload:
    shop_uuid: str
    name: str
    cover_image: str | None = None
    rating: float | None = None
    price_per_person: int | None = None
    cuisine: str | None = None
    address: str | None = None
    source_url: str | None = None
    lat: float | None = None
    lng: float | None = None


class DianpingFetchError(Exception):
    pass


def parse_shop_url(url: str) -> str:
    """从点评链接提取 shopUuid。"""
    url = url.strip()
    m = re.search(r"/shop/([A-Za-z0-9]+)", url)
    if not m:
        raise DianpingFetchError("无法识别大众点评店铺 ID（链接应包含 /shop/xxx）")
    return m.group(1)


def _http_get(url: str, cookies: str | None = None, timeout: float = 15) -> httpx.Response:
    headers = dict(_HEADERS)
    if cookies:
        headers["Cookie"] = cookies
    return httpx.get(url, headers=headers, follow_redirects=True, timeout=timeout)


def _parse_shop_html(html: str, url: str) -> ShopPayload:
    """从移动版店铺页 HTML 提取店铺信息。"""
    uuid = parse_shop_url(url)
    title_m = re.search(r"<title>([^<]+)</title>", html)
    title = title_m.group(1) if title_m else ""
    name = None
    m = re.search(r"【([^】]+)】", title)
    if m:
        name = m.group(1).strip()

    og_m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    cover = og_m.group(1) if og_m else None

    body = re.sub(r"<[^>]+>", "\n", html)
    body = re.sub(r"\s+", " ", body)

    rating = None
    rm = re.search(r"(?:★\s*){5}\s*([\d.]+)", body)
    if rm:
        rating = float(rm.group(1))

    price = None
    pm = re.search(r"¥\s*(\d+)\s*/\s*人", body)
    if pm:
        price = int(pm.group(1))

    cuisine = None
    cm = re.search(r"([\u4e00-\u9fa5/]{2,16}?菜?系?)团购", title)
    if cm:
        seg = cm.group(1).split("/")[-1].strip()
        for marker in ("地区", "城", "区", "街", "庙"):
            idx = seg.rfind(marker)
            if idx >= 0:
                seg = seg[idx + len(marker):]
                break
        cuisine = seg or None
    if not cuisine:
        cm = re.search(r"([\u4e00-\u9fa5]{2,8}菜?系?)团购", title)
        if cm:
            cuisine = cm.group(1).strip()

    address = None
    # 优先从内嵌 JSON 提取（"address":"xxx"，可能被脱敏如 1******，比 None 好）
    am = re.search(r'"address"\s*:\s*"([^"]+)"', html)
    if am:
        address = am.group(1).strip() or None
    else:
        am = re.search(r"到店\s*([\u4e00-\u9fa5][\u4e00-\u9fa5A-Za-z0-9*（）()·]{2,39})", body)
        if am:
            address = am.group(1).strip()

    return ShopPayload(
        shop_uuid=uuid,
        name=name or "未命名店铺",
        cover_image=cover,
        rating=rating,
        price_per_person=price,
        cuisine=cuisine,
        address=address,
        source_url=f"https://m.dianping.com/shop/{uuid}",
    )


def fetch_shop(url: str) -> ShopPayload:
    """抓取店铺信息（纯 HTTP，快速）；失败时 Playwright 兜底。"""
    try:
        resp = _http_get(url)
        if resp.status_code == 200 and "大众点评" in resp.text:
            return _parse_shop_html(resp.text, url)
    except Exception:
        pass
    return _fetch_shop_playwright(url)


def _fetch_shop_playwright(url: str) -> ShopPayload:
    """Playwright 兜底（HTTP 被拦时）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DianpingFetchError("未安装 playwright") from exc

    profile_dir = settings.data_dir / "dp_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                chromium_sandbox=(os.geteuid() != 0),  # 容器内以 root 运行需禁沙箱
                headless=True,
                ignore_default_args=["--enable-automation"],
                user_agent=CHROME_UA,
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
            html = page.evaluate("() => document.documentElement.outerHTML")
            context.close()
    except Exception as exc:
        raise DianpingFetchError(f"点评页面抓取失败: {exc}") from exc
    return _parse_shop_html(html or "", url)


def get_dp_cookie_header() -> str | None:
    """从登录 profile 提取 cookie（Playwright 一次性，缓存 15 分钟）。"""
    if _cookie_cache["header"] and time.time() - _cookie_cache["ts"] < _COOKIE_TTL:
        return _cookie_cache["header"]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    profile_dir = settings.data_dir / "dp_profile"
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                chromium_sandbox=(os.geteuid() != 0),  # 容器内以 root 运行需禁沙箱
                headless=True,
                ignore_default_args=["--enable-automation"],
                user_agent=CHROME_UA,
            )
            cookies = context.cookies()
            context.close()
    except Exception:
        return None
    header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    _cookie_cache.update(ts=time.time(), header=header)
    return header


_COORD_RE = re.compile(r"([3][012][.,]\d{4,})[^0-9]{0,40}(118[.,]\d{4,})")


def _fetch_coords_pc_httpx(shop_uuid: str) -> tuple[float, float] | None:
    """快速路径：PC 店铺页 + 登录 cookie（httpx）。"""
    url = f"https://www.dianping.com/shop/{shop_uuid}"
    cookie = get_dp_cookie_header()
    try:
        resp = _http_get(url, cookies=cookie)
        m = _COORD_RE.search(resp.text or "")
        if m:
            lat = float(m.group(1).replace(",", "."))
            lng = float(m.group(2).replace(",", "."))
            if 20 < lat < 45 and 100 < lng < 130:
                return lat, lng
    except Exception:
        pass
    return None


def _fetch_coords_mobile_browser(shop_uuid: str) -> tuple[float, float] | None:
    """兜底路径：移动店铺页 shop.bin 缓存（隐身浏览器 + 登录态），可绕滑块验证。"""
    url = f"https://m.dianping.com/shop/{shop_uuid}"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(settings.data_dir / "dp_profile"),
                channel="chrome",
                chromium_sandbox=(os.geteuid() != 0),  # 容器内以 root 运行需禁沙箱
                headless=True,
                ignore_default_args=["--enable-automation"],
                user_agent=CHROME_UA,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context.add_init_script(_STEALTH_JS)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(6000)
            html = page.evaluate("() => document.documentElement.outerHTML")
            context.close()
    except Exception:
        return None
    m = re.search(r'window\.__xhrCache__\s*=\s*(\{.*?\});?\s*</script>', html or "", re.S)
    if not m:
        return None
    try:
        cache = json.loads(m.group(1))
    except Exception:
        return None
    for k in cache:
        if "shop.bin" in k:
            data = cache[k].get("data") or {}
            lat, lng = data.get("lat"), data.get("lng")
            if lat and lng and 20 < float(lat) < 45 and 100 < float(lng) < 130:
                return float(lat), float(lng)
    return None


def fetch_coords(shop_uuid: str) -> tuple[float, float] | None:
    """获取店铺坐标：快速路径 PC 页，失败走移动页隐身浏览器兜底。"""
    coords = _fetch_coords_pc_httpx(shop_uuid)
    if coords:
        return coords
    return _fetch_coords_mobile_browser(shop_uuid)


_BAIDU_UA = (
    "Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)


def _extract_shop_ids(html: str) -> list[str]:
    ids: list[str] = []
    for m in re.finditer(r"dianping\.com/shop/([A-Za-z0-9]+)", html or ""):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def _search_engine_baidu(keyword: str) -> list[str]:
    """百度移动（对"頂及冒菜"这类罕见词偶有命中，时灵时不灵 → 靠重试+多引擎补）。"""
    out: list[str] = []
    for q in (quote(keyword + " 大众点评"), quote(keyword)):
        try:
            resp = httpx.get(
                "https://m.baidu.com/s?wd=" + q,
                headers={"User-Agent": _BAIDU_UA},
                follow_redirects=True,
                timeout=12,
            )
            out.extend(_extract_shop_ids(resp.text))
        except Exception:
            continue
    return list(dict.fromkeys(out))


def _search_engine_bing(keyword: str) -> list[str]:
    out: list[str] = []
    for q in (quote(keyword + " 大众点评"), quote(keyword)):
        try:
            resp = httpx.get(
                "https://www.bing.com/search?q=" + q + "&mkt=zh-CN",
                headers={"User-Agent": CHROME_UA},
                follow_redirects=True,
                timeout=12,
            )
            out.extend(_extract_shop_ids(resp.text))
        except Exception:
            continue
    return list(dict.fromkeys(out))


def _search_engine_so360(keyword: str) -> list[str]:
    """360 搜索（能返回点评链接，但可能混入噪音店 → 靠店铺页抓取后用户自选）。"""
    out: list[str] = []
    for q in (quote(keyword + " 大众点评"), quote(keyword)):
        try:
            resp = httpx.get(
                "https://www.so.com/s?q=" + q,
                headers={"User-Agent": CHROME_UA},
                follow_redirects=True,
                timeout=12,
            )
            out.extend(_extract_shop_ids(resp.text))
        except Exception:
            continue
    return list(dict.fromkeys(out))


def _search_engine_sogou(keyword: str) -> list[str]:
    out: list[str] = []
    for q in (quote(keyword + " 大众点评"), quote(keyword)):
        try:
            resp = httpx.get(
                "https://www.sogou.com/web?query=" + q,
                headers={"User-Agent": CHROME_UA},
                follow_redirects=True,
                timeout=12,
            )
            out.extend(_extract_shop_ids(resp.text))
        except Exception:
            continue
    return list(dict.fromkeys(out))


_SEARCH_ENGINES = [
    _search_engine_baidu,
    _search_engine_bing,
    _search_engine_so360,
    _search_engine_sogou,
]


def _search_engines_httpx(keyword: str) -> list[str]:
    """单关键词 × 全部快速引擎（兼容旧调用）。"""
    found: list[str] = []
    for eng in _SEARCH_ENGINES:
        try:
            found.extend(eng(keyword))
        except Exception:
            continue
    return list(dict.fromkeys(found))


def _search_bing_browser(keyword: str) -> list[str]:
    """Bing 浏览器渲染版（Playwright 兜底）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    profile_dir = settings.data_dir / "dp_profile"
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                chromium_sandbox=(os.geteuid() != 0),  # 容器内以 root 运行需禁沙箱
                headless=True,
                ignore_default_args=["--enable-automation"],
                user_agent=CHROME_UA,
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(
                "https://www.bing.com/search?q=" + quote(keyword + " 大众点评") + "&mkt=zh-CN",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(4000)
            hrefs = page.evaluate("() => [...document.querySelectorAll('a')].map(a => a.href)")
            context.close()
    except Exception:
        return []
    return _extract_shop_ids("\n".join(hrefs or []))


_DISH_SECTION_CLS = "shop-dish-pc"

_DISH_SKIP = re.compile(
    r"^(推荐菜|查看更多|网友推荐|\(\d+\)|菜单\(\d+\)|去大众点评App查看|查看菜单详情|\d+人推荐)$"
)

# 隐身脚本：隐藏自动化指纹，让 H5guard 反爬放行菜品接口
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
"""


def _upsize_pic(url: str) -> str:
    """把小尺寸图参数换成 750w 大图（URL 中 @ 可能被编码为 %40）。"""
    u = url or ""
    u = re.sub(r"@\d+w_\d+h_1e_1c_1l", "@750w_1e_1l", u)
    u = re.sub(r"%40\d+w_\d+h_1e_1c_1l", "%40750w_1e_1l", u)
    return u


def fetch_dishes(shop_uuid: str, limit: int = 3) -> list[dict]:
    """从点评推荐菜接口抓取真实菜名 + CDN 图片（隐身浏览器绕反爬）。"""
    url = f"https://m.dianping.com/shop/{shop_uuid}/dishlist"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    body = None
    for _attempt in range(2):
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(settings.data_dir / "dp_profile"),
                    channel="chrome",
                    headless=True,
                    ignore_default_args=["--enable-automation"],
                    user_agent=CHROME_UA,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context.add_init_script(_STEALTH_JS)
                page = context.pages[0] if context.pages else context.new_page()
                captured: dict = {}

                def on_response(resp):
                    if "recommenddishlistpage" in resp.url and resp.status == 200:
                        try:
                            captured["body"] = resp.json()
                        except Exception:
                            pass

                page.on("response", on_response)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(9000)
                context.close()
            body = captured.get("body")
            if body:
                break
        except Exception:
            continue
    if not body:
        return []
    data = body.get("data") or body
    tags = data.get("recommendTagList") or []
    dishes: list[dict] = []
    for t in tags:
        name = (t.get("tagName") or "").strip()
        pic = _upsize_pic(t.get("defaultPic") or "")
        if not name or not pic:
            continue
        dishes.append({"name": name, "image_url": pic, "price": t.get("price")})
        if len(dishes) >= limit:
            break
    return dishes


def _keyword_variants(keyword: str) -> list[str]:
    """生成搜索关键词变体（原词 → 去分店后缀 → 繁简转换），去重保序。

    解决两类"搜不到"：
    1. 繁简差异：店名「頂及冒菜(红庙店)」用简体「顶及冒菜」搜不到
    2. 分店后缀：输入「顶及冒菜红庙店」而点评店名带括号「頂及冒菜(红庙店)」
    """
    variants: list[str] = []

    def add(s: str) -> None:
        s = re.sub(r"\s+", "", (s or "").strip())
        if s and s not in variants:
            variants.append(s)

    add(keyword)
    # 去分店后缀：去掉括号内容（含全角/半角）与结尾"店"
    base = re.sub(r"[（(].*?[)）]", "", keyword)
    base = re.sub(r"(分店|店)$", "", base)
    add(base)
    # 渐进去尾：输入「顶及冒菜红庙店」无括号时，逐步去掉结尾分店名（红庙店/新街口店…）
    # 仅当剩余长度足够长，避免把品牌名切坏；先减 2 字（最常见分店名长度）再减 3 字
    if len(base) >= 5:
        for n in (2, 3):
            if len(base) - n >= 3:
                add(base[:-n])
    # 繁简转换（zhconv，纯 Python；未安装则跳过）
    try:
        from zhconv import convert

        for s in list(variants):
            add(convert(s, "zh-cn"))
            add(convert(s, "zh-tw"))
    except ImportError:
        pass
    return variants


def _search_variants_httpx(variants: list[str], max_attempts: int = 3) -> list[str]:
    """并行搜索变体 × 全部快速引擎，命中即停（取消剩余任务），最多重试 max_attempts 轮。

    引擎对罕见词（如「頂及冒菜」）时灵时不灵 → 重试 + 多引擎组合能显著提高命中率。
    """
    def run(round_variants: list[str]) -> list[str]:
        found: list[str] = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            pending = {
                ex.submit(eng, v): (v, eng.__name__)
                for v in round_variants
                for eng in _SEARCH_ENGINES
            }
            while pending and not found:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for fut in done:
                    try:
                        ids = fut.result()
                    except Exception:
                        continue
                    if ids:
                        found.extend(ids)
                        for f in pending:
                            f.cancel()
                        pending = set()
                        break
        return list(dict.fromkeys(found))

    for _ in range(max_attempts):
        ids = run(variants[:4])
        if ids:
            return ids
    return []


def _search_variants_bing_browser(variants: list[str]) -> list[str]:
    """兜底：Bing 浏览器渲染搜索（Playwright），只试前 2 个变体（浏览器慢）。"""
    for v in variants[:2]:
        ids = _search_bing_browser(v)
        if ids:
            return ids
    return []


# 大众点评城市 ID（搜索 URL 必须带城市，否则默认杭州等错城市）
# 南京=5；如需其他城市在「城市 ID 对照表」里查（北京1 上海2 杭州3 广州4 南京5 深圳8 成都13 苏州14）
_DP_CITY_ID = "5"


def _search_dianping_site(variants: list[str]) -> list[str]:
    """点评站内搜索（登录态 + PC 搜索页渲染）：最可靠，搜索引擎没收录的店也能命中。

    罕见店（如「頂及冒菜红庙店」）搜索引擎经常搜不到点评店铺页，但站内搜索
    直接查点评数据库，命中率高得多。城市默认南京（_DP_CITY_ID）。
    Playwright 启动带超时兜底，任何失败返回空（不影响后续引擎）。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    profile_dir = settings.data_dir / "dp_profile"
    found: list[str] = []
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                chromium_sandbox=(os.geteuid() != 0),
                headless=True,
                timeout=45000,  # 启动超时兜底，避免拖慢整个搜索
            )
            try:
                for kw in variants[:3]:  # 最多试 3 个变体（原词/去分店/简体）
                    page = context.new_page()
                    try:
                        url = (
                            f"https://www.dianping.com/search/keyword/{_DP_CITY_ID}/0_"
                            + quote(kw)
                        )
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(3500)  # 等结果列表渲染
                        html = page.content()
                        ids = re.findall(r'href="[^"]*?/shop/([A-Za-z0-9]+)"', html)
                        ids += re.findall(
                            r"(?:https?:)?//(?:www\.)?dianping\.com/shop/([A-Za-z0-9]+)", html
                        )
                        ids = list(dict.fromkeys(ids))
                        if ids:
                            found.extend(ids)
                            break
                    except Exception:
                        continue
                    finally:
                        page.close()
            finally:
                context.close()
    except Exception:
        return []
    return list(dict.fromkeys(found))


def _filter_relevant_shops(
    shops: list[ShopPayload], variants: list[str]
) -> list[ShopPayload]:
    """过滤噪音候选：店名不含任一 ≥2 字变体的视为无关（如搜「頂及冒菜」命中「顶栊粤菜」）。

    全部无关时返回空列表（调用方报"没找到"，避免把错店展示给用户）。
    """
    keys = [v for v in variants if len(v) >= 2]
    relevant = [s for s in shops if s.name and any(v in s.name for v in keys)]
    return relevant


def _rank_shops(shops: list[ShopPayload], variants: list[str]) -> list[ShopPayload]:
    """把店名与搜索词匹配度高的店铺排前面（含繁简/子串匹配），噪音店沉底。"""
    keys = [v for v in variants if len(v) >= 2]

    def score(s: ShopPayload) -> int:
        name = s.name or ""
        return max((len(v) for v in keys if v in name), default=0)

    return sorted(shops, key=score, reverse=True)


# 持久化搜索缓存：引擎命中不稳定，把成功映射存盘，重启不丢（24h 内秒出）
_search_cache_file = settings.data_dir / "search_cache.json"


def _load_search_cache() -> dict:
    try:
        data = json.loads(_search_cache_file.read_text())
        return {k: (v[0], [ShopPayload(**s) for s in v[1]]) for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}


def _save_search_cache() -> None:
    try:
        payload = {
            k: (ts, [s.__dict__ for s in shops])
            for k, (ts, shops) in _search_cache.items()
        }
        _search_cache_file.write_text(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


# 已知店铺映射：搜索引擎搜不到、但已人工确认存在的店（店名关键词 → 点评 shop id）。
# 搜索时优先命中（含变体匹配），解决「頂及冒菜(红庙店)」这类繁简混合/冷门店的搜不到问题。
# 之后遇到其它搜不到的店，可在此追加：如 "某某店": "12345678"。
_KNOWN_SHOPS: dict[str, str] = {
    "頂及冒菜": "780141514",
    "顶及冒菜": "780141514",
}


def _known_shop_ids(variants: list[str]) -> list[str]:
    """按变体查已知店铺映射，返回命中的 shop id（保持映射定义顺序，去重）。"""
    return list(
        dict.fromkeys(
            sid for kw, sid in _KNOWN_SHOPS.items() if any(v == kw for v in variants)
        )
    )


def search_shops(keyword: str, limit: int = 3) -> list[ShopPayload]:
    """按店名搜索点评店铺：多变体多引擎找链接 → 抓取信息+坐标（结果缓存 24 小时）。

    命中链路：已知映射 → 多引擎(百度/Bing/360/搜狗) × 多关键词变体(原词/去分店/繁简) × 重试。
    """
    keyword = keyword.strip()
    now = time.time()
    cached = _search_cache.get(keyword)
    if not (cached and now - cached[0] < _CACHE_TTL):
        # 内存未命中 → 查持久化缓存
        persisted = _load_search_cache().get(keyword)
        if persisted and now - persisted[0] < _CACHE_TTL:
            _search_cache[keyword] = persisted
            cached = persisted
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    variants = _keyword_variants(keyword)
    shop_ids = _known_shop_ids(variants)
    if not shop_ids:
        # 点评站内搜索最可靠（搜索引擎常漏收录店的店铺页），优先
        shop_ids = _search_dianping_site(variants)
    if not shop_ids:
        shop_ids = _search_variants_httpx(variants)
    if not shop_ids:
        shop_ids = _search_variants_bing_browser(variants)
    if not shop_ids:
        raise DianpingFetchError(
            f"没找到「{keyword}」的大众点评店铺页。\n"
            "已自动尝试多种写法（简体/繁体/去掉分店名）和多个搜索源仍无结果，可能是：\n"
            "① 店名含繁体字（如「頂及冒菜」vs「顶及冒菜」），可手动切换繁简再试\n"
            "② 这家店未被点评收录，或点评搜索对无人气小店收录不全。\n"
            "可以直接粘贴该店的大众点评链接到下方「从链接导入」，或手动录入。"
        )

    shops: list[ShopPayload] = []
    # 多抓几个候选给噪音过滤留余地
    for sid in shop_ids[: limit * 2]:
        try:
            shops.append(fetch_shop(f"https://m.dianping.com/shop/{sid}"))
        except DianpingFetchError:
            continue
    if not shops:
        raise DianpingFetchError("找到店铺页但抓取信息失败，请稍后重试")

    shops = _filter_relevant_shops(shops, variants)
    if not shops:
        raise DianpingFetchError(
            "找到候选店铺但店名与关键词不匹配（可能是搜索词太宽泛），请换更准确的名字重试"
        )
    shops = _rank_shops(shops, variants)
    # 只对最终展示的店铺补坐标（减少慢速 playwright 调用）
    for s in shops[:limit]:
        try:
            coords = fetch_coords(s.shop_uuid)
            if coords:
                s.lat, s.lng = coords
        except Exception:
            continue

    _search_cache[keyword] = (now, shops)
    _save_search_cache()
    return shops
