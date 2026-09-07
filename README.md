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
    0.30 × research_fit
  + 0.30 × novelty
  + 0.20 × research_value
  + 0.10 × testability_feasibility
  + 0.10 × evidence_support
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

## 本地体验

在线 Pages 是只读界面。要自己点命令、跑模型或上传文件，按下面做。密钥只写在仓库根目录 `.env`，不要提交 git，也不要写进数据库 / event / SSE / 前端 bundle。`xxxx` 视为未填写。

### 最快路径：引导式配置

```bash
uv sync --all-groups
uv run rigora-setup
```

它在本机起一个一次性面板：先用五屏介绍五个 Agent 各自的职责和选模型的取舍，再让你多选供应商、填 key 与模型（官方 `BASE_URL` 已预填，可当场测试连通性），然后用卡片给 `idea_review` / `working_qa` / `complete` 各指一个模型，再把「方案生成」和「点睛之笔评分」按对配好（面板会同步说明 `low` / `mid` / `high` 三种模式各需几条路径），最后给出文献检索等可选项。确认后写入 `.env`（权限 `600`，只更新它管理的键，保留你已有的注释和其它配置），进程随即退出。

面板一家供应商只展示一个槽——key 填一次，需要多条并行路径时在配对里复用它。面板只监听 `127.0.0.1` 的随机端口，地址带一次性 token；已保存的密钥只以掩码回显，不会明文出现在页面、日志或响应里。想改配置就重跑 `rigora-setup`，上一次填的内容会读回来。面板默认浅色主题，右上角可切深色。

### 本地不再有 demo 兜底

五个 Agent 必须全部分配到某个已配置的槽，否则 `build_container` 直接抛 `ConfigurationIncomplete` 并提示去跑 `rigora-setup`。只有显式写 `RESEARCH_MENTOR_MODEL_PROVIDER=demo` 才会使用固定 fixture 模型——那种情况下模型和文献都是 demo 数据，**不能当模型质量或检索质量的证据**。在线 Pages 的演示是纯前端的（`VITE_STATIC_DEMO`），与此无关。

### 各档目标要准备什么

| 目标 | 要什么 | 要不要额外下载 |
| --- | --- | --- |
| 用真实模型走完流程 | 至少一家 `API_KEY`，且五个 Agent 分配齐 | 不需要 |
| 方案生成与评分交叉互审 | 两家或以上，且**同一家**同时承担 `plan_loop` 和 `key_insight_check` | 不需要 |
| 想法审查用真文献 | 上一项，再填 OpenAlex key | 不需要下模型，但要申请 OpenAlex |
| 上传 PDF/Markdown 并按语义排序 | 上一项，再装 FlagEmbedding 并下载 reranker | **需要**，约 1–2GB |

### 环境

- Python `3.12` 与 [uv](https://docs.astral.sh/uv/)
- Node.js 20+（前端）
- 可选：PowerShell 7，用于 `scripts/dev.ps1` / `scripts/check.ps1`

### 1. 复制环境文件

```bash
cp .env.example .env
```

完整键名与注释在 `.env.example`。下面按「公共项 → 模型 → OpenAlex → RAG」说明含义和怎么填。

### 2. 安装并启动

```bash
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn research_mentor.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

另一个终端：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`。Vite 把 `/api` 代理到 `http://127.0.0.1:8000`。健康检查：`GET http://127.0.0.1:8000/api/v1/health`。

也可一次拉起 API 与 Vite：`pwsh -File scripts/dev.ps1`。

`RESEARCH_MENTOR_DEMO_MODE=true` 且数据库为空时，会 seed 三个 Demo 项目：`demo-project-planning`、`demo-project-working`、`demo-project-validation`。默认为 `false`，正式使用时不会往你的工作区灌示例数据。

### 3. 公共项

| 变量 | 含义 | 本地怎么填 |
| --- | --- | --- |
| `RESEARCH_MENTOR_DEMO_MODE` | `true`：空库 seed 三个 Demo；`false`：不自动灌 Demo | 默认 `false`。只想先看懂界面时可手工开，示例项目会标记 DEMO DATA。`rigora-setup` 不再展示这一项，也不会改写它 |
| `RESEARCH_MENTOR_DATABASE_URL` | 异步数据库 URL | 开发默认 SQLite：`sqlite+aiosqlite:///./research_mentor.db` |
| `RESEARCH_MENTOR_UPLOAD_ROOT` | 上传文件根目录 | 默认 `./data/uploads`（已 gitignore） |
| `RESEARCH_MENTOR_PUBLIC_BASE_URL` | 对外基址（导出链接等） | 本地 `http://localhost:8000` |

改数据库后重新执行 `uv run alembic upgrade head`。生产可改 **PostgreSQL**，例如 `postgresql+asyncpg://user:pass@host:5432/research_mentor`。Alembic 同步 URL 对 SQLite 是 `sqlite:///./research_mentor.db`。

### 4. 真实模型（可选）

这一节是手工编辑 `.env` 的参考；用 `rigora-setup` 的话这些都会被填好。

模板已写好千问 / Deepseek / ChatGPT / GLM 的官方 `BASE_URL`。**只改你要用的那一家**；`AGENTS` 留空的槽不会被调用，但五个 Agent 必须都被某个槽认领，否则启动报错。

每家五个字段（以千问为例，其它家把 `QWEN` 换成 `DEEPSEEK` / `CHATGPT` / `GLM`）：

| 变量 | 含义 |
| --- | --- |
| `RESEARCH_MENTOR_QWEN_API_KEY` | 商家密钥。占位 `xxxx` = 未填 |
| `RESEARCH_MENTOR_QWEN_BASE_URL` | 填到 `/v1`（或商家兼容前缀），**不要**带 `/chat/completions`。官方已在模板里；中转只改这一项 |
| `RESEARCH_MENTOR_QWEN_MODEL` | 模型名，如 `qwen3.7-plus`、`deepseek-v4-flash`、`gpt-5.6-terra`、`glm-5.3-flash` |
| `RESEARCH_MENTOR_QWEN_API_STYLE` | `chat_completions`：走 `openai_compatible` 的 `{BASE_URL}/chat/completions`；`responses`：走 OpenAI Responses API（ChatGPT 官方默认） |
| `RESEARCH_MENTOR_QWEN_AGENTS` | 这把 key 负责哪些 Agent，逗号分隔 |

`AGENTS` 可写：`idea_review`、`plan_loop`、`key_insight_check`、`working_qa`、`complete`，或 `all`。

- `idea_review` / `working_qa` / `complete` **只能出现在一个槽**。
- `plan_loop` 与 `key_insight_check` 的并行路径由 `RESEARCH_MENTOR_PLAN_CHECK_PAIRS` 显式给出，见下一节。
- 同一把 ChatGPT key 的第二个模型用 `CHATGPT_2_*`；其 key / `BASE_URL` / `API_STYLE` 留空则继承主槽。面板一家只展示一个槽，这个槽只留给手工编辑。

按 Agent 的任务特性选模型，同能力的可以替换。这份建议与 `rigora-setup` 面板里显示的是同一份数据（`setup_wizard/catalog.py`），模型名核对时间 2026-09-07：

| Agent | 吃什么能力 | 参考模型 |
| --- | --- | --- |
| `idea_review` | 读多篇文献摘要，吃长上下文，必须稳定输出 JSON | `deepseek-v4-flash` / `qwen3.7-plus` / `gpt-5.6-terra` |
| `plan_loop` | 一次生成较长的结构化方案 | `gpt-5.6-sol` / `deepseek-v4-pro` / `glm-5.3` |
| `key_insight_check` | 严格推理与稳定打分；建议换一家，避免自己写自己审 | `deepseek-v4-pro` / `gpt-5.6-sol` / `glm-5.3` |
| `working_qa` | 交互最频繁，优先便宜且快 | `gpt-5.6-luna` / `qwen3.8-flash` / `glm-5.3-flash` |
| `complete` | 综合多份实验结果做归纳 | `gpt-5.6-sol` / `deepseek-v4-pro` / `qwen3.8-max` |

两处已下线的旧模型名要避开：`deepseek-chat` / `deepseek-reasoner` 自 2026-07-24 起停用，旧请求直接报错；`gpt-4o` / `gpt-4.1` / `o4-mini` 已退役，`o3` 于 2026-08 下线。

#### 方案生成 × 点睛之笔评分的并行配对

`RESEARCH_MENTOR_PLAN_CHECK_PAIRS` 写成有序的 `提案槽>评审槽`，逗号分隔，最多 3 对。左边的槽必须挂 `plan_loop`，右边的槽必须挂 `key_insight_check`，不一致会在启动时报错而不是静默降级。

| 配几对 | 可用模式 | 路径怎么来 |
| --- | --- | --- |
| 1 对 | 仅 `low` | 就这一条。请求 `mid` / `high` 会返回 `plan_mode_unavailable`，而不是退化成同模型自审 |
| 2 对 | `low` / `mid` / `high` | 前两条按顺序配对，`high` 的第三条用 `RESEARCH_MENTOR_PLAN_CHECK_HIGH_CROSS` 指定的交错组合补齐（`ad` = 第一家提·第二家审，`bc` = 第二家提·第一家审） |
| 3 对 | `low` / `mid` / `high` | 每条路就是你写的一对 |

例如 `qwen>glm,deepseek>chatgpt` 配 `ad`，`high` 会跑「千问提·GLM审」「Deepseek提·ChatGPT审」「千问提·ChatGPT审」三条。同一对里尽量选不同厂商、能力相近的两个模型：不同厂商避免自己写自己审，能力相近才不会出现强模型压着弱模型改。

留空这一项则退回旧行为：按 ChatGPT → ChatGPT 第二槽 → 千问 → GLM → Deepseek 的顺序，取同时挂了两个 Agent 的槽轮转配对。

改完 `.env` 后重启 uvicorn。有凭据的真实 provider smoke 只在发布环境执行并记录 request id，结果不得提交进仓库。

### 5. OpenAlex 文献检索（可选，但真模型建议填）

Idea Review / 方案阶段的**真实文献**走 OpenAlex `/works`，不是本地模型。

**什么时候会打 OpenAlex？** 只要任意一家 `AGENTS` 非空，或 `model_provider` 不是 `demo`。此时再不填 key，请求仍可能发出，但 2026 年起无 key 额度极低，现场很容易被限流。

**怎么填：**

1. 打开 [openalex.org](https://openalex.org) 注册免费账户。
2. 到 [openalex.org/settings/api](https://openalex.org/settings/api) 复制 API key。
3. 写入 `.env`：

```bash
RESEARCH_MENTOR_OPENALEX_API_KEY=你的openalex_key
```

代码会同时带查询参数 `api_key` 与 `Authorization: Bearer`。免费 key 每天有额度，够本地演示。

`RESEARCH_MENTOR_OPENALEX_MAILTO` 是旧礼貌池字段。OpenAlex 已用 API key 取代 mailto，**可留空**；填了也会被服务端忽略。

未挂任何真实 Agent 时不会走 OpenAlex，用内置 demo 文献即可。

### 6. 文档 RAG / rerank（可选，默认不用下载）

这里的 RAG 只给**用户上传的项目文档**做 Working 阶段排序，和 OpenAlex 文献检索无关。

**默认不用下载。** 不装 FlagEmbedding、不拉权重，也能上传 `.txt` / `.md` / `.pdf`：Anydoc（`firecrawl-anydoc`，已在默认依赖）会解析；ranker 返回显式 `unavailable`，不伪造分数，Working 仍可回答。pytest 默认不加载权重。

**只有**你希望上传文档按语义（而不是词面）排序时，才下载 [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)（[FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding)）。权重约 1–2GB，写入 `./data/models`（已 gitignore）。

| 变量 | 含义 | 建议 |
| --- | --- | --- |
| `RESEARCH_MENTOR_RERANKER_BACKEND` | `auto`：装了就用 FlagEmbedding；`lexical` / `unavailable` 强制词面或关闭 | 保持 `auto` |
| `RESEARCH_MENTOR_RERANKER_MODEL` | Hub 模型 id | 保持默认 |
| `RESEARCH_MENTOR_RERANKER_CACHE_DIR` | 权重大盘目录 | `./data/models` |
| `RESEARCH_MENTOR_HF_ENDPOINT` | `mirror` / `modelscope` = [ModelScope](https://www.modelscope.cn/models/BAAI/bge-reranker-v2-m3)；`hf-mirror`；`official` | 国内用 `mirror` |
| `RESEARCH_MENTOR_HF_TOKEN` | 仅官网 Hugging Face token | 走 ModelScope 时留 `xxxx` |

国内下载（推荐）：

```bash
uv sync --extra local-ranking
uv run --extra local-ranking python -m research_mentor.cli.download_reranker --mirror
```

不要用 `hf-mirror.com` + 当前 `huggingface_hub` 1.29：跨域 308 会报 `FileMetadataError`。官网可 `--login --official`（[创建 token](https://huggingface.co/settings/tokens)），但国内通常仍慢。

### 上传限制

允许 `.txt` / `.md` / `.markdown` / `.pdf`（`text/plain`、Markdown MIME、`application/pdf`）。单文件默认 10 MB，单项目合计默认 100 MB。存储路径只用内部 project/document ID，原始文件名只进 metadata。解析失败保留原文件，允许 retry；已被证据引用的文档不可删除。

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
