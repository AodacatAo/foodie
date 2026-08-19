"""FastAPI 入口：挂载路由、静态资源、后台任务。"""
import hmac
import ipaddress
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import PROJECT_ROOT, settings
from .database import init_db
from .routers import imports, locations, orders, recipes, restaurants, search
from .tasks.queue import start_worker, stop_worker

AUTH_COOKIE = "foodie_token"
_PUBLIC_API = ("/api/login", "/api/health")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    await start_worker()
    yield
    await stop_worker()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


class LoginBody(BaseModel):
    token: str


def _is_private(ip: str) -> bool:
    """内网/本机地址返回 True（10.x、172.16-31.x、192.168.x、127.x、链路本地等）。"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # 无法解析的按内网处理，不拦截
    return addr.is_private or addr.is_loopback or addr.is_link_local


def _client_ip(request: Request) -> str:
    """真实客户端 IP：cloudflared 隧道一定带 Cf-Connecting-Ip（覆盖伪造），
    没有该头则是直连（局域网/本机），用对端地址。"""
    return (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
    )


def _authed(request: Request) -> bool:
    if not settings.access_token:
        return True  # 未配置密码：不开启登录
    got = request.cookies.get(AUTH_COOKIE)
    return bool(got) and hmac.compare_digest(got, settings.access_token)


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    """访问密码门：只拦外网请求（/api/* 与 /media/*）。

    局域网/本机直连免登录；经隧道（或公网 IP）访问的需密码。
    登录接口和健康检查除外。
    同时给静态资源加长缓存（/media 配合前端 ?v=N 版本号破坏缓存，/assets 为构建 hash 文件名）。
    """
    path = request.url.path
    protected = path.startswith("/api/") or path.startswith("/media/")
    if protected and not path.startswith(_PUBLIC_API):
        external = not _is_private(_client_ip(request))
        if external and not _authed(request):
            if path.startswith("/api/"):
                return JSONResponse({"detail": "需要登录"}, status_code=401)
            return Response(status_code=401)
    response = await call_next(request)
    if path.startswith("/media/") or path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@app.post("/api/login")
def login(body: LoginBody):
    if not settings.access_token or not hmac.compare_digest(body.token, settings.access_token):
        return JSONResponse({"detail": "密码错误"}, status_code=401)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        AUTH_COOKIE,
        settings.access_token,
        max_age=60 * 60 * 24 * 365,  # 1 年，输过一次不用再输
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


app.include_router(recipes.router)
app.include_router(search.router)
app.include_router(imports.router)
app.include_router(restaurants.router)
app.include_router(locations.router)
app.include_router(orders.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/net")
def net_info():
    """返回本机局域网 IPv4 地址，供设置页提示手机访问地址。"""
    import socket
    import subprocess
    import threading

    found = []

    def _discover():
        # 优先走系统命令（快、不触发 DNS；getaddrinfo 在本机 .local 名上会挂起）
        for iface in ("en0", "en1", "en2", "eth0", "wlan0"):
            try:
                out = subprocess.run(
                    ["ipconfig", "getifaddr", iface],
                    capture_output=True, text=True, timeout=2,
                )
                ip = out.stdout.strip()
                if ip and ":" not in ip and not ip.startswith("127."):
                    found.append(ip)
            except Exception:
                pass
        # 兜底：UDP 探测出口地址（带超时，不会发数据包）
        if not found:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2)
                s.connect(("223.5.5.5", 53))
                found.append(s.getsockname()[0])
                s.close()
            except Exception:
                pass

    t = threading.Thread(target=_discover, daemon=True)
    t.start()
    t.join(timeout=4)  # 无论网络环境多奇怪，接口最多等 4 秒
    return {"host": settings.host, "port": settings.port, "ips": sorted(set(found))}


settings.media_dir.mkdir(parents=True, exist_ok=True)  # 挂载前确保目录存在
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")

_dist = PROJECT_ROOT / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
