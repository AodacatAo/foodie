#!/usr/bin/env bash
# 外网访问（Cloudflare 免费隧道，免注册）
# 用法: ./scripts/tunnel.sh
# 说明:
#   - 每次启动会生成一个新的 https://xxx.trycloudflare.com 临时地址（打印在日志里）
#   - 需要固定域名时：注册免费 Cloudflare 账号 + 一个自己的域名，改用命名隧道
#   - 服务本身需先启动（./scripts/start.sh）
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x ./bin/cloudflared ]; then
  echo "==> 未找到 ./bin/cloudflared，尝试下载（gh 镜像）…"
  mkdir -p ./bin
  ARCH=$(uname -m)
  if [ "$ARCH" = "arm64" ]; then FILE="cloudflared-darwin-arm64.tgz"; else FILE="cloudflared-darwin-amd64.tgz"; fi
  curl -sL --max-time 150 -o ./bin/cloudflared.tgz "https://ghfast.top/https://github.com/cloudflare/cloudflared/releases/latest/download/$FILE"
  tar -xzf ./bin/cloudflared.tgz -C ./bin && rm ./bin/cloudflared.tgz && chmod +x ./bin/cloudflared
fi

exec ./bin/cloudflared tunnel --url http://127.0.0.1:8080 --no-autoupdate --protocol http2
