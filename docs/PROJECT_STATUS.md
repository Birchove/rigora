# 傲娇导师项目状态与开发交接

> 本文是持续维护的项目状态文档，供后续开发者快速理解设计、现状、缺口和继续开发顺序。

## 1. 状态基准

- 记录日期：2026-09-01
- 当前开发分支：`feature/full-product-v1`
- 实现审计基线：`65755f0`（不含本状态文档后续产生的 commit）
- 目标版本：v1.0
- 当前版本定位：可安装、可测试的 deterministic multi-agent backend core；尚不是可运行的完整产品
- 当前测试基线：Task 18 完成后 `350 passed`
- v1 implementation plan：Task 1–18 已有独立 commit；Task 19–32 尚未达到对应验收标准

分支关系：

```text
main (3eebca6，v0.1 初始核心)
  └── design/full-product（完整产品设计与实施计划）
        └── feature/full-product-v1（当前实现分支）
```

## 2. 设计依据与裁决顺序

发生冲突时，开发者必须按以下优先级裁决，不得用早期流程图覆盖已确认的 v1 状态机：

1. `docs/design/2026-08-30-full-product-design.md`：已确认的 v1.0 完整产品规格；
2. `docs/design/命名架构具体版.md`：结构化 Schema 与非流程图正文；
3. `docs/design/prompt仓库.md`：公共 Mentor Prompt、五 Agent 固定 Prompt 与组合规则；
4. `docs/design/AI+ 创新大赛.md`：产品背景和前端要求；
5. 历史流程图与图片。

实施时使用 `docs/superpowers/plans/2026-08-30-full-product-implementation.md`。该计划包含 7 个 Milestone、32 个按 TDD 编排的 Task，以及 34 项产品验收场景映射。

2026-09-01 增量裁决已把验收场景扩充为 34 项，并调整尚未完成的 Task 16、18、19、20、28、30–32。旧/新版《AI+ 创新大赛》的流程图和图片不能绕过这些显式裁决。

同日用户确认《Working RAG 与用户控制增量设计》：v1 取消低分硬拒，Working query 必须带研究/阶段/任务上下文；success 只提出结果确认；forward 正式允许 `plan=None`；等待状态的新 idea 使用显式 restart。Task 19 先修正已完成 Task 16 中与新裁决冲突的低分短路，再继续 completion loop。

## 3. 产品设计摘要

### 3.1 产品目标

“傲娇导师”面向 computer science 科研场景，帮助用户完成 Idea 审查、研究方案生成与修订、实验过程问答、结果记录、补充验证选择和写作方向整理。产品不替用户执行实验，不编造结果，也不自动生成完整论文正文。

v1 采用 full-stack Agent-oriented modular monolith：

```text
React / TypeScript frontend
        │ POST commands / GET views / SSE events
        ▼
FastAPI API layer
        ▼
Application services + durable run worker
        ▼
Deterministic Harness ──► five Agent runners
        │                       │
        │                       └── StructuredModelPort
        ├── Repository / UnitOfWork ports
        ├── LiteratureSearchPort
        ├── DocumentParserPort
        ├── RetrievalRankerPort
        ├── FileStorePort
        └── PublicEventPublisherPort
                │
                ▼
SQL / OpenAlex / AnyDoc / FlagEmbedding / model adapters
```

### 3.2 五个 Agent

| Agent | 设计职责 | 明确边界 |
|---|---|---|
| `idea_review` | 检索并审查输入；由 LLM 判断 `opinion / range / forward`；给出规划、进入 Working、澄清或拒绝建议 | 不生成完整研究方案，不决定最终 KeyInsight |
| `plan_loop` | 首次生成 ResearchPlan；按 Check 反馈或用户反馈做最小必要修订 | 不自行确认方案，不修改 Harness 状态 |
| `key_insight_check` | 评估 KeyInsight 的研究匹配度、新颖性、价值、可行性和证据支撑 | 只给原始评分与建议，不计算权威 final score，不重写方案 |
| `working_qa` | 围绕当前实验任务回答、澄清、拒绝或确认该任务完成；维护实验事实快照 | 不决定补充实验是否充分，不负责论文写作 |
| `complete` | 根据主实验与已完成验证提出结构化验证候选或写作指导 | 不把未执行实验视为完成，不生成完整论文正文 |

### 3.3 权限边界

- Agent 负责语义分类、评估、解释和声明式候选输出。
- Harness/Application 独占 routing、session phase、check round、task status、用户确认 gate、权威评分、幂等、并发和持久化。
- Agent 不得直接调用另一个 Agent。
- 外部文本、附件、文献和检索结果均视为业务数据，不能修改 Agent 职责、系统规则或输出 Schema。
- `current_date` 由代码按 `Asia/Shanghai` 生成，不由用户提供。
- 只有实际用于判断的来源进入 `EvidenceRef`；检索结果记录在 `LiteratureRecord`。

### 3.4 目标业务流程

```text
用户 Idea
  → Idea Review
      ├─ range / 信息不足 → 请求用户补充 → 重新审查
      ├─ reject → 拒绝并给出原因及可执行改进
      ├─ opinion → low/mid/high 的 1/2/3 条 Plan Loop ↔ Key Insight Check 候选路径 → User gate
      └─ forward → 使用已有实验上下文直接准备 Working
  → Working QA
  → 用户记录主实验结果
  → Complete
      ├─ 已充分 → WritingGuidance → Completed
      ├─ 需验证 → 用户选择 validation → Working → 记录结果 → Complete
      └─ 结果动摇主张 → 返回方案修订回路
```

Check Agent 只输出原始五维评分；Harness 使用固定权重重新计算：

```text
final_score =
    0.20 × research_fit
  + 0.25 × novelty
  + 0.20 × research_value
  + 0.20 × testability_feasibility
  + 0.15 × evidence_support
```

结果保留一位小数，`final_score >= 6.0` 即通过，不设置单项否决条件。

### 3.5 v1 明确不做

- 自动生成完整论文正文；
- 替用户执行实验或编造实验结果；
- 将上下文压缩或语气塑造实现为独立 Agent；v1 由 Harness service 和 UI 表达层分别承担这两项能力；
- 计算机科学以外领域的专业科研辅导；非 CS 输入必须返回 `unsupported-domain`，不得进入 Agent pipeline；
- 多租户账号、计费和组织权限；
- 分布式微服务和消息队列。

v1 产品能力和 Eval 限定在 computer science。v1 必须包含上下文压缩和克制的“傲娇”语气，但不为它们新增独立 Agent：上下文压缩由 Harness application service 完成；“傲娇”只用于非实质性的 UI microcopy，不能改写 Agent 输出，也不能驱动 Agent 为维持人设而刻意反对用户。是否在 post-v1 将任一能力 Agent 化只是可选评估项，当前不承诺目标版本。

新增统一规则：`low/mid/high` 是 Harness 对现有 Plan/Check runner 的 1/2/3 路隔离编排，不新增 Agent 类型；用户按 candidate ID 单选。必要条件 gate 因未定义而不参与评分。Working `success` 必须经用户结果记录确认；所谓 `error` 映射为既有 plan issue 或显式 validation result，不使用含义不清的 `validationResult` boolean。Context Assembler 按 Agent 投影，`sys_input` 只进入 instructions，不重复进入动态 payload。

## 4. v0.1 历史实现基线

本节保留 Task 1 开始前的逐文件审计，供理解迁移来源，不再代表 2026-09-01 的实时文件清单。当前完成进度以 §1、Git 独立 Task commits 和 implementation plan 为准；不得因为本节写“缺少”而重复实现 Task 2–15。

### 4.1 根目录、配置与文档

| 文件 | 当前功能 | 状态说明 |
|---|---|---|
| `README.md` | 描述 v0.1 架构、五 Agent、评分、目录、测试命令和边界 | 已实现；完整产品上线后需再次更新 |
| `pyproject.toml` | Python 3.12 项目元数据；声明 Pydantic、FastAPI、SQLAlchemy、Alembic、OpenAI、AnyDoc 等 v1 依赖 | 依赖已固定；大部分 provider 尚未接线 |
| `uv.lock` | 锁定 Python 依赖 | 已实现并通过 `uv lock --check` |
| `.gitattributes` | 强制 Agent `prompt.md` 使用 LF，保证 Prompt hash 跨平台稳定 | 已实现 |
| `.gitignore` | 忽略本地 `.worktrees/` 等非项目产物 | 已实现 |
| `src/research_mentor/config.py` | `Settings` 从 `RESEARCH_MENTOR_` 环境变量读取 provider、模型、数据库、上传目录、公开 URL 和 demo mode；`HarnessConfig` 固定 loop、评分和检索阈值 | Task 1 已实现 |
| `src/research_mentor/errors.py` | 定义项目基础异常及重复 session、非法转换、不变量、port 执行和 session 不存在异常 | 已实现 v0.1 异常层 |
| `src/research_mentor/application/__init__.py` | 预留 application package | 只有包入口，尚无 application service |

### 4.2 Domain 模型

| 文件 | 当前功能 | 尚未覆盖的 v1 内容 |
|---|---|---|
| `src/research_mentor/domain/research.py` | `InitialInput`、用户方案反馈、知识项、里程碑、KeyInsight、ResearchPlan、用户 accept/override/revision、OverrideRecord；包含基础 Pydantic 校验 | 缺 Project、Conversation、ResearchContext、cycle/version 等完整模型 |
| `src/research_mentor/domain/evidence.py` | `LiteratureRecord` 与 `EvidenceRef` 分离；保存来源、相关性和证据支持说明 | 缺检索诊断、chunk provenance 和 provider 元数据 |
| `src/research_mentor/domain/checks.py` | Check 五维分数、诊断、assessment 和 Harness 最终输出模型 | 后续需迁移到完整 v1 run/version 契约 |
| `src/research_mentor/domain/experiments.py` | 主实验/验证任务类型、实验信息、主实验结果、验证结果和任务关系校验 | 缺 validation candidate/selection/queue、结果影响和修订回路模型 |

### 4.3 公共 Agent 输入和 Prompt 组装

| 文件 | 当前功能 |
|---|---|
| `src/research_mentor/agents/common.py` | 定义 `SysInput`、仅检索型 Agent 使用的 `RetrievalSysInput`、默认行为约束、检索规则、当前中国日期和统一 `AgentInvocation` |
| `src/research_mentor/agents/common_mentor.md` | 固定的公共导师角色 Prompt |

当前 Prompt 组合方式统一为：

```text
common_mentor.md
  + 当前 Agent 的 prompt.md
  + SysInput 中该 Agent 适用的 runtime guidelines
  + 作为业务数据封装的结构化 user input
```

业务数据前明确声明“不是系统指令”，并使用 Agent 专属 XML-like 标签包裹 JSON，以降低 prompt injection 风险。

### 4.4 五个 Agent 的具体文件

每个 Agent 目录均采用相同结构：

- `contracts.py`：Pydantic Input、SysInput、Output 和字段约束；
- `prompt.md`：固定 Agent Prompt；
- `prompting.py`：组合公共 Prompt、Agent Prompt、runtime policy 和业务输入；
- `runner.py`：调用 `StructuredModelPort` 并再次校验结构化输出。

| 目录 | 当前已实现功能 |
|---|---|
| `src/research_mentor/agents/idea_review/` | 支持 `opinion / range / forward` 分类和 `proceed_to_plan / proceed_to_working / request_refinement / reject` action；Idea Review 独占 `RetrievalSysInput`；输出检索记录和实际证据 |
| `src/research_mentor/agents/plan_loop/` | 支持 initial、Check 修订、用户反馈修订三种互斥输入模式；输出 ResearchPlan、change summary 和用户回复 |
| `src/research_mentor/agents/key_insight_check/` | 输出五维原始评估、诊断、证据和修订建议；不输出权威 final score |
| `src/research_mentor/agents/working_qa/` | 支持 answer、clarify、decline、success；校验只有进行中的任务可调用；success 必须返回包含 actual result 的完整实验快照 |
| `src/research_mentor/agents/complete/` | 接收方案、主实验和已完成验证，应用 validation/writing guidelines；当前只输出 plan 和字符串 `final_hint` |

注意：上述 Agent runner 已具备清晰 contract 和调用边界，但当前只能通过 memory model adapter 在测试中返回预置结果，尚未接入真实 LLM。

### 4.5 Harness

| 文件 | 当前功能 |
|---|---|
| `src/research_mentor/harness/state.py` | 定义 v0.1 `ResearchSession`、13 个 session phase、9 类 session event 及其 payload |
| `src/research_mentor/harness/routing.py` | 纯函数实现 Idea Review、Check、用户方案决策、Working 和 Complete 的确定性路由；拒绝非法 action/phase 组合 |
| `src/research_mentor/harness/scoring.py` | 按固定权重重新计算 Check final score；阈值默认 6.0；不设置单项否决；失败时最多取 3 条 revision request |
| `src/research_mentor/harness/orchestrator.py` | 原子执行 session 创建、Idea 审查、Plan/Check 循环、用户确认、Working 启动与问答、主/验证实验结果记录和 Complete；维护状态与事件并检查不变量 |

已实现的关键 Harness 行为：

- Agent 不直接互调；
- Harness 校验状态和 action 合法性；
- Check 最多默认 5 轮；
- Check 通过后必须经过用户 accept、override 或 request revision；
- forward 路径必须显式提供 Working task context 和 plan；
- 实验完成后必须由用户记录结果，不能从问答内容猜测；
- Complete 未完成时停在 validation selection，而不是解析 `final_hint` 自动创建任务；
- 每次有效命令写入 session event。

### 4.6 Ports 与 memory adapters

| 文件 | 当前功能 | 状态说明 |
|---|---|---|
| `src/research_mentor/ports/model.py` | 同步 `StructuredModelPort.invoke()` protocol | 已有边界；v1 要迁移为 async typed call |
| `src/research_mentor/ports/retrieval.py` | 同步文献搜索 protocol | 已有最小边界；缺 OpenAlex 和项目文档检索 |
| `src/research_mentor/ports/repository.py` | session add/get/commit/event list protocol | 已有 v0.1 边界；缺 project/UoW/outbox/并发版本 |
| `src/research_mentor/ports/clock.py` | 可注入时钟 protocol | 已实现 |
| `src/research_mentor/adapters/memory/model.py` | 按 Agent 队列返回预置结构化输出 | 仅供 deterministic test，不是真实 LLM |
| `src/research_mentor/adapters/memory/retrieval.py` | 按查询字符串返回预置文献 | 仅供测试，不是真实检索 |
| `src/research_mentor/adapters/memory/repository.py` | 深拷贝保存 session 和 event，校验重复/缺失/ID 不一致 | 仅限进程内存，重启丢失 |
| `src/research_mentor/adapters/memory/clock.py` | 固定 timezone-aware 时间 | 用于 deterministic test |

### 4.7 测试与 Eval

| 文件 | 覆盖内容 |
|---|---|
| `tests/test_config_and_errors.py` | Settings、HarnessConfig 和异常继承 |
| `tests/test_architecture_boundaries.py` | import 方向与模块边界 |
| `tests/domain/test_research.py` | Idea、计划、用户决策等 domain 校验 |
| `tests/domain/test_experiments.py` | 主实验/validation task 关系和字段校验 |
| `tests/agents/test_idea_review.py` | Idea Review contracts、Prompt 和 runner |
| `tests/agents/test_plan_and_check.py` | Plan Loop 和 Key Insight Check contracts/runners |
| `tests/agents/test_working_and_complete.py` | Working QA 与 Complete contracts/runners |
| `tests/agents/test_prompt_contracts.py` | 固定 Prompt 内容 hash，防止无意漂移 |
| `tests/harness/test_routing.py` | 各类 action 的确定性 routing |
| `tests/harness/test_scoring.py` | 五维权重、四舍五入、6.0 阈值和 revision request |
| `tests/harness/test_event_contracts.py` | session event contract |
| `tests/harness/test_orchestrator_planning.py` | Idea、Plan、Check、用户 gate 和事件流程 |
| `tests/harness/test_orchestrator_working.py` | Working、结果记录、Complete 和显式停点 |
| `tests/adapters/test_memory_ports.py` | memory model、retrieval、clock |
| `tests/adapters/test_memory_repository.py` | session repository 的复制隔离和错误条件 |
| `evals/key_insight_check_cases.json` | Check Agent scoring 回归样例 |
| `tests/evals/test_key_insight_check_eval.py` | 读取 Eval 样例并验证 Harness 判定 |

该历史快照当时的全量测试基线为 229 项通过，不代表当前测试数量或 v1 完整产品已经实现。

## 5. Task 进度与尚未实现内容

### 5.1 Milestone A：v1 Contracts 与 Harness 状态机

| Task | 状态 | 未完成内容 |
|---|---|---|
| 1. v1 依赖、配置与应用入口 | 已完成 | 后续只在对应 provider 接入时扩充配置，不重复改造 |
| 2. 项目、对话、文档与 AgentRun 模型 | 已完成 | 保留独立 commit，不重复实现 |
| 3. ForwardResearchContext、ResearchContext、Idea Review action | 已完成 | 保留独立 commit，不重复实现 |
| 4. Complete、validation selection 与结果影响 | 已完成 | 保留独立 commit，不重复实现 |
| 5. SessionPhase、PlanLoop round 与 Harness 权威评分 | 已完成 | 保留独立 commit，不重复实现 |
| 6. completion routing 与 validation queue | 已完成 | 保留独立 commit，不重复实现 |

### 5.2 Milestone B：持久化、文档与检索 providers

Task 7–12 已完成并各有独立 commit：repository/UoW/event ports、SQLAlchemy/Alembic、事务与乐观并发、安全文档处理、OpenAlex、项目 chunk 检索和可选 FlagEmbedding ranker 均已落地。后续只按其 contract 使用或修复回归，不重复实现。

### 5.3 Milestone C：真实 structured model 与 RAG

Task 13–16 已完成：async typed model port、OpenAI Responses/OpenAI-compatible adapters、Idea Review 两阶段检索、Working QA 相关性选择、Context Assembler 投影、context budget、provenance 与 Harness compaction 均已有独立 commit。

### 5.4 Milestone D：完整 Orchestrator 与 Application commands

Task 17–18 已闭合 Idea Review 四种 action、非 CS domain guard、forward `ResearchContext` 与 stage task 初始化，以及 `low/mid/high` 的 1/2/3 路 Plan/Check 候选隔离、单选和 exhausted override。Milestone D 尚未实现：

- Working → result → Complete 的三路闭环：writing、validation、plan revision；
- application command bus；
- command 幂等键、统一 phase guard、project version guard；
- durable AgentRun worker；
- retry、cancel、超时和服务重启恢复。

### 5.5 Milestone E：FastAPI、SSE 与 Demo

FastAPI 等依赖已加入，但没有 API 代码。尚未实现：

- composition root 与 FastAPI lifecycle；
- project、command、view 和统一 error envelope API；
- 文档上传、状态、retry/delete API；
- 研究日志 JSON/Markdown export API；
- public event SSE；
- `Last-Event-ID` 断线恢复；
- deterministic demo mode 和三阶段演示数据。

### 5.6 Milestone F：React 前端

当前仓库没有前端工程。尚未实现：

- React/Vite/TypeScript 工程和 typed API client；
- 三栏项目工作台、阶段视图和证据面板；
- Idea 输入、方案确认/修订/override；
- Working QA、实验结果录入和 validation 选择；
- 文件上传、SSE 状态、失败重试和完整用户操作；
- desktop/narrow-screen 布局、accessibility 和视觉规范；
- 仅用于超长输入、遗漏选择和等待状态等非实质场景的“傲娇” microcopy；科研评价、拒绝理由、证据和风险说明保持中性严谨。

### 5.7 Milestone G：Evals、E2E、文档与发布审计

现有 Check eval 只是起点。尚未实现：

- 五 Agent 的完整 Eval datasets 与统一 runner；
- provider/mock/demo 的质量回归阈值；
- Playwright E2E；
- 34 项产品验收场景；
- frontend unit/build/accessibility 检查；
- production quickstart、环境变量说明和最终 README；
- release audit 与真实 provider smoke test 记录。

### 5.8 安全与产品约束缺口

- application 层尚未限制只接受配置声明的 CS domain/alias；
- 文件路径、MIME、大小和项目隔离尚未实现；
- API key、连接字符串和用户文档的日志脱敏尚未实现；
- provider、文档解析和外部检索的失败恢复尚未实现；
- 多进程并发、重复 command 和 stale version 尚未实现；
- Prompt 已有基本数据/指令隔离，但尚无端到端 adversarial 测试。

## 6. 推荐继续开发顺序

下一位开发者应从 implementation plan 的当前首个未完成 Task 继续，不应跳过 Milestone gate：

1. **Milestone A（Task 2–6）已完成**：不得重复实现；
2. **Milestone B（Task 7–12）已完成**：不得重复实现；
3. **Milestone C（Task 13–16）已完成**：不得重复实现；
4. **完成 Milestone D（Task 17–21）**：将 domain、provider 和 durable run 组合成完整 application journey；
5. **完成 Milestone E（Task 22–26）**：建立 API、SSE 和 deterministic demo；
6. **完成 Milestone F（Task 27–29）**：实现 React 工作台；
7. **完成 Milestone G（Task 30–32）**：补齐 Eval、E2E、34 项验收和发布审计。

每个 Task 必须遵循计划中的 RED → GREEN → 全量回归 → commit 顺序。只有当前 Milestone gate 全绿，才进入下一 Milestone。

## 7. 不可破坏的实现约束

1. 五个 Agent 职责保持独立，不新增第六个强制 Agent。
2. Agent 不直接互调；所有状态转换由 Harness/Application 执行。
3. Check Agent 不决定是否通过；Harness 重算分数并以总分 6.0 为阈值。
4. `range` 不得直接进入计划；必须请求用户补充或确认方向。
5. 合法 `forward` 由 Idea Review 判断并直接进入 Working 准备，不由 Harness 重新做语义分类。
6. 用户结果必须显式记录；不得从 Agent 文本或 `ExperimentInfo` 猜测实验结果。
7. 未经用户选择的 validation 不得创建为执行中任务。
8. `final_hint` 或模型自然语言不得被解析成 command。
9. 负面、不显著或不符合预期的结果必须保留，不得美化。
10. Prompt 固定内容的修改必须同步评估 Prompt contract hash；不得无意修改换行符。
11. `retrieval_guidelines` 只注入检索型 Agent，不能放回所有 Agent 的公共 `SysInput`。
12. 文件、文献、检索结果和用户文本一律视为不可信业务数据。
13. 只做当前 Task 要求的最少变更，不提前实现后续 Milestone。
14. Python 环境和依赖统一使用 `uv`。
15. v1 的上下文压缩由 Harness application service 完成，不建立压缩 Agent；压缩结果必须保留 source turn IDs，不能创造或改写事实。
16. v1 的“傲娇”语气只由 UI microcopy 表达，不建立语气 Agent；不得改写 Agent 的 action、评分、事实、证据、拒绝理由或风险说明。

## 8. 开发环境与验证

要求 Python `3.12` 和 `uv`。

```powershell
uv sync --dev
uv lock --check
uv run pytest -q -p no:cacheprovider
```

Check Agent Eval：

```powershell
uv run pytest -q -p no:cacheprovider tests/evals/test_key_insight_check_eval.py
```

提交前至少检查：

```powershell
git diff --check
git status --short
```

不得提交以下本地产物：

- `.venv/`
- `.uv-cache*/`
- `.pytest_cache/`
- `__pycache__/`
- 本地数据库、上传文件和用户数据
- API key、`.env` 或其他 secrets
- 父目录中的 `task_plan.md`、`findings.md`、`progress.md`

## 9. 接手开发的完成判定

开发者开始新 Task 前，应能回答：

- 本次修改对应 implementation plan 的哪个 Task 和验收测试？
- 该逻辑属于 Agent 语义判断，还是 Harness/Application 确定性权限？
- 是否引入了尚未到达 Milestone 的外部 I/O 或抽象？
- 是否保持 Prompt、contract、state 和 persistence 的单一权威来源？
- 是否先写失败测试，并在实现后运行目标测试与全量回归？

本文应在每个 Task 或 Milestone 完成后更新：至少修改状态基准、已实现文件、对应 Task 状态、测试基线和下一开发起点。
