# 下一名开发者交接文档

> 更新时间：2026-09-02
> 本文以 GitHub `main` 的当前实现为准。不要沿用历史交接文档中“Task 1–15”“main 仍是 v0.1”或“尚无 SQL/API”的旧结论。

## 1. 当前基线

- 仓库：`D:\A_main\arrogant_teacher\research_mentor_core`
- 团队统一分支：`main`
- backend Task 1–26 实现基线：`661c0c6`（`功能：加入可复现完整流程 Demo`）；Task 27 frontend foundation 随当前 `main` 提交。
- `main` 是唯一团队开发分支；`feature/full-product-v1` 仅作为落后于 `main` 的历史开发分支保留。
- implementation plan 共 32 个 Task；Task 1–28 已完成，Task 29–32 未完成。
- 当前 Python 全量测试基线：`438 passed`。
- 当前 Alembic head：`20260901_0005`。
- 当前已有 `frontend/` React 19/Vite/TypeScript 科研工作台；Task 28 frontend baseline 为 5 个 test files、27 tests，production build 通过。
- 2026-09-02 已审阅并同步外部最新版 `design_document/AI+ 创新大赛.md`；仓库副本保留全部内容，仅规范了行尾空白。Task 27–29 计划已补入新版前端约束。

开始工作前执行：

```powershell
Set-Location 'D:\A_main\arrogant_teacher\research_mentor_core'
git checkout main
git pull --ff-only origin main
git status --short --branch
git log --oneline -8
uv lock --check
uv run pytest -q -p no:cacheprovider
```

如果工作区存在未知修改，先阅读 diff；默认它们属于其他开发者，不得覆盖、删除或 reset。

## 2. 必读文档与裁决顺序

按以下顺序阅读和裁决：

1. `docs/design/2026-08-30-full-product-design.md`：v1.0 最高优先级规格；
2. `docs/superpowers/specs/2026-09-01-working-rag-and-control-design.md`：Working RAG、结果确认和用户控制增量裁决；
3. `docs/design/命名架构具体版.md`：结构化 Schema 与非流程图正文；
4. `docs/design/prompt仓库.md`：公共 Mentor Prompt 与五 Agent 固定 Prompt；
5. `docs/design/AI+ 创新大赛.md`：产品背景与前端要求；
6. `docs/superpowers/plans/2026-08-30-full-product-implementation.md`：Task 1–32 执行计划；
7. `docs/PROJECT_STATUS.md`：详细实现历史与当前缺口。

历史流程图不能覆盖高优先级设计中的明确 contract。固定 `prompt.md` 不得顺手修改；若确需修改，必须同步 Prompt hash contract 和 Eval。

## 3. 已完成范围

### Milestone A：Task 1–6

已完成 v1 domain contracts、ResearchContext/forward context、Complete/validation models、canonical session phase、Plan/Check round、权威评分和 validation queue。

### Milestone B：Task 7–12

已完成 repository/UoW/event/outbox ports、SQLAlchemy/Alembic、乐观并发、安全文件存储、OpenAlex adapter、document chunk retrieval 和可选 ranker。外部网络测试使用 mock。

### Milestone C：Task 13–16

已完成 async structured model port、OpenAI Responses adapter、OpenAI-compatible adapter、Idea Review 两阶段 RAG、Working contextual retrieval、context projection/budget/compaction。

Working 检索必须遵守已经确认的规则：

- query 拼接 normalized idea、research question/forward stage、current task/current experiment 与 question；
- rank score 只作为 diagnostics；
- v1 不按低分或空结果在模型前硬拒；
- Task 30 再使用标注集校准阈值。

### Milestone D：Task 17–21

已完成 Idea Review 路由、`low/mid/high` 多候选 Plan/Check、Working → result → Complete、validation/revision/writing 闭环、application command union、幂等与 phase/version guard、durable run lease/retry/cancel/recovery。

关键状态约束：

- Working `success` 只进入 `AWAITING_RESULT_RECORD`，不会直接完成 task；
- 用户提交结构化结果后才完成 task；`resume_working` 可返回 Working；
- forward 允许 `ResearchContext.plan=None`，不得反推虚假 plan；
- validation 结果必须先回 Complete；plan revision 可优先中断 pending queue；
- queued/completed/skipped/pending validation 按完整 task identity 去重；
- 用户等待状态没有 server timeout 或自动选择；
- 新 idea 使用显式 `restart_research(confirm_restart=True)`，运行中不能抢占。

### Milestone E：Task 22–26

已完成 FastAPI lifecycle、project/command/view API、文档上传与 parse job、journal JSON/Markdown export、public SSE、deterministic demo mode。

当前公开能力包括：

- `/api/v1/health`；
- project create/list/get 与 command endpoint；
- document upload/list/get/retry/delete；
- journal JSON/Markdown；
- project SSE replay/live polling/heartbeat；
- 三个 deterministic demo projects；
- SQL migrations 到 `0005`。

### Milestone F（部分）：Task 27–28

已建立 React 19/Vite/TypeScript、npm lockfile、Vitest、typed command union、`/api/v1` project/command client、稳定 `ApiError`、SSE public event cursor/去重 client，以及符合已确认视觉 tokens 的最小科研工作台 shell。`.gitignore` 已排除 `node_modules`、build 和 TypeScript 增量产物。

Task 28 已实现 desktop 三栏、14 个精确 phase 的结构化视图、五阶段 timeline、窄屏 project drawer/evidence sheet、证据 adopted/discarded filter、run trace、document/export panel、19999 字 composer 计数、server `allowed_commands` action dock、持续 Demo 标识、visible focus/reduced-motion，以及 panel 背景滚动锁定和 Escape 关闭。“傲娇”文案只存在于三项固定非实质 microcopy。当前卡片内容仍为 typed/static presentation；真实 project data、上传、SSE 和 command submit 属于 Task 29。

当前 backend `ProjectView` 只返回 project/title/domain/version/phase/is_demo/allowed_commands，尚未返回计划草案中设想的 `active_run` 与 `last_event_sequence`。Task 27 frontend types 忠实匹配当前 API；Task 29 接 run lock/SSE 恢复前必须先扩展后端 view contract 和测试，不能让前端猜测。

## 4. 必须如实理解的模型/API状态

当前没有真实模型 API 的成功调用记录，也没有提供或保存任何 API Key。

已经完成的是 adapter 与 contract：

- `OpenAIResponsesModelAdapter`：调用 Responses API structured output；
- `OpenAICompatibleModelAdapter`：调用兼容 `/chat/completions` 的 JSON Schema API；
- `DemoModelAdapter`：返回固定、通过生产 Pydantic Schema 的 deterministic fixture；
- adapter tests 使用 fake client/HTTP mock，不产生真实模型费用。

默认配置为：

```text
RESEARCH_MENTOR_MODEL_PROVIDER=demo
RESEARCH_MENTOR_DEMO_MODE=true
RESEARCH_MENTOR_MODEL_API_KEY=<未设置>
```

因此 `438 passed` 证明 deterministic/mock contract 正确，不证明真实 provider 可用。

此外，当前 composition root 仍存在重要运行时接线缺口：

- `AgentRunWorker` 在 `bootstrap.py` 中以 `handlers={}` 创建；
- `CommandBus` 的 production handler map 目前只注册 `cancel_run` 和 `restart_research`；
- 其余 Agent commands 尚未完整连接到五个 Agent runner、Harness transaction 和 durable worker；
- Task 23 的 HTTP contract 测试主要通过注入测试 handler 验证 API 行为。

所以目前不能宣称“用户 command → durable worker → 五 Agent → 真实模型 → 原子状态提交”的 production 链路已经跑通。下一名开发者必须把它列为显式修复项，最晚在 Task 29 完整用户操作接线前完成，并在 Task 32 有凭据的环境做真实 provider smoke test。不得用 demo success 代替真实 provider success。

## 5. 当前未完成任务

剩余 4 个 Task：

### Task 29：完整前后端操作接线

- 文件上传、SSE、command feedback、run status、retry/cancel；
- 所有主要用户操作从 UI 到 backend 闭环；
- 在此 Task 前后必须补齐 production command/worker/Agent handler wiring 缺口。

### Task 30：五 Agent Eval 与阈值校准

- 扩充五 Agent datasets 和统一 runner；
- 校准 Working RAG diagnostics threshold；
- 低分仍不能变回硬拒规则。

### Task 31：Playwright E2E 与 34 项验收

- 完整 demo E2E；
- desktop/narrow-screen、keyboard、focus、reduced-motion；
- 34 项 acceptance scenario 可追溯覆盖。

### Task 32：文档、quickstart 与 release audit

- 更新 README、环境变量、开发/生产命令；
- Python/frontend/Eval/E2E/build/migration/security gate；
- 有凭据时运行真实 provider smoke test，仅记录 request ID，不记录 secret；
- 没有凭据时明确标记该项未验证，不得伪造通过。

## 6. 前端视觉决策

前端规格已经确认，不需要重新发起设计讨论：

- 定位：严谨的科研判断与推进工作台，不是通用聊天工具；
- desktop 三栏：projects / structured research timeline / evidence；
- narrow screen：左栏 drawer、右栏 evidence sheet；
- palette：paper `#F7F3E8`、ink `#1F2A2A`、slate `#52605D`、mentor orange `#C65A2E`、rule `#D8D1C1`、evidence tint `#E9EFEA`；
- signature：细暖橙 research marginalia rail；
- 中文正文优先可读性，指标与代码使用等宽字体；
- 不使用大面积渐变、玻璃拟态、emoji 或无意义 dashboard 指标；
- keyboard、visible focus、reduced motion 和非颜色单一表达是硬性要求。
- 证据栏必须区分“检索到”和“本轮实际采用”，限制可见数量并支持 adopted/discarded 筛选；状态由 server view/event 驱动。
- 只有短状态和已校验自然语言允许 typewriter；结构化卡片、panel、选择项与 JSON 禁止逐字流式拼接。
- 刷新、SSE 重连和版本冲突后恢复 server state，同时按 project/phase 保留未提交 draft。
- Markdown 清理后再渲染，外链安全打开；panel 打开时锁背景滚动，composer 与 panel 不得同时可编辑。

## 7. 开发方法与验证

用户已要求降低额外审查消耗，后续采用精简策略：每个 Task 做 TDD 聚焦测试、一次全量回归、一次 diff/风险自检和独立 commit；只在 migration、并发、security 或 Milestone gate 使用额外审查。

Python：

```powershell
uv lock --check
uv run pytest -q -p no:cacheprovider
```

Frontend 建立后：

```powershell
Set-Location frontend
npm test -- --run
npm run build
```

Git：

```powershell
git diff --check
git status --short --branch
git show --check --stat --oneline HEAD
```

每个 Task 必须先 RED、再 GREEN、全量回归、独立 commit。不要提交 `.env`、API Key、数据库、上传文件、cache、venv、`node_modules` 或构建临时文件。

## 8. 下一步执行顺序

1. 从 `main` 拉取最新代码；
2. 运行 Python baseline，确认 `438 passed`；
3. 执行 Task 29，在完成 UI 操作的同时补齐 `ProjectView.active_run/last_event_sequence` 与 production command/worker/Agent wiring，并增加真实的 application journey tests；
4. 完成 Task 30–32；
5. 最终 release audit 必须把 demo/mock、real adapter contract、real provider smoke 三种证据分开汇报。

## 9. 完成定义

只有同时满足以下条件才能报告 v1.0 完成：

- Task 1–32 全部完成；
- 34 项验收场景有测试证据；
- Python、frontend、Eval、Playwright、build、migration 和 accessibility gate 全绿；
- production command → worker → Agent → Harness → persistence 链路真实接通；
- demo mode 与 real mode 使用同一公开 API contract；
- `docs/PROJECT_STATUS.md` 与 README 反映真实状态；
- 有凭据时完成真实 provider smoke test；无凭据时明确记录未验证；
- 工作区干净，不包含 secret 或本地产物。

从 Task 29 开始，不要重复实现 Task 1–28，也不要把 adapter/mock/demo 测试误报为真实外部 API 已联调。
