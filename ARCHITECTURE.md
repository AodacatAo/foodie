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

# 模块二：美食收藏（餐厅库）

> 状态：v1 设计稿（2025）
> 目标：收藏爱吃的店；出门吃饭时按菜系/人均/评分/距离/吃过次数快速选店；每次吃完记录。

## 1. 核心决策（已与用户确认）

| 决策点 | 选择 |
|---|---|
| 数据录入 | **手动录入为主** + 大众点评抓取 spike 验证（可行再接入） |
| 平台优先 | 大众点评（菜系/人均/评分数据全） |
| 距离 | 浏览器定位 + 常用位置（家/公司）；距离前端本地计算显示 |
| 就餐记录 | 次数 + 日期 + 备注 + 实付人均 + 个人评分 |
| 定位技术 | haversine 距离；店铺坐标来自抓取数据或高德地理编码兜底 |

## 2. 数据模型

```sql
restaurants                          visit_logs
┌───────────────────────────┐        ┌────────────────────────────┐
│ id (PK)                   │        │ id (PK)                    │
│ name                      │        │ restaurant_id (FK, 级联删) │
│ cuisine       菜系         │        │ visited_at   日期          │
│ address                   │        │ note         备注          │
│ lat / lng     坐标         │        │ rating       个人打分 1-5   │
│ price_per_person 人均     │        │ cost_per_person 实付人均    │
│ rating        平台评分     │        │ created_at                 │
│ cover_image               │        └────────────────────────────┘
│ source_url / source_shop_id
│ source_platform  dianping/meituan/manual
│ tags JSON
│ status  draft/published    -- 抓取来的进草稿，手动录入直接发布
│ visit_count / last_visited_at  -- 冗余聚合，记录时更新
│ (FTS 冗余列: name/cuisine/address/tags_text)
│ created_at / updated_at
└───────────────────────────┘

user_locations（常用位置，少量固定点）
  id, name(如"家"/"公司"), lat, lng
```

**设计要点**：
- `visit_count` / `last_visited_at` 冗余在餐厅表，写 `visit_logs` 时事务内同步更新，列表排序免聚合查询。
- 删除餐厅时 `visit_logs` 级联删除（SQLite FK ON DELETE CASCADE）。
- 店铺坐标是距离功能的根基：抓取时从平台数据直接拿（点评数据含经纬度）；手动录入时可选高德地理编码 API 解析（需用户自备 key，可选功能）。

## 3. 距离与排序（前端本地计算）

- 个人量级（几百家店）列表接口一次返回全部 published 店，**前端本地**完成：
  - 当前位置：浏览器 `navigator.geolocation`（localhost 为 secure context 可用）→ 失败则用户手动输入/选择常用位置
  - 距离：haversine 公式（前端实现，~20 行）
  - 筛选：菜系 / 人均区间 / 评分下限 / 距离上限 / 是否吃过
  - 排序：距离 / 人均 / 评分 / 最近吃过 / 吃过次数
- 搜索仍走服务端 FTS（店名/菜系/地址），其余筛选排序全部本地。

## 4. 大众点评抓取 spike（可行性验证，先不承诺）

复用模块一的 Playwright 模式，验证目标：
1. 店页面是否含内嵌数据（`__INITIAL_STATE__` 或 SSR JSON）→ 店名/菜系/人均/评分/坐标/图
2. 点评反爬强度（滑块验证、x-signature 签名）是否影响无头抓取
3. 结论：可行 → 接入链接导入（草稿流）；不可行 → 保持手动录入兜底

风险与对策：点评反爬显著强于小红书，spike 失败属预期；手动录入表单（店名/菜系/人均/评分/地址）保证流程不依赖抓取。

## 5. API 设计

```
GET    /api/restaurants?q=&tag=&status=   列表（FTS 搜索 + 过滤，含坐标）
GET    /api/restaurants/{id}              详情（含最近 N 条就餐记录）
POST   /api/restaurants                   手动录入（直接 published）
PUT    /api/restaurants/{id}              编辑
DELETE /api/restaurants/{id}              删除（级联删记录）
POST   /api/restaurants/{id}/publish      草稿确认
GET    /api/restaurants/{id}/visits       就餐记录列表
POST   /api/restaurants/{id}/visits       记录一次 {visited_at, note, rating, cost_per_person}
DELETE /api/visits/{id}                   删除误记
GET    /api/restaurants/tags              标签聚合
GET/POST/PUT/DELETE /api/locations        常用位置
```

## 6. 前端页面

| 页面 | 功能 |
|---|---|
| 餐厅库 `/restaurants` | 筛选栏（菜系/人均/评分/距离/是否吃过）+ 排序（距离/人均/评分/最近吃过/次数）+ 卡片（封面、菜系、人均、评分、距离 km、吃过 N 次） |
| 餐厅详情 `/restaurant/:id` | 信息卡（地址/人均/评分/平台链接）、**就餐记录时间线**（日期/备注/评分/实付）、「🍽 记录一次」按钮、编辑/删除 |
| 录入 `/restaurant/new` | 手动表单；未来加点评链接导入 |
| 设置 `/settings` | 常用位置管理（家/公司，地图点选或经纬度输入） |

## 7. 里程碑

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **N1 骨架** | restaurants/visit_logs 模型 + CRUD + 手动录入 + 列表筛选排序（距离先用常用位置/手动位置） | 手动录入 3 家店，可按菜系/人均排序 |
| **N2 定位** | 浏览器定位 + haversine 距离显示排序 + 常用位置管理 | 打开页面自动显示"距当前位置 x.x km" |
| **N3 记录** | 就餐记录 + 次数聚合 + 时间线展示 | 记录 5 次后详情页时间线正确、列表显示"吃过 5 次" |
| **N4 spike** | 大众点评抓取验证（可选接入） | 结论文档：可行/不可行 + 证据 |
| **N5 打磨** | 前端打磨、README、备份覆盖新表 | 日常可用 |

## 8. 复用与扩展

- 复用模块一：FastAPI 单体结构、SQLite+FTS、Vue3 前端、Playwright 抓取模式、草稿确认流（抓取数据进草稿）
- 顶部导航新增「餐厅库」入口
- 可选增强（暂不做）：地图视图（Leaflet + OSM 免费瓦片）、随机推荐"今天吃什么"（结合次数/距离）

---

## 模块二 · 实施记录（N1-N5）

### 里程碑状态

| 阶段 | 状态 | 备注 |
|---|---|---|
| N1 骨架 | ✅ 完成 | 模型/CRUD/手动录入/筛选排序，冒烟测试通过 |
| N2 定位 | ✅ 完成 | 自动定位(静默失败可手动)/精度提示/距离筛选/详情页距离 |
| N3 记录 | ✅ 完成 | 记录一次(日期/评分/实付/备注)/时间线/次数聚合/统计(平均评分/实付) |
| N4 spike | ✅ 完成 | 点评匿名可抓封面/店名/评分/人均/菜系/地址；坐标不可靠 |
| N5 打磨 | ✅ 完成 | 加载态/空态/README/备份覆盖 |

### 大众点评抓取 spike 结论（2025）

**可行项**（匿名即可，无需登录）：
- 店铺页 `og:image` → **封面图**（p0.meituan.net CDN，可下载）
- 页面标题 → 店名（【】内）、菜系（"XX地区YY菜系团购"段）
- 页面文本 → 评分（★★★★★ 4.6）、人均（¥101/人）、地址（部分脱敏 xx路13******）
- 页面无验证码、无 IP 风险拦截（UA 伪装 + 无头 Chrome）

**不可行项**：
- 坐标：移动端页面不提供可靠坐标（lat/lng 请求参数恒为 0）；shopservice 接口参数复杂且非必需不请求
- 结论：**接入"链接→信息+封面"同步流**（`/api/restaurants/sync-info` + 编辑器一键抓取），坐标仍由用户提供或手动录入

**抓取流程**：编辑/录入时贴点评链接 → 点「🔄 从点评抓取」→ 预填店名/菜系/人均/评分/地址/封面 → 保存时封面下载到 `media/restaurants/{id}-{时间戳}.jpg`。

**媒体缓存策略（2026-08 修正）**：`/media` 响应带 `Cache-Control: immutable` 长缓存；封面/推荐菜这类**内容可换**的图片文件名带时间戳（新内容 = 新路径 = 新 URL，浏览器自动拉新），废除前端手工 `?v=N` 版本号；同步推荐菜前清空该餐厅旧图目录，避免孤儿文件累积。步骤图/上传图等**内容不变**的资源沿用稳定文件名。

### 封面策略（最终）
1. 点评链接抓取 → 点评封面图（优先）
2. 手动贴图片 URL → 下载
3. 都没有 → 本地自动生成（菜系渐变 + emoji + 店名），保证每店有图

### 访问方式（2025 迭代）

| 方式 | 地址 | 说明 |
|---|---|---|
| 本机 | http://127.0.0.1:8080 | 始终可用 |
| 局域网 | http://<电脑IP>:8080（启动时打印，设置页可查） | 服务监听 0.0.0.0；手机需同一 Wi-Fi |

**访问密码**：`.env` 配 `ACCESS_TOKEN` 后，**只有非局域网请求需要登录**（按 `Cf-Connecting-Ip` 判断真实客户端 IP，公网 IP 才要求密码）；局域网/本机直连一律免登录。登录一次 Cookie 有效 1 年（`POST /api/login`）。前端 401 时弹出登录遮罩。当前未接公网隧道，鉴权保持防御性保留。

**移动端**：≤768px 时顶部导航切换为底部 Tab 栏（菜谱/餐厅/导入/草稿/设置）；卡片两列、筛选栏两列、表单单列；局域网 http 下浏览器禁用 GPS → 按出口 IP 网络定位兜底（ipinfo.io → ip-api.com 双源）。

**已知坑**：
- `socket.getaddrinfo(本机.local)` 在部分网络会挂起 → `/api/net` 与 start.sh 用 `ipconfig getifaddr` + 线程超时
- macOS 防火墙首次会询问是否允许 Python 接收连接，需点允许；路由器开 AP 隔离会挡设备互访

### NAS 容器化部署（QNAP <NAS-IP>，常驻服务）

**结构**（`/share/ZFS2_DATA/foodie`）：
- `Dockerfile` + `docker-compose.yml`：`foodie`（应用，端口 8080，卷挂 `./data:/app/backend/data`；公网隧道已移除，仅局域网访问）
- 数据（DB/媒体/whisper 模型/浏览器登录态）全部在 `./data`，重建容器不丢
- **配置不进镜像（2026-08 安全加固）**：`.env` 只在 NAS 宿主机目录，compose `env_file` 运行时注入环境变量；Dockerfile 不再 `COPY .env`，`.dockerignore` 排除 `.env`——密钥不会固化在镜像层
- 镜像内 `playwright install chrome`（npmmirror 加速）满足 `channel="chrome"`；容器内 root 运行 → 爬虫启动参数 `chromium_sandbox=(os.geteuid() != 0)`

**部署**：`NAS_PASS='<nas密码>' python3 scripts/deploy_qnap.py all`（pack→upload→extract→build→up）。
- compose 显式 `image: foodie:latest`：build 阶段打 tag 后 `compose up -d` 能检测到镜像变化并自动重建容器（否则 compose 默认镜像名 `foodie-foodie` 与 build 产物无关，新代码永远不生效——2026-08 部署时踩坑后修正）
- QNAP 未启用 SFTP 子系统 → 上传走 SSH exec 通道流式 tar
- docker CLI 全路径 `/share/ZFS1_DATA/.qpkg/container-station/bin/docker`
- 数据库迁移用 sqlite `backup()` API 做一致性快照（服务器运行中也安全）
- **NAS 数据备份（2026-08 复盘后补上）**：此前 NAS 侧无任何备份机制（无 HBS3/HybridBackup、无快照计划）。现由 `scripts/nas_backup.sh` + crontab（每日 04:15，deploy 幂等安装）备份到异池 `/share/ZFS19_DATA/foodie-backups`（zpool3 ≠ zpool1，池级故障隔离）：DB 走容器内 sqlite backup API（运行中安全），media/snapshots/models 用 rsync `--link-dest` 与上一份硬链接去重（跨池不能硬链接源文件，去重只发生在目标池内），wechat-notify 凭据一并覆盖，保留 14 天 + `latest/` 软链
- **数据库结构演进（2026-08）**：版本化迁移 `backend/app/migrations.py` —— `schema_migrations` 表记录已应用版本，启动时事务内按序执行未应用项；约定「只增不改」、回填用 NULL/默认值守卫、每个迁移只执行一次（全新建库重放无害）。新增列/回填一律走迁移，废除 init_db 手工补丁式 `_add_column_if_missing`
- 登录态与数据迁移后，Mac 端服务应停止，避免两份数据分叉

**访问**：局域网 `http://<NAS-IP>:8080`（免密）。公网访问已移除（2026-08）；如未来需要可重新引入内网穿透方案，鉴权中间件已保留（`Cf-Connecting-Ip` 判断 + `ACCESS_TOKEN`）。
- Mac 端不再常驻运行（避免双数据源）；临时用可 `./scripts/start.sh`，数据以 NAS 为准


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
| P1-2 媒体缓存 | 前端 `?v=3` 手工版本号，改图忘 bump 就显示旧图 | 封面/推荐菜文件名带时间戳（新内容=新 URL），`mediaUrl` 去掉版本号；同步推荐菜前清空旧图目录 |
| P1-3 NAS 数据备份 | **盘点结果：此前无任何备份**（未装 HBS3/HybridBackup、无快照计划、qsnapshot 配置为空） | `scripts/nas_backup.sh` + crontab 每日 04:15（deploy 幂等安装）：DB 容器内 sqlite backup API 一致性快照、media/快照/模型 rsync `--link-dest` 去重、wechat-notify 凭据一并覆盖，备份到**异池** zpool3（`/share/ZFS19_DATA/foodie-backups`，14 天 + `latest/`）；首跑已验证 integrity ok |

**部署侧连带修复（复盘验证时发现）**：
- compose 服务缺 `image:` 字段 → compose 默认镜像名 `foodie-foodie` 与 build 产物 `foodie:latest` 无关，**新代码构建后 up 永远不生效**；已显式 `image: foodie:latest`
- 本 NAS（Container Station 3.1.2 + QTS 5.2.8）buildkit 构建上下文挂载报 `error creating zfs mount`（手动 zfs create 正常，属 dockerd 侧问题）→ deploy 构建固定 `DOCKER_BUILDKIT=0` 走经典构建器

**验证**：本地冒烟（venv + 临时 DATA_DIR，订单合并/空车/下架/不存在菜品全路径 400/404 正确，重启迁移幂等）→ NAS 全量部署 → 线上 schema_migrations=1,2,3 → 真实下单（小炒黄牛肉×1+炝爆藕丁×2=¥114）微信通知 `sent` → 删除测试单。备份首跑 `integrity: ok`，去重生效（次日目录 14K）。
