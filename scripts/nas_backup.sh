#!/bin/sh
# 食集 NAS 每日备份（异池）：foodie 数据 + wechat-notify 凭据 → /share/ZFS19_DATA/foodie-backups
# - 数据库：容器内 python sqlite backup API 一致性快照（运行中安全）
# - 大文件：硬链接视图（media/snapshots/models，日全量视图共享历史块，省空间）
# - 目标池 zpool3 与源池 zpool1 为不同物理池，池级故障不互相影响
# 安装：crontab 增加一行（deploy_qnap.py up 阶段幂等安装）
#   15 4 * * * /share/ZFS2_DATA/foodie/scripts/nas_backup.sh
set -u

DOCKER=/share/ZFS1_DATA/.qpkg/container-station/bin/docker
SRC=/share/ZFS2_DATA/foodie/data
WECHAT_DATA=/share/ZFS2_DATA/wechat-notify/wechat-data
DEST=/share/ZFS19_DATA/foodie-backups
KEEP=14                      # 保留最近 N 天
STAMP=$(date +%Y%m%d-%H%M%S)
DAY="$DEST/daily/$STAMP"
LOG=/tmp/foodie_backup.log

mkdir -p "$DAY"
echo "[$(date '+%F %T')] 备份开始 → $DAY" >> "$LOG"

# 1) 数据库一致性快照；容器不可用/失败时 rsync 原文件降级（尽力而为）
if "$DOCKER" exec foodie python -c "import sqlite3" >/dev/null 2>&1 \
   && "$DOCKER" exec foodie python -c "
import sqlite3
src = sqlite3.connect('/app/backend/data/foodie.db')
dst = sqlite3.connect('/tmp/foodie-backup.db')
with dst:
    src.backup(dst)
src.close()
" 2>>"$LOG" \
   && "$DOCKER" cp foodie:/tmp/foodie-backup.db "$DAY/foodie.db" 2>>"$LOG"; then
    "$DOCKER" exec foodie rm -f /tmp/foodie-backup.db 2>/dev/null
    echo "[$(date '+%F %T')] DB 一致性快照完成" >> "$LOG"
else
    echo "[$(date '+%F %T')] DB 备份 API 失败，rsync 降级" >> "$LOG"
    rsync -a "$SRC/foodie.db" "$SRC/foodie.db-wal" "$SRC/foodie.db-shm" "$DAY/" 2>>"$LOG" || true
fi

# 2) 大文件增量：rsync + --link-dest（与上一份备份硬链接去重，仅复制变更文件；
#    注意跨池不能对源文件硬链接，去重只发生在目标池 zpool3 内部）
for sub in media snapshots models; do
    if [ -d "$SRC/$sub" ]; then
        if [ -e "$DEST/latest/$sub" ]; then
            rsync -a --link-dest="$DEST/latest/$sub" "$SRC/$sub/" "$DAY/$sub/" 2>>"$LOG" || true
        else
            rsync -a "$SRC/$sub/" "$DAY/$sub/" 2>>"$LOG" || true
        fi
    fi
done

# 3) wechat-notify 凭据（独立服务数据卷，小文件）
if [ -d "$WECHAT_DATA" ]; then
    rsync -a "$WECHAT_DATA/" "$DAY/wechat-data/" 2>>"$LOG" || true
fi

# 4) latest 软链 + 过期清理
ln -sfn "$DAY" "$DEST/latest"
find "$DEST/daily" -mindepth 1 -maxdepth 1 -type d -mtime +$KEEP -exec rm -rf {} + 2>>"$LOG"

echo "[$(date '+%F %T')] 完成：$(du -sh "$DAY" 2>/dev/null | cut -f1)" >> "$LOG"
