# 🍜 食集 · 综合美食 Web

本地部署的个人美食库。第一模块：**菜谱** —— 从小红书链接/手动内容导入，自动提炼「食材 + 步骤」，本地持久化，随时搜索查询。

架构设计见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

## 快速开始

```bash
./scripts/start.sh
```

首次运行会自动：构建前端（npm）→ 创建 Python 虚拟环境（venv）→ 安装依赖 → 启动服务并打开浏览器（默认 http://127.0.0.1:8080）。

### 配置（.env）

复制 `.env.example` 为 `.env` 并填写：

| 配置 | 说明 | 必需 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（内容提炼） | 建议 |
| `XHS_COOKIE` | 小红书登录 cookie（M2 链接抓取） | M2 起 |
| `HOST` / `PORT` | 服务地址 | 否 |

> 建议使用**小红书小号**的 cookie，降低风控风险。

## 功能

### 🍜 菜谱库（模块一）
- **手动录入**：粘贴笔记正文 → 自动提炼食材/步骤（LLM，可配置）→ 草稿确认 → 入库
- **小红书链接抓取**：粘贴链接 → 自动抓取（Playwright + 本地登录态）→ 图片下载 → OCR → LLM 提炼 → 草稿
- **视频菜谱**：视频下载 → Whisper 本地语音转文字 → LLM 提炼步骤，详情页可播原视频
- **搜索**：FTS 全文搜索（菜名/食材/步骤），标签过滤
- **草稿箱**：LLM 提炼结果人工确认后才正式入库

### 🍽 餐厅库（模块二）
- **手动录入 + 大众点评一键抓取**：贴点评链接自动填店名/菜系/人均/评分/地址/封面
- **封面保证**：点评封面 > 手动图片 URL > 自动生成（菜系渐变+emoji+店名）
- **找店**：菜系/人均/评分/距离/吃过与否筛选，按距离/人均/评分/最近吃过/次数排序
- **定位**：浏览器自动定位（精度提示）、常用位置（家/公司）
- **就餐记录**：记录一次（日期/评分/实付/备注），时间线 + 次数/平均统计

## 数据

- SQLite（WAL 模式）：`backend/data/foodie.db`
- 图片/快照：`backend/data/media/`、`backend/data/snapshots/`
- 备份：`./scripts/backup.sh`（建议 cron/launchd 每日执行）

## 目录结构

```
backend/    FastAPI 应用（app/ 路由/服务/管线，data/ 运行时数据）
frontend/   Vue3 + Vite SPA（dist/ 构建产物由后端托管）
scripts/    start.sh 一键启动 · backup.sh 备份
```

## 里程碑

- [x] M1 骨架：CRUD + FTS 搜索 + 手动录入 + 草稿确认
- [x] M2 抓取：Playwright 登录态抓取（页面内嵌数据，绕开签名）+ 图片下载 + OCR + LLM 提炼
  - 登录：`backend/.venv/bin/python scripts/xhs_login.py`（弹 Chrome 窗口手动登录一次，登录态存 `backend/data/xhs_profile/`）
  - 注意：频繁自动化请求可能触发小红书 IP 风控（提示"IP 存在风险"），冷却后自动恢复；必要时切换网络
- [x] M3 视频菜谱：视频下载 + Whisper 本地转写 + 提炼（模型：ModelScope 下载到 `backend/data/models/`）
- [x] 模块二 N1-N5：餐厅库（CRUD/点评抓取/定位/就餐记录/打磨）

## 开发

```bash
# 后端（热重载）
cd backend && .venv/bin/uvicorn app.main:app --reload

# 前端（Vite dev server，代理 /api → 8080）
cd frontend && npm run dev
```
