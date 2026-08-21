# 综合美食 Web — 架构设计文档

> 状态：v1 设计稿（2025）
> 范围：第一模块「菜谱」—— 小红书链接抓取 + 提炼 + 本地查询

---

## 1. 项目概述

### 1.1 目标
- **综合美食 Web**：本地部署的个人美食库，持久化存储，随时调用。
- **第一模块（菜谱）**：粘贴小红书笔记链接 → 自动抓取 → 提炼「食材 + 步骤」→ 入库 → 随时搜索查询。
- 后续可扩展模块：收藏夹、购物清单、食材库存、「今天吃什么」随机推荐等（本设计预留扩展位，不在 v1 实现）。

### 1.2 核心决策（已与用户确认）
| 决策点 | 选择 |
|---|---|
| 后端 | Python FastAPI |
| 笔记形式 | 图文笔记为主 → 需要 OCR |
| 内容提炼 | 云端 LLM API（DeepSeek，OpenAI 兼容） |
| 抓取登录态 | 用户提供小红书登录 cookie |
| 部署 | 本机直接运行（venv + uvicorn），不做 Docker（v1） |
| 存储 | SQLite（主数据）+ 文件系统（图片/快照） |

### 1.3 设计原则
1. **单体优先**：本地个人工具，不引入微服务、消息队列等复杂度。
2. **抓取与存储解耦**：抓取管线产出「原始快照 + 提炼结果」，数据层只依赖快照，抓取挂了不影响已入库数据。
3. **人机协同**：LLM 提炼结果默认进入「草稿」态，人工确认后才正式入库——LLM 会出错，确认环节是质量底线。
4. **一切可降级**：小红书接口变更/封禁时，保留「手动粘贴笔记内容」的兜底入库通道。

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────┐
│  浏览器 (Web UI — Vue3 SPA，FastAPI 静态托管)        │
│  列表搜索 │ 详情查看 │ 链接导入 │ 草稿确认编辑         │
└────────────────────────┬────────────────────────────┘
                         │ HTTP / JSON
┌────────────────────────▼────────────────────────────┐
│  FastAPI 应用层                                      │
│  ├─ routers/    recipes · imports · search           │
│  ├─ services/   业务逻辑层                            │
│  └─ tasks/      后台任务执行器（asyncio 任务队列）     │
├──────────────────────────────────────────────────────┤
│  抓取管线 import_pipeline（异步执行）                  │
│  URL解析 → XHS API 抓取 → 文本/图片提取               │
│  → OCR(图片) → LLM 结构化提炼 → 草稿入库              │
├──────────────────────────────────────────────────────┤
│  存储层                                              │
│  ├─ SQLite (WAL) + SQLAlchemy + FTS5 全文搜索        │
│  ├─ data/media/   笔记图片（按 note_id 分目录）       │
│  ├─ data/snapshots/ 原始抓取 JSON 快照                │
│  └─ scripts/backup.sh 备份                            │
└──────────────────────────────────────────────────────┘
```

**关键设计**：抓取管线是**独立的单向数据流**，每步产出物落盘（快照），任何一步失败都有明确断点，可断点重试。

---

## 3. 技术选型

| 组件 | 选型 | 理由 |
|---|---|---|
| Web 框架 | FastAPI + uvicorn | 异步友好、自动 OpenAPI 文档、生态成熟 |
| ORM | SQLAlchemy 2.x | 与 FastAPI 标准搭配，模型清晰 |
| 数据库 | SQLite（WAL 模式）+ FTS5 | 零运维、单文件易备份；个人量级绰绰有余 |
| 抓取 | `xhs` PyPI 库（首选）+ Playwright（降级） | 前者轻量（cookie + JS 签名），后者兜底（完整浏览器环境） |
| OCR | RapidOCR（onnxruntime） | 离线、免费、轻量（约百 MB 模型），支持中文 |
| LLM | DeepSeek API（`deepseek-chat`） | 便宜（百万 token 级别）、OpenAI 兼容协议 |
| 前端 | Vue3 + Vite（SPA） | 后续多模块扩展友好；构建产物由 FastAPI 静态托管 |
| 后台任务 | asyncio 队列（进程内） | v1 无持久化任务需求，避免引入 Celery/Redis |
| 配置 | 环境变量 + `.env` + `config.yaml` | cookie、API key 不入代码库 |

---

## 4. 数据模型（v1）

### 4.1 ER 概览

```
recipes                    import_tasks
┌──────────────────┐       ┌──────────────────────┐
│ id (PK)          │       │ id (PK)              │
│ title            │       │ url                  │
│ author           │       │ note_id              │
│ source_url       │       │ status               │
│ note_id          │       │   pending/running/   │
│ cover_image      │       │   success/failed/    │
│ description      │       │   needs_review       │
│ cooking_time_min │       │ snapshot_path        │
│ servings         │       │ ocr_text_path        │
│ ingredients JSON │       │ llm_output_path      │
│ steps JSON       │       │ error                │
│ tags JSON        │       │ created_at           │
│ status           │       │ updated_at           │
│   draft/published│       └──────────────────────┘
│ created_at       │
│ updated_at       │
└──────────────────┘
```

### 4.2 关键列设计说明

- **ingredients**（JSON 数组）：`[{ "name": "鸡胸肉", "amount": "300g", "note": "切块" }]`
- **steps**（JSON 数组）：`[{ "order": 1, "title": "腌制", "description": "...", "image": "note_xxx/1.jpg" }]` —— 步骤可关联原图，图文菜谱的图片顺序即步骤顺序。
- **tags**（JSON 数组）：`["川菜", "快手菜", "一人食"]`
- **status 双态**：`draft`（LLM 提炼待人工确认）→ `published`（确认入库）。这保证 LLM 输出不直接污染主数据。
- **import_tasks.status = needs_review**：抓取成功但提炼结果置信度低（LLM 校验失败/OCR 为空），转人工处理。
- v1 食材/步骤用 JSON 列（务实）；搜索依赖 FTS5 冗余索引列，不做关系表拆分。

### 4.3 搜索设计

- SQLite **FTS5 虚拟表**：冗余索引 `title / description / ingredients 文本 / steps 文本 / tags`。
- 写入时同步维护 FTS 表；查询用 `MATCH` 支持关键词搜索，另支持标签过滤、状态过滤、按更新时间排序。
- 中文分词：FTS5 默认 unicode61 对中文按字符切分，个人量级够用；如效果差可后续引入 `simple` 分词器或 jieba 预处理，v1 不引入。

---

## 5. 抓取管线详细设计（核心模块）

### 5.1 管线流程

```
用户提交 URL
   │
   ▼
[1] URL 校验解析          → 校验 xiaohongshu.com 域名，提取 note_id
   │                        （/explore/<id>、/discovery/item/<id>、短链重定向等）
   ▼
[2] XHS 抓取              → xhs 客户端（cookie + x-s 签名）请求笔记详情
   │                        失败 → 降级 Playwright 打开 URL 抓页面数据
   │                        再失败 → 任务失败，提示用户手动粘贴内容
   ▼
[3] 内容提取              → title / desc / 作者 / 封面 / 图片列表
   │                        图片下载到 data/media/<note_id>/
   │                        原始响应存 data/snapshots/<note_id>.json
   ▼
[4] OCR（图文核心）        → RapidOCR 按图片顺序识别 → 拼接为 ocr_text
   │                        空文本的图片（纯装饰图）跳过
   ▼
[5] LLM 结构化提炼        → DeepSeek：输入 [正文 + OCR 文本] → 输出 JSON
   │                        {title, ingredients[], steps[], cooking_time,
   │                         servings, tags, notes}
   │                        Pydantic schema 校验；失败重试 2 次
   ▼
[6] 草稿入库              → 生成 recipe(status=draft) + import_task 关联
   │                        UI 通知用户去「草稿确认页」
   ▼
[7] 人工确认              → 用户编辑食材/步骤/标签 → 确认 → status=published
```

### 5.2 抓取适配层（xhs_client）

- 封装 `xhs` 库：注入用户 cookie（`web_session`、`a1`、`webId` 等），自动处理 x-s 签名。
- **接口抽象**：`XHSFetcher` 定义 `fetch_note(note_id) -> NotePayload`，内部实现可切换：
  - `XhsApiFetcher`（首选，轻量）
  - `PlaywrightFetcher`（降级，打开笔记页抓取初始 state JSON）
- 抓取限速：相邻请求间隔 ≥ 3s，防风控。
- cookie 过期检测：返回登录态错误码时，任务标记 `failed` 并在 UI 提示「cookie 失效，请更新」。

### 5.3 OCR 服务（ocr_service）

- RapidOCR（onnxruntime CPU 推理），全离线。
- 输入：图片路径列表（保持小红书图片顺序）；输出：`[{image_index, text}]`。
- 轻量优化：大图先缩放（最长边 ≤ 1600px）再识别，控制耗时。

### 5.4 LLM 服务（llm_service）

- Provider 抽象：`LLMProvider` 接口（`complete(system, user) -> str`），当前实现 `OpenAICompatProvider`（DeepSeek base_url = `https://api.deepseek.com`）。
- Prompt 模板（`prompts/refine.py`）：
  - System：你是专业的菜谱结构化助手，将小红书笔记内容提炼为结构化 JSON。
  - User：原文 + OCR 文本 + 严格 JSON 输出格式说明。
- 输出校验：`RefinedRecipe` Pydantic 模型，`ingredients`/`steps` 非空才通过；失败自动重试（次数上限 2，带错误反馈的二次 prompt）。
- **防幻觉**：prompt 明确「原文没有的信息（如耗时、份量）用 null，不要编造」。

### 5.5 后台任务

- 进程内 asyncio 任务队列（`tasks/`）：提交导入 → 后台按管线执行 → 更新 `import_tasks` 状态。
- 前端轮询任务状态（v1 简单可靠；量级不需要 WebSocket）。
- 服务重启未完成任务：启动时扫描 `pending/running` 任务，标记为 `failed(interrupted)` 可手动重试。

---

## 6. 前端设计（v1）

技术：Vue3 + Vite，构建产物由 FastAPI `StaticFiles` 托管（单端口，本地部署最简）。

| 页面 | 功能 |
|---|---|
| 菜谱列表 `/` | 搜索框（FTS 关键词）、标签过滤、卡片列表（封面/标题/作者/耗时） |
| 菜谱详情 `/recipe/:id` | 封面、食材清单（勾选交互）、步骤（文字 + 关联原图）、来源链接、编辑 |
| 导入 `/import` | 粘贴小红书链接 → 提交 → 显示任务进度（轮询） |
| 草稿确认 `/drafts/:task_id` | 展示 LLM 提炼结果，逐字段可编辑 → 确认入库 / 放弃 |
| 手动录入 `/manual` | 兜底通道：无链接时手动粘贴标题/正文/图片，走同一提炼管线（OCR+LLM） |

---

## 7. 项目目录结构

```
foodie/
├── ARCHITECTURE.md
├── README.md
├── .env.example              # cookie / DEEPSEEK_API_KEY / 路径配置样例
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 入口（挂路由 + 静态资源）
│   │   ├── config.py         # 配置加载（env + yaml）
│   │   ├── database.py       # SQLAlchemy engine/session
│   │   ├── models.py         # ORM 模型（Recipe / ImportTask）
│   │   ├── schemas.py        # Pydantic 模型（API + LLM 校验共用）
│   │   ├── routers/
│   │   │   ├── recipes.py    # CRUD + 编辑
│   │   │   ├── imports.py    # 提交/查询任务、草稿确认
│   │   │   └── search.py     # FTS 搜索
│   │   ├── services/
│   │   │   ├── recipe_service.py
│   │   │   ├── xhs_client.py      # 抓取适配层
│   │   │   ├── ocr_service.py     # RapidOCR
│   │   │   ├── llm_service.py     # DeepSeek 提炼
│   │   │   └── import_pipeline.py # 管线编排
│   │   ├── prompts/refine.py      # LLM prompt 模板
│   │   └── tasks/queue.py         # 后台任务队列
│   ├── data/                  # 运行时数据（gitignore）
│   │   ├── foodie.db
│   │   ├── media/<note_id>/…
│   │   └── snapshots/<note_id>.json
│   └── requirements.txt
├── frontend/                 # Vue3 + Vite SPA
│   ├── src/{views,components,api}
│   └── dist/                 # 构建产物（FastAPI 托管）
└── scripts/
    ├── start.sh              # 一键启动（检查依赖 → uvicorn → 开浏览器）
    └── backup.sh             # 打包 data/ → 带时间戳 tar.gz
```

---

## 8. 部署与运维

### 8.1 启动（scripts/start.sh）
1. 检查/创建 venv，安装 requirements。
2. 校验 `.env`（cookie、API key 缺失时给出明确提示）。
3. 启动 uvicorn（`localhost:8080`，SQLite WAL）。
4. 自动打开浏览器。

### 8.2 备份（scripts/backup.sh）
- 打包 `data/`（SQLite + media + snapshots）→ `backups/foodie-YYYYMMDD-HHMMSS.tar.gz`。
- SQLite 用 `sqlite3 .backup` 在线备份（WAL 模式下安全），再连同 media 归档。
- 建议 cron/launchd 每日执行（v1 提供脚本，定时由用户自行配置）。

### 8.3 数据安全
- `.env`（含 cookie / API key）gitignore，不入库。
- SQLite 单文件 + 图片目录即全部数据，备份即完整可迁移。

---

## 9. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 小红书接口变更/反爬升级 | 抓取失效 | 适配层隔离（xhs/Playwright 双实现）；快照落盘不依赖接口稳定性；兜底手动录入 |
| cookie 过期/风控 | 抓取失败，可能封号 | 低频限速（≥3s 间隔）；建议使用小号；失败时 UI 明确提示更新 cookie |
| 图文 OCR 识别质量 | 步骤文本错漏 | 保留原图并在步骤中关联展示；草稿确认环节对照原图人工修正 |
| LLM 提炼幻觉/结构错误 | 数据质量差 | JSON schema 强校验 + 重试；缺失信息置 null 不编造；draft 人工确认门槛 |
| FTS5 中文分词效果 | 搜索召回差 | 个人量级可接受；预留 jieba 预处理扩展位 |
| 版权/合规 | — | 仅个人本地使用；保存来源链接并展示「查看原帖」；不对外发布 |

---

## 10. 里程碑计划

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **M1 骨架** | 项目脚手架、数据模型、Recipe CRUD、FTS 搜索、手动录入兜底 | 不依赖抓取即可录入并搜索菜谱 |
| **M2 抓取** | xhs_client（cookie）+ Playwright 降级、import 任务流 | 输入真实链接能抓回笔记数据与图片 |
| **M3 提炼** | RapidOCR + DeepSeek 结构化 + 草稿确认页 | 图文菜谱全自动提炼，人工确认后入库 |
| **M4 完善** | 前端打磨、一键启动、备份脚本、README | 日常可用的完整闭环 |

> 依赖的第三方库（xhs 抓取、RapidOCR）在 M1 阶段先做技术验证（spike），确认可行后再进入 M2，避免返工。

---

## 11. 待办/开放问题

- [ ] 项目命名与目录（当前暂定 `foodie/`，可改）
- [ ] M1 阶段先跑通「xhs 库 + cookie」抓取 spike，验证签名方案在当前环境可用
- [ ] 小红书视频笔记 v1 仅提取封面+描述，是否可接受
- [ ] 端口默认 8080，是否冲突

---

# 模块二：美食收藏（餐厅库）—— 已整体移除（2026-08）

餐厅库模块（大众点评抓取 + 收藏/评分/距离/就餐记录）已应要求**整体移除**：

- 后端：`routers/restaurants.py`、`routers/locations.py`、`services/restaurant_service.py`、
  `services/dianping_client.py`、`services/amap_client.py`、`services/cover_service.py`
  （字体辅助提取为独立 `services/fonts.py`，供分享卡片继续使用）全部删除；
  `Restaurant/VisitLog/UserLocation` 模型、`restaurants_fts` 虚拟表与触发器、相关 schema、
  `AMAP_KEY` 配置、`zhconv` 依赖一并移除
- 前端：餐厅列表/详情/录入三页面与 RestaurantEditor 组件、路由、导航入口、API 函数删除；
  设置页「常用位置」卡片删除（局域网访问/关于保留）
- 脚本：`dianping_login.py`、`backfill_dishes.py` 删除
- 数据：NAS 上 restaurants/visit_logs/user_locations 旧表与 media/restaurants、media/dishes、
  media/uploads 旧文件**保留不动**（如需彻底清理另行处理）
- 迁移：历史迁移 v2 加表存在性守卫，全新建库不再创建餐厅相关表也能通过

### 模块三 · 菜单/点餐（2026-08）

**双端模型**：
| 端 | 路由 | 能力 |
|---|---|---|
| 管理端 | `/#/menu` | 上架/下架、定价（内联编辑）、分类（预设+自定义）、点单记录管理、生成扫码二维码 |
| 用户端 | `/#/order` | 美团式点餐：分类栏过滤、+/- 份数、底部购物车（清单/合计/清空）、填名字下单；**无导航/无定价/无做法预览**（路由 `meta.hideNav` 隐藏全部导航） |

**数据模型**（recipes 表扩展 + orders 表）：
- `on_menu`（上架）、`menu_at`（上架时间）、`menu_price`（元）、`menu_category`（分类）、`menu_want`（管理端「今天想吃」勾选）
- `orders`：下单快照（person/items JSON/total/created_at）
- `menu_qty` 列已废弃保留（旧版把购物车份数存服务端，已废弃——见下）

**购物车位置（2026-08 架构修正）**：购物车从服务端 `recipes.menu_qty` 迁移到**每台设备前端 localStorage**（`foodie_cart_v1`，每台手机独立互不干扰）；下单时前端提交明细 `POST /orders {person, items:[{recipe_id, qty}]}`，**服务端按当前菜单校验（存在性/上架状态）并以服务端价格快照**，客户端价格一律不采信。原「点单状态与管理端实时互通、下单清空服务端购物车」的语义随之移除；`menu_want` 回归纯管理端意愿标记，与购物车彻底解耦。

**API**：`POST /recipes/{id}/menu`（上架）、`DELETE .../menu`（下架）、`POST .../menu-price`、`POST .../menu-category`、`POST .../want`（想吃切换）、`POST /orders`（提交本机购物车明细→校验+快照）、`GET/DELETE /orders`

**微信下单通知**（NAS 直推，秒级）：
- 后端 `wechat_notify.py` 用 Python 实现 iLink 官方 sendmessage 协议（协议常量对齐腾讯 openclaw-weixin SDK 2.4.6：`iLink-App-Id: bot`、`AuthorizationType: ilink_bot_token`、`X-WECHAT-UIN` 随机、body 含 `base_info`）
- 账号凭据：NAS 数据卷 `data/wechat_account.json`（登录产物迁移，不入版本库）
- **彻底分离（2026-08 二次重构）**：`wechat-notify` 已成为**独立仓库/独立 compose**（NAS 目录 `/share/ZFS2_DATA/wechat-notify`，端口 8090，Bearer token 鉴权，凭据数据卷 `wechat-data/`）；食集下单时经 HTTP 调 `WECHAT_NOTIFY_URL=http://wechat-notify:8090/notify`（通过 `docker network connect foodie_default wechat-notify` 运行时打通，deploy 脚本幂等执行），食集容器内**不含任何微信代码**
- 通用接口：`POST :8090/notify {text}`——供脚本/DSH skill 等主动触达微信；配套 DSH skill「wechat-notify」
- 早期方案（Mac launchd 轮询 `scripts/order-notify.mjs`）已停用，脚本保留备用
- **prepare failed 根治（2026-08-20）**：iLink `sendmessage` 的「已 prepare」状态绑定**登录会话世系**（get_updates_buf）——空 buf 轮询建立的是无法发送的旁观会话，`notifystart` 保活救不回（症状：聊天桥下线约 5-6 小时后推送持续 prepare failed，已实测复现）。wechat-notify 服务新增**持续 getupdates 长轮询监控循环**（会话游标持久化在数据卷 `get_updates_buf.json`，重启沿用），不再依赖电脑端聊天桥在线。注意：若电脑端 DSH 聊天桥与 NAS 共用同一 bot 账号，会话世系仍会互相抢占（历史上可共存但偶发失败）；彻底隔离需为 NAS 服务单独登录一个 bot 账号（备选方案，未实施）

**扫码点餐**：管理端「📱 扫码点餐」按钮用 qrcode 库生成二维码，指向 `{origin}/#/order`（自动适配局域网 IP），手机同 Wi-Fi 微信扫码直达用户端。

---

## 架构复盘 · P0/P1 落地记录（2026-08）

对三模块整体复盘后，按优先级落地 P0/P1（其余 P2/P3 见复盘结论，暂缓）：

| 项 | 结论 | 落地 |
|---|---|---|
| P0-1 密钥入镜像 | `.env` 曾被打进镜像层（Dockerfile `COPY .env`） | 移除 COPY + `.dockerignore` 排除 `.env`；配置改由 compose `env_file` 运行时注入（宿主目录 `.env`） |
| P0-2 购物车位置 | 购物车原存服务端 `recipes.menu_qty`，多手机互相串扰、并发下单重复快照；且启动时无条件 `UPDATE menu_qty=1 WHERE menu_want=1` 会把「想吃」强行塞回购物车 | 购物车迁移到**每台设备前端 localStorage**；下单改前端提交明细、服务端按当前菜单校验 + 服务端价格快照；`menu_want` 回归纯管理端意愿标记；启动时无条件 UPDATE 删除；废弃的 `/order` 端点与 `menu_qty` 输出字段移除（列保留兼容） |
| P1-1 迁移机制 | 加列靠 init_db 手工补丁（`_add_column_if_missing`），无版本记录 | `backend/app/migrations.py`：`schema_migrations` 表 + 版本化迁移（只增不改、防重复写法），init_db 事务内按序执行 |
| P1-2 媒体缓存 | 前端 `?v=3` 手工版本号，改图忘 bump 就显示旧图 | 内容可变图片（分享卡片等）文件名带时间戳（新内容=新 URL），`mediaUrl` 去掉版本号（原餐厅封面/推荐菜部分随模块二移除） |
| P1-3 NAS 数据备份 | **盘点结果：此前无任何备份**（未装 HBS3/HybridBackup、无快照计划、qsnapshot 配置为空） | `scripts/nas_backup.sh` + crontab 每日 04:15（deploy 幂等安装）：DB 容器内 sqlite backup API 一致性快照、media/快照/模型 rsync `--link-dest` 去重、wechat-notify 凭据一并覆盖，备份到**异池** zpool3（`/share/ZFS19_DATA/foodie-backups`，14 天 + `latest/`）；首跑已验证 integrity ok。**QNAP cron 坑（2026-08-21）**：crond 以 `-c /tmp/cron/crontabs`（tmpfs）运行，只改 `/etc/config/crontab` 任务不执行——必须 `crontab /etc/config/crontab` 安装进运行中 crond（deploy 脚本已固化） |

**部署侧连带修复（复盘验证时发现）**：
- compose 服务缺 `image:` 字段 → compose 默认镜像名 `foodie-foodie` 与 build 产物 `foodie:latest` 无关，**新代码构建后 up 永远不生效**；已显式 `image: foodie:latest`
- 本 NAS（Container Station 3.1.2 + QTS 5.2.8）buildkit 构建上下文挂载报 `error creating zfs mount`（手动 zfs create 正常，属 dockerd 侧问题）→ deploy 构建固定 `DOCKER_BUILDKIT=0` 走经典构建器

**验证**：本地冒烟（venv + 临时 DATA_DIR，订单合并/空车/下架/不存在菜品全路径 400/404 正确，重启迁移幂等）→ NAS 全量部署 → 线上 schema_migrations=1,2,3 → 真实下单（小炒黄牛肉×1+炝爆藕丁×2=¥114）微信通知 `sent` → 删除测试单。备份首跑 `integrity: ok`，去重生效（次日目录 14K）。

---

## 功能迭代记录（2026-08 · 第三批）

**A5 菜谱分享卡片**：详情页「📤 分享卡片」→ `POST /api/recipes/{id}/share-card` → `services/share_card.py` 用 PIL 合成竖向长图（750px 宽：品牌头/标题/封面/食材/步骤+配图/页脚日期），存 `media/share/{id}-{时间戳}.png`（新内容=新 URL，旧卡片自动清理）。手机长按保存发微信。依赖中文字体：本机 PingFang → 容器 wqy-microhei（Dockerfile 新增 `fonts-wqy-microhei fonts-noto-color-emoji`，同时修复 NAS 上封面生成中文豆腐块问题）。

**C1 订单状态机**：`orders.status`（迁移 v4：pending→making→served）。管理端点单记录「开始制作/上菜」，`POST /api/orders/{id}/status`；上菜时微信通知。用户端点单后本地轮询（8s，2h 上限），「已下单→制作中→已上菜」进度条；刷新页面后凭 `foodie_last_order`（localStorage）恢复轮询。

**C3 打印版菜单 PDF**：管理端「🖨 打印菜单」→ `GET /api/recipes/menu.pdf?origin=` → `services/menu_pdf.py`（reportlab，A4 双栏按分类分节 + 页脚扫码点餐二维码指向 `{origin}/#/order`）。中文字体：容器 wqy-microhei.ttc（TrueType）→ reportlab 内置 CID `STSong-Light`（本机 PingFang 为 CFF 字体 reportlab 不支持，已踩坑）→ Helvetica 兜底。依赖新增 `reportlab>=4.0`、`qrcode>=7.4`。

---

## 前端视觉统一（2026-08 · 第四批）

- **导航重构**：新增 `components/Icon.vue`（SVG stroke 图标库，替代原 emoji，跨端渲染一致）；桌面玻璃顶栏与手机底部悬浮 Tabbar 共用同一套「active 判定」（按 route.name + query.status 精确匹配），修复「菜谱库/草稿箱」双高亮 bug；手机 Tabbar 激活项为品牌渐变胶囊
- **设计系统增强**：容器放宽到 1200px、`--skeleton` 骨架屏 shimmer、`.page-title/.page-sub` 统一页面标题、毛玻璃（backdrop-filter）角标/操作钮、聚焦描边统一
- **页面细节**：列表卡片角标重排（草稿/菜单中毛玻璃小标签左上角，上架操作改图标钮右上角，桌面/手机一致）；菜单「想吃」毛玻璃胶囊 + 激活渐变；详情页步骤图圆角、meta 图标化；点餐页分类栏毛玻璃吸顶、购物车深色渐变条；微修：分类 chip、购物车/清空/上菜等操作性 emoji 全部 SVG 化（仅正文语义 emoji 保留）；**移动端菜单页头部修正（2026-08-21）**：桌面「标题左+按钮右」一行式布局在窄屏错位，移动端改竖排（标题一行、打印/扫码两按钮等宽一行），想吃胶囊加深对比度

---

## 点餐页视觉升级（2026-08 · 第五批）

`/#/order` 整页重做为「手机点餐 App」风格（520px 居中列，手机全宽）：
- **Hero 渐变头**：品牌橙红渐变 + 漂浮光斑动画（blur 圆斑）、毛玻璃 logo 徽章、日期/道数副标题、已选数量弹出徽章
- **交互动效**：菜品卡片交错入场（rise + stagger）、分类胶囊渐变激活态、加号点击涟漪 + 数字弹跳（:key 重放动画）、已点卡片橙边高亮
- **购物车**：深色渐变悬浮胶囊条（购物车角标弹跳、金额实时）、底部抽屉弹层（transition sheet）、下单按钮流光扫过（shine）
- **订单进度**：渐变进度条 + 圆点从灰色渐变激活 + 当前阶段脉冲呼吸；**上菜时 canvas 撒花动画**
- 全页无新增依赖（纯 CSS 动画 + 60 行 canvas 撒花）
