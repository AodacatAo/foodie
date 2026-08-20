# 🍜 食集 · 综合美食 Web

本地部署的个人美食库，三大模块：

1. **菜谱** —— 小红书链接/手动内容导入，自动提炼「食材 + 步骤」
2. **餐厅** —— 大众点评抓取 + 收藏/评分/距离/就餐记录
3. **菜单 · 点餐** —— 上架菜谱成菜单，定价分类，手机扫码点餐（美团式），下单微信通知

架构设计见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

## 部署（推荐：NAS 常驻）

项目以 Docker Compose 部署在 QNAP NAS 上常驻运行（局域网访问，7x24）：

```bash
NAS_PASS='<NAS密码>' python3 scripts/deploy_qnap.py all
```

- 局域网访问：`http://<NAS-IP>:8080`（免登录）
- 数据（数据库/图片/登录态/微信凭据）全部在 NAS 数据卷，**部署只更新代码、绝不覆盖线上数据**
- 配置安全：`.env`（含 API Key/令牌）只存在于 NAS 宿主机目录，运行时经 compose `env_file` 注入容器，**不打入镜像层**（.dockerignore 兜底排除）
- 容器 `restart: always` + 健康检查自动拉起
- 微信通知是**独立服务**（独立仓库 [wechat-notify](https://github.com/AodacatAo/wechat-notify)、独立 compose），按需单独部署，食集不含任何微信代码

## 本地开发运行

```bash
./scripts/start.sh
```

首次运行自动：构建前端 → 创建虚拟环境 → 安装依赖 → 启动（http://127.0.0.1:8080）。

### 配置（.env）

复制 `.env.example` 为 `.env` 并填写：

| 配置 | 说明 | 必需 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（菜谱提炼） | 建议 |
| `XHS_COOKIE` | 小红书登录 cookie（链接抓取） | M1 抓取时 |
| `ACCESS_TOKEN` | 访问密码（仅非局域网请求校验；目前无公网入口，防御性保留） | 否 |
| `HOST` / `PORT` | 服务地址 | 否 |
| `WECHAT_NOTIFY_URL` | 微信通知独立服务地址（下单时推送；服务部署见独立仓库 wechat-notify） | 否 |
| `NOTIFY_TOKEN` | 微信通知服务的鉴权令牌（与独立服务配置一致） | 配了通知时 |

## 功能

### 🍜 菜谱库
- **手动录入**：粘贴笔记正文 → LLM 提炼食材/步骤 → 草稿确认 → 入库
- **小红书链接抓取**：链接 → Playwright 登录态抓取 → 图片 OCR → LLM 提炼 → 草稿
- **视频菜谱**：Whisper 本地语音转写 + 提炼，详情页可播视频
- **搜索**：FTS 全文搜索（菜名/食材/步骤）+ 标签过滤 + 草稿箱

### 🍽 餐厅库
- **搜店添加**：按店名搜索（点评站内搜索 + 多引擎兜底）→ 一键添加（封面/人均/评分/坐标/推荐菜全自动）
- **推荐菜**：真实点评 CDN 图片自动抓取，可从详情页手动重新同步
- **筛选排序**：菜系/人均/我的评分/吃过与否/距离；按距离/人均/评分/最近吃过/次数
- **定位**：浏览器定位 + 常用位置（家/公司）+ 手动坐标；局域网 http 下自动降级网络定位
- **就餐记录**：卡片 +1 快速记录；详情页时间线（日期/照片/备注），可编辑、两步骤确认删除
- **我的评分**：5 星半星点击 + 0.1 精度输入

### 📋 菜单 · 点餐（模块三）
- **上架**：菜谱卡片右上角「🍽 上架 / ✓ 已上架」切换（删除移至详情页）
- **管理端**（`/#/menu`）：定价（点击内联编辑）、分类（预设热菜/凉菜/汤/主食/小吃/饮品/甜品 + 自定义）、点单记录（下单人/明细/合计/删除）、生成扫码二维码
- **用户端**（`/#/order`，扫码直达）：美团式点餐——分类栏过滤、菜品卡片（图/名/价）、圆形 +/- 份数控件、底部购物车（已点清单/份数/总合计/清空）、填名字「✔ 下单」；**无任何管理入口**（隐藏导航、无定价、无做法预览）
- **购物车本机化**：购物车存在每台设备自己的 localStorage（`foodie_cart_v1`），多台手机同时点餐互不干扰；下单时服务端按当前菜单校验并以服务端价格快照（防篡改）
- **管理端「想吃」**：勾选「今天想吃」置顶并合计预算（纯意愿标记，与用户端购物车解耦）
- **下单通知**：下单后 NAS 后端直接推送微信（iLink 官方协议，秒级送达，不依赖电脑）
- **通用微信通知**：下单时食集经 HTTP 调用独立的微信通知服务（**独立仓库/独立容器** `wechat-notify`，端口 8090，见其仓库 README）

## 数据

- SQLite（WAL）：`backend/data/foodie.db`；媒体 `backend/data/media/`
- 结构演进：版本化迁移（`backend/app/migrations.py` + `schema_migrations` 表），启动时自动按序执行未应用迁移
- 备份：`./scripts/backup.sh`（建议定期执行）；`backups/` 存历史快照

## 目录结构

```
backend/    FastAPI 应用（app/routers · app/services · app/models，data/ 运行时数据）
frontend/   Vue3 + Vite SPA（views/ 路由懒加载，dist/ 构建产物）
scripts/    start.sh 启动 · deploy_qnap.py NAS 部署 · backup.sh 备份
Dockerfile / docker-compose.yml   容器化部署（微信通知服务在独立仓库 wechat-notify）
```

## 版本库

- NAS Gitea：`nas-git:aodacat/foodie.git`（origin）
- GitHub：`github.com/AodacatAo/foodie`（**公开**，代码全量脱敏无任何敏感信息）

## 里程碑

- [x] M1 菜谱：CRUD + FTS + 小红书抓取（OCR/Whisper）+ 草稿确认
- [x] M2 餐厅：点评搜索/推荐菜真图/坐标/距离/就餐记录/评分
- [x] M3 菜单点餐：上架/定价/分类/扫码点餐/购物车/下单/微信通知
- [x] 基础设施：NAS 容器化部署、局域网访问、移动端适配、版本库双备份、微信通知独立服务
