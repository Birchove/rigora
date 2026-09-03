# Rigora

耐心严谨的个性化科研探索导师。**核心理念是用更严格、更具体的用户输入，换更优质、可核对的系统输出。** 面向 computer science 科研场景：审查研究想法、生成并修订方案、辅导实验过程、记录结果、选择补充验证，并整理写作方向。不代写论文、不替用户做实验。

**在线演示（GitHub Pages，只读）**：[https://birchove.github.io/rigora/](https://birchove.github.io/rigora/)

Pages 站点展示三个 seeded Demo 项目的界面，不跑 FastAPI / 真实模型。完整交互请按下方本地启动。

当前版本为 **v1**：full-stack Agent-oriented modular monolith。五个 Agent 只做一次结构化推理；Harness 独占状态流转、评分和用户确认 gate。前端通过 typed command、`ProjectView` 与 SSE 操作项目，不复制后端路由表。

产品截图（桌面三栏与窄屏 drawer/sheet）保存在 `frontend/tests/e2e/visual.spec.ts-snapshots/`。设计叙事图见 `docs/design/AI+ 创新大赛 -_ Rigora/`。

## 核心架构

```text
React / TypeScript frontend
        │ POST commands / GET views / SSE events
        ▼
FastAPI API + durable run worker
        ▼
Deterministic Harness ──► five Agent runners
        │
        └── SQL / OpenAlex / Anydoc / FlagEmbedding / model adapters
```

```text
用户输入
   │
   ▼
Idea Review ──forward──────────────► Working QA
   │ plan
   ▼
Plan Loop ◄──revision── Key Insight Check
   │ 用户确认                   │ pass
   ▼                            ▼
Working QA ──记录实验结果──► Complete
```

| Agent               | 职责                                                            |
| ------------------- | ------------------------------------------------------------- |
| `idea_review`       | 检索并审查用户想法，识别 `idea_type`，给出 plan、forward、clarify 或 reject 建议。 |
| `plan_loop`         | 生成研究方案，或根据用户反馈和检查意见修订 `ResearchPlan`。                         |
| `key_insight_check` | 评估“点睛之笔”的研究匹配度、新颖性、研究价值、可行性与证据支撑。                             |
| `working_qa`        | 围绕正在进行的实验提供问答与状态整理。                                           |
| `complete`          | 基于已经记录的实验结果给出下一项验证或写作方向。                                      |

Agent 不直接调用其他 Agent，也不能修改 session phase、循环次数或任务状态。

Harness 独占：routing 和状态转移；Check loop 次数；确定性评分与通过判定；用户确认 gate；task lifecycle、持久化与公开事件。

## 方案候选模式

`low/mid/high` 是 Harness 对现有 `plan_loop` / `key_insight_check` runner 的隔离编排，不新增 Agent 类型：

| 模式 | 候选路径 |
| --- | --- |
| `low` | 1 条（默认） |
| `mid` | 2 条 |
| `high` | 3 条 |

`RunPlanCommand.mode` 默认 low。`mid/high` 必须按 candidate ID 单选；`low` 可省略并指向唯一候选。必要条件 gate 因规则未定义而不实现。

## Check Agent 评分

Check Agent 只输出五项原始评分、理由和修订建议。Harness 按固定权重重新计算：

```text
final_score =
    0.20 × research_fit
  + 0.25 × novelty
  + 0.20 × research_value
  + 0.20 × testability_feasibility
  + 0.15 × evidence_support
```

加权结果先保留一位小数。通过条件为 `final_score >= 6.0`，且各维不低于下界：`research_fit >= 3.5`、`novelty >= 3.0`、`research_value >= 3.0`、`testability_feasibility >= 3.0`、`evidence_support >= 2.5`。权重与阈值集中在 `src/research_mentor/hyperparameters.py`。Working 检索分只作 diagnostics；低分或空结果不得在模型前硬拒。

## 产品边界与 v1 scope

产品**不替写代码/论文正文、不解决无关细碎问题**。也不替用户执行实验或编造结果。

v1 明确范围：

- 只辅导 computer science；非 CS 返回 `unsupported-domain`，不进入 Agent pipeline；
- 不自动生成完整论文正文；
- 不为上下文压缩或界面语气新增独立 Agent；边界提示保持中性，不改写评审结论；
- 无多租户账号、计费和组织权限；
- 非分布式微服务。

Demo 项目：`demo-project-planning`、`demo-project-working`、`demo-project-validation`。没有真实 provider 凭据时，只证明 deterministic demo / mock contract，不证明真实模型质量。

## 环境要求

- Python `3.12` 与 [uv](https://docs.astral.sh/uv/)
- Node.js 20+（前端）
- 可选：PowerShell 7，用于 `scripts/dev.ps1` / `scripts/check.ps1`

复制 `.env.example` 为 `.env`。API key 只从环境读取，不得写入数据库、event、SSE 或前端 bundle。

## Demo 快速开始

默认各商家 `AGENTS` 留空（`model_provider=demo`）且 `RESEARCH_MENTOR_DEMO_MODE=true`，不需要 API key。API 进程的 lifespan 会启动 durable worker，并在空库时 seed 三个 demo 项目。

```powershell
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn research_mentor.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

另一个终端：

```powershell
Set-Location frontend
npm install
npm run dev
```

或一次启动 API worker 与 Vite：

```powershell
pwsh -File scripts/dev.ps1
```

浏览器打开 `http://127.0.0.1:5173`。Vite 将 `/api` 代理到 `http://127.0.0.1:8000`。健康检查：`GET http://127.0.0.1:8000/api/v1/health`。

## 真实模型配置

复制 `.env.example` 为 `.env`。千问 / Deepseek / ChatGPT / GLM 各填：API key、`BASE_URL`、模型名、`API_STYLE`、覆盖的 Agent 列表。`plan_loop` 与 `key_insight_check` 可以同时写在多家下面，`high/mid/low` 按 ChatGPT→千问→GLM 做 3/2/1 路交叉审查。同一把 ChatGPT key 的第二个模型用 `CHATGPT_2_*`（key/url/style 留空则继承主槽）。官方 URL 已写在模板里；中转改 `BASE_URL` 并把 `API_STYLE` 设为 `chat_completions`。未分配的 Agent 走 demo。

```powershell
$env:RESEARCH_MENTOR_QWEN_API_KEY = "<your-key>"
$env:RESEARCH_MENTOR_QWEN_BASE_URL = "https://your-relay.example/v1"
$env:RESEARCH_MENTOR_QWEN_MODEL = "qwen-plus"
$env:RESEARCH_MENTOR_QWEN_API_STYLE = "chat_completions"
$env:RESEARCH_MENTOR_QWEN_AGENTS = "idea_review,plan_loop,key_insight_check,working_qa,complete"
$env:RESEARCH_MENTOR_DEMO_MODE = "false"
```

`API_STYLE=responses` 走 OpenAI Responses API；`chat_completions` 走 `openai_compatible` 的 `{BASE_URL}/chat/completions`。有凭据的真实 provider smoke 只在发布环境执行并记录 request id，结果不得提交进仓库。

## 文献、解析与可选排序

- **OpenAlex**：真实文献检索走 `/works`。免费账户 API key 用 `RESEARCH_MENTOR_OPENALEX_API_KEY`（查询参数 `api_key` 与 `Authorization: Bearer`）；礼貌池可另设 `RESEARCH_MENTOR_OPENALEX_MAILTO`。未设置 key / mailto 仍可请求，但额度与限流更严。
- **Anydoc**：`firecrawl-anydoc` 已在默认依赖中。纯文本 / Markdown 走 `PlainTextParser`；PDF 等在线程池中转为规范 Markdown。
- **FlagEmbedding**：项目上传文档的 Working RAG rerank，使用 [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)（[FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding)）。权重约 1GB，下载到 `./data/models`（已 gitignore）。国内请走 [ModelScope](https://www.modelscope.cn/models/BAAI/bge-reranker-v2-m3)：Hugging Face token 只能提高官网限额，不能加速国内链路；`hf-mirror.com` 在 `huggingface_hub` 1.29 上会因跨域 308 报 `FileMetadataError`。

```bash
uv sync --extra local-ranking
uv run --extra local-ranking python -m research_mentor.cli.download_reranker --mirror
```

官网下载可登录（[创建 token](https://huggingface.co/settings/tokens)）：

```bash
uv run --extra local-ranking python -m research_mentor.cli.download_reranker --login --official
```

也可在 `.env` 写 `RESEARCH_MENTOR_HF_ENDPOINT=mirror`。未安装或权重缺失时 ranker 返回显式 `unavailable`，不伪造分数，Working 仍可回答。pytest 默认不加载权重。

## 数据库

开发默认 **SQLite**：`sqlite+aiosqlite:///./research_mentor.db`（Alembic 同步 URL 为 `sqlite:///./research_mentor.db`）。生产可改 **PostgreSQL** 异步 URL，例如 `postgresql+asyncpg://user:pass@host:5432/research_mentor`。变更后重新执行 `uv run alembic upgrade head`。

## 文件限制

上传根目录默认 `./data/uploads`。允许 `.txt` / `.md` / `.markdown` / `.pdf`（对应 `text/plain`、Markdown MIME、`application/pdf`）。单文件默认 10 MB，单项目合计默认 100 MB。存储路径只使用内部 project/document ID，原始文件名只进 metadata。解析失败保留原文件，允许 retry；已被证据引用的文档不可删除。

## API 与 SSE contract

前缀 `/api/v1`。错误统一为 `{ "error": { "code", "message", "retryable", "details" } }`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 进程与 provider 探活 |
| `POST` | `/projects` | 创建项目 |
| `GET` | `/projects` | 列出项目 |
| `GET` | `/projects/{project_id}` | 聚合 `ProjectView`（含 `allowed_commands`、`active_run`） |
| `POST` | `/projects/{project_id}/commands` | discriminated command；Agent 命令 `202 + run_id`，确定性命令 `200 + view` |
| `POST/GET/DELETE` | `/projects/{project_id}/documents` | 上传、列表、详情、retry、未引用删除 |
| `GET` | `/projects/{project_id}/events` | SSE，`text/event-stream` |
| `GET` | `/projects/{project_id}/journal.json` | 权威研究日志 |
| `GET` | `/projects/{project_id}/journal.md` | 由 JSON 派生的 Markdown |

Command 必须带 `command_id` 与 `expected_version`。SSE 用递增 sequence；重连取 `Last-Event-ID` 与 query `after` 的较大值，心跳不写入 domain event。前端不得猜测 routing，只渲染服务端 `allowed_commands`。

## 测试矩阵

```powershell
uv lock --check
uv run alembic upgrade head
uv run pytest -q -p no:cacheprovider
Set-Location frontend
npm test -- --run
npm run build
npm run e2e -- --project=chromium
```

或：

```powershell
pwsh -File scripts/check.ps1
```

| 层 | 命令 | 覆盖 |
| --- | --- | --- |
| Python | `uv run pytest -q -p no:cacheprovider` | domain / Agent / Harness / API / 34 项验收矩阵 |
| Eval | `uv run pytest -q -p no:cacheprovider tests/evals` | 五 Agent 与 RAG 阈值；`provider_mode=demo` |
| Frontend | `npm test -- --run` 与 `npm run build` | 组件与 production bundle |
| E2E | `npm run e2e -- --project=chromium` | demo 全路径、forward、validation、recovery、a11y、security、visual |

## 项目目录

```text
.
├── src/research_mentor/   # agents、domain、harness、application、api、adapters
├── frontend/              # React 19 / Vite / Playwright
├── tests/                 # 合同、集成与验收测试
├── evals/                 # versioned EvalSuite JSON
├── migrations/            # Alembic
├── scripts/               # dev.ps1、check.ps1
├── docs/design/           # 产品设计、Prompt、命名架构
├── pyproject.toml
└── uv.lock
```

## 设计文档

- [docs/design/2026-08-30-full-product-design.md](docs/design/2026-08-30-full-product-design.md)：v1.0 完整规格
- [docs/superpowers/specs/2026-09-01-working-rag-and-control-design.md](docs/superpowers/specs/2026-09-01-working-rag-and-control-design.md)：Working RAG 与用户控制增量
- [docs/design/prompt仓库.md](docs/design/prompt仓库.md)：公共 Mentor Prompt 与五个 Agent Prompt
- [docs/design/命名架构具体版.md](docs/design/命名架构具体版.md)：Input/Output Schema 与 Harness
- [docs/design/AI+ 创新大赛.md](docs/design/AI+%20创新大赛.md)：产品背景与前端要求
- [docs/superpowers/plans/2026-08-30-full-product-implementation.md](docs/superpowers/plans/2026-08-30-full-product-implementation.md)：32 项实施计划
- [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)：实现交接状态

若历史流程图与当前代码或结构化 Schema 存在冲突，以完整产品设计、Working RAG 规格、当前 contracts 和测试为准。
