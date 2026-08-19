#!/usr/bin/env python3
"""一键部署食集到 QNAP NAS（Docker Compose）。

用法: NAS_PASS='xxx' python3 scripts/deploy_qnap.py [stage]

stage: pack   —— 本机打包（一致性 DB 备份 + 代码/数据 tar）
       upload —— SFTP 上传到 NAS /share/ZFS2_DATA/foodie
       extract—— NAS 上解包
       build  —— NAS 上构建镜像（耗时较长）
       up     —— compose 启动 + 自检
       all    —— 全流程（默认）
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time

import paramiko


def _resolve_nas_host() -> str:
    """从 ~/.ssh/config 的 nas-git 条目解析 NAS 地址（代码零硬编码）。
    也可用环境变量 NAS_HOST 覆盖。找不到时回退占位符。"""
    env = os.environ.get("NAS_HOST")
    if env:
        return env
    try:
        ssh_conf = os.path.expanduser("~/.ssh/config")
        host = None
        active = False
        for line in open(ssh_conf, encoding="utf-8"):
            line = line.strip()
            if line.lower().startswith("host ") and "nas-git" in line:
                active = True
                continue
            if active and line.lower().startswith("host ") and "nas-git" not in line:
                break
            if active and line.lower().startswith("hostname "):
                host = line.split(None, 1)[1]
                break
        if host:
            return host
    except Exception:
        pass
    return "your-nas-ip"  # 占位：请设置 NAS_HOST 或在 ~/.ssh/config 配置 nas-git


NAS_HOST = _resolve_nas_host()
NAS_USER = os.environ.get("NAS_USER", "admin")
NAS_DIR = "/share/ZFS2_DATA/foodie"
DOCKER = "/share/ZFS1_DATA/.qpkg/container-station/bin/docker"
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # foodie/
STAGE = "/tmp/foodie_deploy"
PASS = os.environ.get("NAS_PASS")
if not PASS:
    print("缺少 NAS_PASS 环境变量")
    sys.exit(1)


def ssh(conn, cmd, timeout=300):
    stdin, stdout, stderr = conn.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return out, err


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(NAS_HOST, port=22, username=NAS_USER, password=PASS, timeout=20,
              allow_agent=False, look_for_keys=False)
    return c


def pack():
    print("== pack: 一致性备份 DB ==")
    os.makedirs(f"{STAGE}/data_stage", exist_ok=True)
    src = sqlite3.connect(f"{LOCAL_ROOT}/backend/data/foodie.db")
    dst = sqlite3.connect(f"{STAGE}/data_stage/foodie.db")
    with dst:
        src.backup(dst)
    dst.close()
    src.close()

    print("== pack: 复制数据目录（media/models/配置/浏览器登录态）==")
    data_root = f"{LOCAL_ROOT}/backend/data"
    for name in os.listdir(data_root):
        if name in ("foodie.db", "foodie.db-wal", "foodie.db-shm"):
            continue  # db 已用备份 API 生成
        p = os.path.join(data_root, name)
        if os.path.isdir(p):
            shutil.copytree(p, f"{STAGE}/data_stage/{name}", dirs_exist_ok=True)
        else:
            shutil.copy2(p, f"{STAGE}/data_stage/{name}")

    print("== pack: 打包代码 ==")
    with tarfile.open(f"{STAGE}/code.tgz", "w:gz") as t:
        for rel in ["backend/app", "backend/requirements.txt", "frontend/dist",
                    ".env", "Dockerfile", ".dockerignore", "docker-compose.yml"]:
            t.add(f"{LOCAL_ROOT}/{rel}", arcname=rel)

    print("== pack: 打包数据 ==")
    with tarfile.open(f"{STAGE}/data.tgz", "w:gz") as t:
        t.add(f"{STAGE}/data_stage", arcname="data")

    for f in ("code.tgz", "data.tgz"):
        sz = os.path.getsize(f"{STAGE}/{f}") / 1e6
        print(f"   {f}: {sz:.1f} MB")


def upload(conn):
    """QNAP 未启用 SFTP 子系统：改用 SSH exec 通道流式传 tar 并就地解包。

    data.tgz 仅用于**首次部署**（NAS 上还没有数据库时迁移数据）；
    已部署后跳过——绝不覆盖线上数据（历史上多次部署覆盖导致数据丢失）。
    """
    print("== upload: 流式上传并解包 ==")
    for f in ("code.tgz", "data.tgz"):
        if f == "data.tgz":
            out, _ = ssh(conn, f"[ -f {NAS_DIR}/data/foodie.db ] && echo EXISTS || echo MISSING", timeout=30)
            if "EXISTS" in out:
                print("   data.tgz 跳过：NAS 已有数据库（保护线上数据，不覆盖）")
                continue
        src = f"{STAGE}/{f}"
        t0 = time.time()
        chan = conn.get_transport().open_session()
        chan.settimeout(1800)
        chan.exec_command(
            f"mkdir -p {NAS_DIR} && cd {NAS_DIR} && rm -f {f} && tar -xzf - && echo EXTRACT_OK"
        )
        with open(src, "rb") as fh:
            while True:
                chunk = fh.read(1 << 16)
                if not chunk:
                    break
                chan.sendall(chunk)
        chan.shutdown_write()
        out = chan.makefile().read().decode(errors="replace").strip()
        err = chan.makefile("stderr").read().decode(errors="replace").strip()
        if "EXTRACT_OK" not in out:
            print(f"   {f} 解包失败:", out[-300:], err[-300:])
            sys.exit(1)
        print(f"   {f} → {NAS_DIR} 完成 ({time.time()-t0:.0f}s)")
        chan.close()


def extract(conn):
    print("== extract: NAS 解包 ==")
    out, err = ssh(conn, f"cd {NAS_DIR} && tar -xzf code.tgz && tar -xzf data.tgz && ls -d data app 2>/dev/null && rm -f code.tgz data.tgz")
    print(out.strip()[:500])
    if err.strip():
        print("[stderr]", err.strip()[:300])


MIRRORS = [
    "docker.1panel.live",
    "dockerproxy.net",
    "docker.m.daocloud.io",
    "hub.rat.dev",
]


def _pick_mirror(conn):
    """Docker Hub 不可达时，探测可用的国内镜像源（返回 200/401 都视为可用）。"""
    out, _ = ssh(conn, "curl -s --max-time 8 -o /dev/null -w '%{http_code}' https://registry-1.docker.io/v2/", timeout=30)
    if out.strip() in ("200", "401"):
        return None  # Hub 可达，用默认
    for m in MIRRORS:
        out, _ = ssh(conn, f"curl -s --max-time 8 -o /dev/null -w '%{{http_code}}' https://{m}/v2/", timeout=30)
        code = out.strip()
        if code in ("200", "401"):
            print(f"   Docker Hub 不可达，选用镜像源: {m}")
            return m
    print("   警告: 没有可用镜像源，尝试直连 Hub")
    return None


def build(conn):
    print("== build: NAS 构建镜像（进度写入 /tmp/foodie_build.log）==")
    mirror = _pick_mirror(conn)
    args = ""
    if mirror:
        args = f"--build-arg BASE_IMAGE={mirror}/library/python:3.11-slim"
    # QNAP 无 nohup：用 setsid 完全脱离 SSH 会话
    out, err = ssh(conn, f"cd {NAS_DIR} && setsid sh -c '{DOCKER} build -t foodie:latest {args} . > /tmp/foodie_build.log 2>&1' < /dev/null & echo started", timeout=60)
    print(out.strip()[:200])
    if err.strip():
        print("[stderr]", err.strip()[:300])


def up(conn):
    print("== up: 准备隧道镜像 + compose 启动 ==")
    # cloudflared 也来自 Hub；不可达时经镜像源拉取并打回原名
    mirror = _pick_mirror(conn)
    if mirror:
        out, _ = ssh(conn, f"{DOCKER} pull {mirror}/cloudflare/cloudflared:latest 2>&1 | tail -2 "
                           f"&& {DOCKER} tag {mirror}/cloudflare/cloudflared:latest cloudflare/cloudflared:latest", timeout=900)
        print(out.strip()[:400])
    out, err = ssh(conn, f"cd {NAS_DIR} && {DOCKER} compose up -d 2>&1", timeout=600)
    print(out.strip()[:800])
    if err.strip():
        print("[stderr]", err.strip()[:400])
    time.sleep(8)
    out, _ = ssh(conn, f"{DOCKER} ps --filter name=foodie --format '{{{{.Names}}}} {{{{.Status}}}}'")
    print(out.strip())
    out, _ = ssh(conn, f"curl -s --max-time 8 http://127.0.0.1:8080/api/health")
    print("NAS 本机 health:", out.strip()[:200])
    out, _ = ssh(conn, f"{DOCKER} logs foodie-tunnel 2>&1 | grep -o 'https://[a-z-]*\\.trycloudflare\\.com' | head -1")
    if out.strip():
        print("外网隧道地址:", out.strip())
    else:
        print("外网隧道地址: 尚未就绪（稍后 docker logs foodie-tunnel 查看）")


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    steps = ["pack", "upload", "extract", "build", "up"] if stage == "all" else [stage]
    conn = None
    for s in steps:
        if s == "pack":
            pack()
        else:
            if conn is None:
                conn = connect()
            {"upload": upload, "extract": extract, "build": build, "up": up}[s](conn)
    if conn:
        conn.close()
    print("== 完成 ==")


if __name__ == "__main__":
    main()
