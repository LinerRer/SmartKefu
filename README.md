# SmartKefu · 智能客服系统

> 基于 RAG（检索增强生成）的 AI 智能客服系统：AI 自动应答为主、人工坐席兜底、工单可追踪，覆盖"知识库 → AI 多轮问答 → 转人工 → 工单 → 数据看板"完整闭环。

**开发状态**：v1.0 已完成　|　**技术方向**：AI 应用开发（RAG / Agent）

**核心指标**（真实评测）：检索 Hit@4 100%（18 正例）、负例拒识 2/2、pytest 47 用例全绿、首字响应 < 3s。评测可用 `backend/scripts/eval_retrieval.py` 复现。

---

## 项目简介

SmartKefu 面向中小企业在线客服场景，用企业自有知识库驱动 AI 自动回答产品、售前售后等标准化咨询，支持多轮对话与流式响应；当 AI 无法解答或用户主动要求时，可平滑转接人工坐席，无坐席在线时自动生成工单，全程数据可统计。

项目采用工程化、分层架构设计，重视**幻觉抑制、引用溯源、可观测性与可测试性**；本地以嵌入式 Qdrant + 本机 MySQL 全链路可运行，部署方案（Docker Compose + 云服务器）作为 v1.1 规划。

---

## 功能特性

- **AI 知识库问答（RAG）**：向量语义检索 + BM25 关键词检索，RRF 融合 + Rerank 重排
- **多轮对话**：滑动窗口记忆，支持上下文指代，流式（SSE）逐字输出
- **引用溯源与幻觉抑制**：答案标注来源，知识库无答案时不编造
- **意图识别与自动转人工**：识别业务咨询 / 闲聊 / 转人工 / 超范围，答不上自动转人工
- **人工坐席工作台**：WebSocket 实时收发、排队接入、查看 AI 历史、多会话接待
- **工单系统**：无人在线自动生成工单 / 留言，状态可流转、可追踪
- **知识库管理**：多知识库、PDF/DOCX/TXT/MD 上传解析分块、FAQ 管理、检索测试
- **数据看板**：会话量、AI 解决率、转人工率、响应时长、满意度
- **工程化**：JWT 鉴权 + 角色权限、限流、TTL 缓存、结构化日志（trace_id）、定时日报（APScheduler）、统一响应与异常
- **质量保障**：pytest 47 用例（服务层/纯逻辑/安全/HTTP 全链路/权限矩阵），测试库隔离；检索与对话效果评测可复现

---

## 技术架构

系统采用分层架构：接入层 → 接口层 → 业务服务层 → AI 能力层 → 数据层 → 基础设施层。

```
访客聊天窗口 / 管理端（Vue3 + Element Plus）
          │  REST · SSE · WebSocket
   FastAPI（统一响应/异常 · JWT · 限流）
          │
   对话 · RAG · 知识库 · 坐席 · 工单 · 统计
          │
   Embedding(bge-m3) · 混合检索 · Rerank · LLM(DeepSeek)
          │
   MySQL（业务）· Qdrant（向量，嵌入式本地运行）
          │
   本地全链路运行（Docker Compose 部署为 v1.1 规划）
```

> 详见 [docs/02-技术架构与技术栈.md](docs/02-技术架构与技术栈.md)。

---

## 技术栈

| 分类 | 技术 |
|---|---|
| 后端 | Python 3.11、FastAPI、Uvicorn、SQLAlchemy 2.0、Alembic、Pydantic、pydantic-settings |
| AI | DeepSeek、bge-m3（Embedding）、bge-reranker-v2-m3（Rerank）、openai SDK、rank_bm25 |
| 数据 | MySQL 8.0、Qdrant（嵌入式） |
| 实时 / 工程 | SSE（sse-starlette）、WebSocket、JWT、loguru、APScheduler、slowapi、pytest |
| 前端 | Vue 3、Vite、TypeScript、Element Plus、Pinia、Vue Router、Axios、ECharts |
| 文档解析 | PyMuPDF、python-docx |
| 部署 | 本地全链路运行；Docker Compose + Nginx 为 v1.1 规划 |

---

## 快速开始

### 环境要求

- Python 3.11（虚拟环境在项目根目录 `.venv/`）
- Node.js 18+（前端）
- MySQL 8.0（Windows 服务名 `MySQL`）、Qdrant（嵌入式本地运行，无需单独服务）

### 一键启动（推荐，Windows）

**方式一：双击（最简单）**

- 双击项目根目录的 **`start.bat`**：自动检查/启动 MySQL → 启动后端(8000) → 启动前端(5173) → 就绪后自动打开浏览器。
- 双击 **`stop.bat`**：一键停止前后端（MySQL 服务保持运行）。

启动后会弹出两个独立窗口（后端 uvicorn、前端 vite），运行期间请保持窗口打开；关闭窗口即停止对应服务。

**方式二：命令行**

```powershell
# 项目根目录执行
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1        # 启动
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1 -Stop  # 停止
```

脚本幂等：端口已被占用会自动跳过，重复执行无副作用；首次运行会自动安装前端依赖。

- 前端地址：`http://localhost:5173`（5173 被占用时自动切到 5174）
- 后端接口文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/v1/health`

<details>
<summary>手动分步启动（Linux/macOS 或想看清每一步）</summary>

### 后端

```bash
# 1. 在项目根目录创建并激活虚拟环境（.venv 位于根目录，与脚本一致）
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 2. 安装后端依赖
cd backend
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填写数据库、模型 API Key 等

# 4. 数据库迁移
alembic upgrade head

# 5. 启动服务
uvicorn app.main:app --reload
```

访问接口文档：`http://127.0.0.1:8000/docs`

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 运行测试

```bash
cd backend
# 测试库隔离：自动使用同 MySQL 实例的 smart_kefu_test 库
python -m pytest tests -v
```

### 效果评测

```bash
cd backend
python scripts/eval_retrieval.py   # 四配置 Hit@4 对比 + 负例拒识
```

> 部署：v1 采用本地全链路运行（嵌入式 Qdrant，无需 Docker）；容器化与云服务器上线列为 v1.1。

</details>

---

## 项目结构

```
smart-kefu/
├── README.md
├── start-dev.ps1 / start.bat / stop.bat   # 一键启动与停止
├── docs/                    # 需求分析 / 技术架构
├── backend/
│   ├── app/
│   │   ├── core/            # 配置、日志、安全、缓存、异常
│   │   ├── api/v1/          # 路由与依赖
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic 模型
│   │   ├── crud/            # 数据访问
│   │   └── services/        # 业务逻辑（含 rag 子模块）
│   ├── scripts/             # 评测脚本
│   ├── tests/               # pytest
│   ├── alembic/             # 数据库迁移
│   └── requirements.txt
└── frontend/
    └── src/                 # 视图、状态、路由、API 封装
```

---

## 文档索引

- [需求分析](docs/01-需求分析.md)
- [技术架构与技术栈](docs/02-技术架构与技术栈.md)

---

## 路线图（Roadmap）

**v1.0（已完成）**

- 工程地基（环境 / FastAPI / 数据库）
- RAG 核心（文档流水线 / 向量 / 混合检索 / AI 多轮对话）
- 业务闭环（转人工 / 工单 / 鉴权 / 前端 / 退出人工三路径）
- 数据看板 + 定时日报 + 测试评测

**v1.1（下一步）**

- Docker Compose 容器化 + 云服务器部署
- 超时计时器持久化（消息时间戳 + 巡检）
- 前端路由守卫

**v2.0（规划）**

- 多租户 SaaS 与计费
- 多渠道接入（微信 / 小程序 / 抖音）
- 语音能力
- 从人工会话中自动学习知识库

---

## 说明

- 项目中的性能/效果指标（Hit@4、解决率、首响时长）均来自真实评测与库内统计，可用 `backend/scripts/eval_retrieval.py` 与看板接口复现；开发期小样本指标已如实标注，不虚构；
- 所有密钥通过 `.env` 配置，不提交到代码仓库。
