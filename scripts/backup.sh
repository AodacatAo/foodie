#!/usr/bin/env bash
# 备份：SQLite 在线备份（WAL 安全）+ media/snapshots 归档
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$ROOT/backups"

if [ -f "$ROOT/backend/data/foodie.db" ]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$ROOT/backend/data/foodie.db" ".backup '$ROOT/backups/foodie-${STAMP}.db'"
    echo "==> 数据库备份: backups/foodie-${STAMP}.db"
  else
    cp "$ROOT/backend/data/foodie.db" "$ROOT/backups/foodie-${STAMP}.db"
    echo "==> 数据库备份(直接复制): backups/foodie-${STAMP}.db"
  fi
fi

if [ -d "$ROOT/backend/data/media" ] || [ -d "$ROOT/backend/data/snapshots" ]; then
  tar -czf "$ROOT/backups/media-${STAMP}.tar.gz" -C "$ROOT/backend/data" media snapshots 2>/dev/null || true
  echo "==> 图片/快照备份: backups/media-${STAMP}.tar.gz"
fi

echo "==> 备份完成"
