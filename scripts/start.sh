#!/usr/bin/env bash
# 一键启动：前端构建（如缺失）→ Python venv → 启动服务 → 打开浏览器
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
BACKEND="$ROOT/backend"

# 1. 前端构建（dist 缺失时）
if [ ! -d "$ROOT/frontend/dist" ]; then
  echo "==> 首次运行，构建前端…"
  (cd "$ROOT/frontend" && npm_config_cache="$ROOT/frontend/node_modules/.npm-cache" npm install && npm run build)
fi

# 2. Python 虚拟环境
if [ ! -d "$BACKEND/.venv" ]; then
  echo "==> 创建 Python 虚拟环境…"
  python3 -m venv "$BACKEND/.venv"
fi
echo "==> 安装/更新依赖…"
"$BACKEND/.venv/bin/pip" install -q -r "$BACKEND/requirements.txt"

# 3. .env 配置
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "==> 已生成 .env（请填写 DEEPSEEK_API_KEY / XHS_COOKIE 后重启生效）"
fi

# 4. 启动（端口取自 .env，由 pydantic-settings 读取）
cd "$BACKEND"
HOST=$("$BACKEND/.venv/bin/python" -c "from app.config import settings; print(settings.host)")
PORT=$("$BACKEND/.venv/bin/python" -c "from app.config import settings; print(settings.port)")
echo "==> 本机访问: http://127.0.0.1:$PORT"
if [ "$HOST" = "0.0.0.0" ]; then
  LAN_IPS=$("$BACKEND/.venv/bin/python" - <<'PY' 2>/dev/null || true
import socket, subprocess
ips = []
for iface in ("en0", "en1", "en2", "eth0", "wlan0"):
    try:
        out = subprocess.run(["ipconfig", "getifaddr", iface], capture_output=True, text=True, timeout=2)
        ip = out.stdout.strip()
        if ip and ":" not in ip and not ip.startswith("127."):
            ips.append(ip)
    except Exception:
        pass
if not ips:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("223.5.5.5", 53))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
for ip in sorted(set(ips)):
    print(ip)
PY
)
  for ip in $LAN_IPS; do
    echo "==> 局域网（手机/平板，同一 Wi-Fi）: http://$ip:$PORT"
  done
fi
(sleep 1.5; open "http://127.0.0.1:$PORT" 2>/dev/null || true) &
exec "$BACKEND/.venv/bin/uvicorn" app.main:app --host "$HOST" --port "$PORT"
