# Rigora 完整产品设计规格

- 状态：已于 2026-08-30 获用户确认，并于 2026-09-01 按新版《AI+ 创新大赛》完成增量裁决。
- 日期：2026-08-30。
- 目标版本：v1.0。
- 目标读者：后端、Agent、RAG、前端、测试与部署实现者。
- 基线：GitHub `main` commit `3eebca6` 的 v0.1 Python core。

本文把现有快照扩展为可运行、可持久化、可展示的完整产品。本文中的“必须”“不得”“只能”均为强制要求。

## 1. 范围与裁决优先级

设计依据从高到低为：

1. 本文明确写出的 v1.0 裁决；
2. `docs/design/命名架构具体版.md` 的结构化 Schema 与非流程图正文；
3. `docs/design/prompt仓库.md` 的固定 Prompt 与组合规则；
4. `docs/design/AI+ 创新大赛 -_ Rigora/AI+ 创新大赛 -_ Rigora.md` 的产品和前端要求；
5. 历史流程图与图片。

冲突时使用更高优先级规则。不得以旧流程图覆盖本文状态机。

2026-09-01 新版《AI+ 创新大赛》的有效新增意图已经显式吸收到本文；后续开发仍以本文为最高优先级，不直接从源文档流程图反推 contract。新版中的图片路径只用于产品叙事和演示稿排版，不是实现或验收依据。

### 1.1 v1.0 必须完成

- 保留五个职责独立的 Agent；
- 真实 structured LLM adapter；
- OpenAlex 文献检索；
- 项目文档上传、Markdown 转换、chunk 和检索；
- 可选本地 FlagEmbedding rank adapter；
- SQL 持久化、事件、乐观并发和恢复；
- Idea Review、Plan/Check/User gate、Working、Complete 全流程；
- Plan/Check 支持 `low / mid / high` 三种方案模式，分别产生 1 / 2 / 3 条独立候选路径；
- forward 用户已有实验材料直接进入 Working；
- 结构化 validation 候选、用户选择、排序、循环和跳过；
- 结构化 WritingGuidance；
- 主实验或补充实验动摇结论时的修订回路；
- command API、文件 API、SSE 公开事件流；
- 三栏 React 前端与项目隔离；
- 研究日志 JSON/Markdown 导出；
- deterministic demo mode、自动测试与 Eval。

### 1.2 v1.0 不实现

- 自动生成完整论文正文；
- 替用户执行实验或编造实验结果；
- 强制加入第六个压缩 Agent 或独立语气 Agent；
- 生物医药等高风险领域的专用能力；
- 多租户账号、计费和组织权限；
- 分布式微服务和消息队列。

不得为多候选路径新增 Agent 职责类型。`mid/high` 是现有 `plan_loop` 与 `key_insight_check` 的独立 run 组合，由 Harness 管理路径、轮次和用户选择。上下文压缩由 Harness application service 完成；触及产品边界时的界面提示保持柔缓中性，不建立语气 Agent。

v1.0 产品能力和 Eval 限定在 computer science。`InitialInput.domain` 仍保留字符串以支持未来扩展，但 application 层只能接受配置中声明的 CS domain/alias；其他领域返回明确的 unsupported-domain refinement，不假装具备专科能力。

## 2. 架构总览

采用 **full-stack Agent-oriented modular monolith**：

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
        ├── RepositoryPort
        ├── LiteratureSearchPort
        ├── DocumentParserPort
        ├── RetrievalRankerPort
        ├── FileStorePort
        └── PublicEventPublisherPort
                │
                ▼
SQL / OpenAlex / Anydoc / FlagEmbedding / model adapters
```

### 2.1 权限边界

Agent 负责语义判断，Harness 负责确定性状态和数据完整性。

Agent 可以：

- 分类、评估、解释、提出候选任务；
- 根据有效输入输出已声明的结构化 contract；
- 明确不确定性和检索失败。

Agent 不得：

- 直接调用另一个 Agent；
- 修改 session phase、task status、version、run status；
- 自行计算权威 Check final score；
- 把未选择的 validation 标为已完成；
- 把 final hint 当成可执行 command；
- 访问 API key、数据库连接或任意本地文件路径。

Harness/Application 独占：

- command 校验、幂等和乐观并发；
- Agent run 创建、重试、超时与恢复；
- routing、check round、user gate；
- task queue、结果记录、validation 选择；
- session/event/outbox 原子持久化；
- 对外公开事件和 view model；
- export 构造。

## 3. 仓库结构

保留现有模块，并增加以下职责目录：

```text
.
├── src/research_mentor/
│   ├── domain/
│   │   ├── documents.py
│   │   ├── conversations.py
│   │   ├── completion.py
│   │   ├── jobs.py
│   │   └── journal.py
│   ├── agents/                    # 现有五 Agent vertical slices
│   ├── harness/
│   │   ├── orchestrator.py
│   │   ├── routing.py
│   │   ├── state.py
│   │   ├── scoring.py
│   │   └── task_factory.py
│   ├── application/
│   │   ├── commands.py
│   │   ├── command_service.py
│   │   ├── project_service.py
│   │   ├── retrieval_service.py
│   │   ├── document_service.py
│   │   ├── context_service.py
│   │   ├── run_service.py
│   │   └── export_service.py
│   ├── api/
│   │   ├── app.py
│   │   ├── dependencies.py
│   │   ├── errors.py
│   │   ├── schemas.py
│   │   └── routes/
│   ├── ports/
│   └── adapters/
│       ├── model/
│       ├── openalex/
│       ├── documents/
│       ├── embeddings/
│       ├── filestore/
│       ├── sql/
│       └── demo/
├── migrations/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   ├── styles/
│   │   └── test/
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.ts
├── evals/
├── tests/
└── docs/design/
```

不得新建与五 Agent 平行、承担相同语义判断的 service。

## 4. 核心数据模型

所有外部输入使用 Pydantic v2 校验。动态文本仍视为业务数据，不进入 stable instructions。

### 4.1 项目与并发

```python
class ResearchProject(BaseModel):
    project_id: str
    title: str
    domain: str
    session_id: str
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

class ExpectedVersion(BaseModel):
    expected_version: int = Field(ge=1)
```

每个 mutation command 必须携带 `command_id` 和 `expected_version`。重复 `command_id` 返回原结果，不重复运行 Agent；错误 version 返回 conflict。

### 4.2 文件

```python
DocumentStatus = Literal["uploaded", "parsing", "ready", "failed"]

class UploadedDocument(BaseModel):
    document_id: str
    project_id: str
    original_name: str
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str
    status: DocumentStatus
    created_at: datetime
    error_message: str | None = None

class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    ordinal: int = Field(ge=0)
    heading_path: list[str] = Field(default_factory=list)
    markdown: str
```

解析后的完整 Markdown 和 chunk 必须持久化。Agent input 只能接收经过检索选中的 chunk，不得默认注入整份大文件。

### 4.3 文献与检索诊断

`LiteratureRecord` 增加：

- `record_id`：内部稳定 ID；
- `provider`：当前为 `openalex` 或 `demo`；
- `provider_id`：例如 OpenAlex Work ID；
- `publication_date`；
- `cited_by_count`；
- `retrieved_at`；
- `query_id`。

```python
class RetrievalDiagnostics(BaseModel):
    query: str
    provider: str
    candidate_count: int
    selected_count: int
    top_relevance: float | None
    status: Literal["ok", "empty", "unavailable"]
    limitation: str | None = None
```

`empty` 表示成功检索但无结果；`unavailable` 表示外部失败。二者不得都解释成“不相关”。

### 4.4 forward 研究上下文

`IdeaReviewOutput.action == "proceed_to_working"` 时必须包含：

```python
ForwardStage = Literal[
    "experiment_in_progress",
    "main_experiment_completed",
    "validation_in_progress",
    "research_completed",
]

class ForwardResearchContext(BaseModel):
    stage: ForwardStage
    research_question: str
    current_experiment: ExperimentInfo | None = None
    main_result: MainExperimentResult | None = None
    completed_validations: list[ValidationResult] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
```

`proceed_to_working` 要求 `missing_fields=[]` 且 stage 所需字段完整，否则只能 `request_refinement`。

stage cross-field 规则：

- `experiment_in_progress`：必须有包含非空 current experiment 的 `current_experiment`；
- `main_experiment_completed` 与 `research_completed`：必须有 `main_result`；
- `validation_in_progress`：必须同时有 `main_result` 和 current experiment；
- 已完成结果的 `actual_result`、`conclusion` 不得由 Agent 根据附件文件名推断；只接受用户明确内容或已解析结构化记录。

Working 和 Complete 使用：

```python
class ResearchContext(BaseModel):
    normalized_idea: str
    research_question: str
    plan: ResearchPlan | None = None
    forward_context: ForwardResearchContext | None = None
```

恰好一个 `plan` 或 `forward_context` 必须存在。forward 不经过 Plan Loop，符合既定路由。

`TaskFactory` 确定性构造 task：accepted plan 创建 main task；forward in-progress 使用导入的 current experiment；forward completed 创建“核对已有结果与补充验证需求”的 main review task，先进入 Working 让用户确认事实，再记录结果并进入 Complete。TaskFactory 不调用 LLM。

### 4.5 对话与压缩

```python
class ConversationTurn(BaseModel):
    turn_id: str
    role: Literal["user", "assistant", "system_event"]
    content: str
    created_at: datetime
    agent_name: AgentName | None = None
    evidence_ids: list[str] = Field(default_factory=list)

class CompactContext(BaseModel):
    summary: str
    source_turn_ids: list[str]
    facts: list[str]
    unresolved_questions: list[str]
```

压缩是 application service，不是新 Agent。它只能压缩历史表达，不能创造实验事实；原始 turn 永久保留。

### 4.6 Complete 输出与 validation

```python
ValidationPriority = Literal["critical", "high", "medium", "low"]

class ValidationCandidate(BaseModel):
    candidate_id: str
    task: ValidationTask
    priority: ValidationPriority
    rank: int = Field(ge=1)
    rationale: str
    addresses_claims: list[str]

class ExcludedValidation(BaseModel):
    paradigm: ValidationParadigm
    validation_type: ValidationType
    reason: str

class WritingGuidance(BaseModel):
    suggested_structure: list[str]
    key_results_to_report: list[str]
    key_discussion_points: list[str]
    limitations: list[str]

CompletionMode = Literal["validation", "plan_revision", "writing"]

class CompleteAgentOutput(BaseModel):
    mode: CompletionMode
    plan: ResearchPlan | None
    final_hint: str
    validation_candidates: list[ValidationCandidate] = Field(default_factory=list)
    excluded_validations: list[ExcludedValidation] = Field(default_factory=list)
    writing_guidance: WritingGuidance | None = None
    revision_reason: str | None = None
```

确定性 cross-field 规则：

- `validation`：至少一个 candidate；无 writing guidance/revision reason；
- `plan_revision`：必须有 revision reason；无 candidates/writing guidance；
- `writing`：必须有 writing guidance；无 candidates/revision reason；
- candidate rank 从 1 开始且唯一；candidate ID 唯一；
- Complete Agent 不输出 `completion_status`，Harness 根据 `mode` 路由。

### 4.7 用户选择

```python
class ValidationSelection(BaseModel):
    selected_candidate_ids: list[str] = Field(default_factory=list)
    skipped_candidate_ids: list[str] = Field(default_factory=list)
    finish_without_more_validation: bool = False
    user_reason: str | None = None
```

规则：

- selected 与 skipped 不得重叠，只能引用当前候选；
- selected task 按 candidate rank 入队；
- `finish_without_more_validation=True` 时 selected 必须为空且 user reason 非空；
- 用户拒绝 critical validation 时必须永久记录候选、导师理由和用户理由；
- 前端展示顺序可以变化，但提交必须使用 candidate ID。

### 4.8 实验结果影响

```python
ResultImpact = Literal["supports", "neutral", "contradicts", "invalidates"]
ExecutionStatus = Literal["completed", "failed", "cancelled"]
```

`MainExperimentResult` 和 `ValidationResult` 增加 `execution_status`、`impact` 与 `failure_reason`。负面结果可以是 `completed + contradicts`；不得把科学结论不支持预期等同执行失败。

### 4.9 研究日志

```python
class ResearchJournal(BaseModel):
    project: ResearchProject
    initial_input: InitialInput
    idea_review: IdeaReviewOutput
    literature: list[LiteratureRecord]
    plans: list[PlanLoopOutput]
    checks: list[KeyInsightCheckOutput]
    plan_decisions: list[UserPlanDecision]
    override_records: list[OverrideRecord]
    experiment_tasks: list[ExperimentTaskContext]
    main_result: MainExperimentResult | None
    validation_results: list[ValidationResult]
    complete_outputs: list[CompleteAgentOutput]
    writing_guidance: WritingGuidance | None
    generated_at: datetime
```

JSON 是权威导出；Markdown 从该模型确定性渲染，不解析聊天正文来猜字段。

### 4.10 Check scoring 与轮次

权威计算保持：

```text
final_score = round(
    0.20 × research_fit
  + 0.25 × novelty
  + 0.20 × research_value
  + 0.20 × testability_feasibility
  + 0.15 × evidence_support,
  1,
)
check_decision = final_score >= 6.0
```

不存在单项否决。模型不输出权威 final score 或 decision。

现有 `PlanLoopInput.loop_round=5` 含义不清，在 v1 migration 中替换为：

```python
check_round: int = Field(ge=0)
max_check_rounds: int = Field(ge=1)
```

首次 plan 和用户主动 revision 使用 `check_round=0`；第 N 次内部 Check 失败回 Plan 时使用 `check_round=N`。只有 Harness 修改计数，最大值默认 5。

### 4.11 Plan 候选模式与必要条件 gate

`PlanGenerationMode = Literal["low", "mid", "high"]`，默认 `low`；候选数固定映射为 1、2、3。每条 `PlanCandidatePath` 有稳定 `candidate_id`、`candidate_index`、独立的 active plan、Check 历史和 `check_round`。Harness 可并发调度不同路径的 AgentRun，但每个 run 仍只调用一个 Agent；Agent 之间不得互调。`mid/high` 必须等所有仍可产出候选的路径到达 pass 或 exhausted 决策点后，再进入候选选择 gate。用户只能按 candidate ID 选择一条进入 Working；未选候选和评分历史仍写入研究日志。

路径差异通过配置化的 candidate profile 与明确的 `candidate_index`/focus hint 产生并记录，不能假称相同 request 的随机重复就是有效差异。v1 只保留现有五种 Agent 职责，不把“每条路径的一提一审”解释为新增 Agent 类型。

新版源文档提到“必要条件 gate”，但没有定义 gate 名称、判定字段、失败路由或与总分阈值的关系。因此本版本继续以五维加权总分 `>= 6.0` 为唯一机器通过条件，`check_guidelines` 不得新增单项否决。新增 gate 必须先由用户确认完整规则，再修改本节、Schema、Eval 和 acceptance；实现者不得猜测。

## 5. 状态机

`AgentRunStatus` 与科研 `SessionPhase` 分离。Agent 运行时 session 保持业务 phase，前端通过 run/event 显示 busy。

### 5.1 Session phases

保留现有 phase，并增加：

- `AWAITING_PLAN_REVISION_DECISION`；
- `AWAITING_VALIDATION_RESULT` 不新增，仍使用 `AWAITING_RESULT_RECORD`；
- `AWAITING_WORKING_CONTEXT` 只用于迁移旧 session，新 session 不应停在此处。

### 5.2 主路径

```text
AWAITING_IDEA
  ├─ range/refine ─► AWAITING_IDEA_REFINEMENT ─► review
  ├─ reject ───────► REJECTED
  ├─ opinion ──────► PLANNING ► CHECKING_KEY_INSIGHT
  │                    ▲             │ fail (< max)
  │                    └─────────────┘
  │                                  ├─ fail (= max) ► CHECK_LOOP_EXHAUSTED
  │                                  └─ pass ► AWAITING_PLAN_DECISION
  │                                                ├─ revise ► PLANNING
  │                                                └─ accept/override ► WORKING
  └─ forward ───────────────────────────────────────────────────────► WORKING

WORKING
  ├─ answer/clarify/decline ► WORKING
  ├─ task completed ─────────► AWAITING_RESULT_RECORD
  └─ plan issue ─────────────► AWAITING_PLAN_REVISION_DECISION

AWAITING_RESULT_RECORD ► COMPLETING
COMPLETING
  ├─ validation ─────► AWAITING_VALIDATION_SELECTION
  ├─ plan_revision ──► AWAITING_PLAN_REVISION_DECISION
  └─ writing ────────► COMPLETED

AWAITING_VALIDATION_SELECTION
  ├─ select ► WORKING（队列首项）
  └─ finish_without_more_validation ► COMPLETING（带用户 override 记录）
```

其中 `PLANNING ↔ CHECKING_KEY_INSIGHT` 是一条候选路径模板。`low` 运行一条并沿用普通 `AWAITING_PLAN_DECISION`；`mid/high` 分别运行两/三条相互隔离的模板，聚合后进入同一用户候选选择 gate。候选模式和每条路径的 profile 在创建本轮 plan 时冻结，重试不得偷偷改变数量或 profile。

### 5.3 Validation queue

- 一次选择可包含多个 task；session 只允许一个 `current_task`；
- 当前 validation 记录结果后回 `COMPLETING`；
- Complete Agent 必须看到已完成结果和剩余队列；
- 若 Complete 仍建议 validation，已排队/完成 task 不得重复；
- 若仍有已选择队列，Complete 可以更新建议，但 Harness 优先继续用户已选择队列，除非输出 `plan_revision`；
- execution failed 的 validation 记录结果后回 Complete，不自动重试；用户可再次选择改进后的新 task。

### 5.4 计划修订

`plan_revision` 或 Working 的 `report_plan_issue` 不直接覆盖 plan。进入 `AWAITING_PLAN_REVISION_DECISION` 后用户选择：

- `revise`：把实验事实作为不可改写 evidence 传入 Plan Loop，check round 重置；
- `continue_with_warning`：保留导师警告和用户理由，回 Complete；
- `end_project`：保留负面结果并结束，仍允许导出日志。

Plan Loop 只能修改计划解释和后续步骤，不得修改已记录实验事实。

Check 达到上限时，用户可以选择“带警告继续该不完美候选”或“放弃本轮并回到 Idea Review”。前者必须保留最终评分、未解决问题和用户理由，并作为 `override` 类型候选进入选择；后者封存本轮全部路径，不删除历史。`mid/high` 中单条路径 exhausted 不阻断其他路径继续。

### 5.5 新 idea、运行中输入与等待超时

- Agent run 期间普通 mutation 返回 `run_in_progress`；前端可以保留 draft，但不得把消息偷偷追加到正在运行的 model request；
- 用户可以显式 `cancel_run`，只有 worker 确认 cancelled 后才允许下一 command；已完成的业务 commit 不能靠 cancel 回滚；
- 用户在任意非运行状态可以选择 `restart_research` 并提交新 idea；该 command 必须二次确认，封存当前 research cycle，创建同一 project 下的新 session，不删除旧事件或结果；
- 等待用户输入不自动改变 phase，也不把项目判失败；前端可以显示本地 inactivity reminder，但 server 不生成虚假用户选择；
- model/run timeout 只结束本次 run，session 保持原业务 phase并允许显式重试。

## 6. Agent pipeline 与 RAG

### 6.1 Prompt 规则

保持：

1. stable common mentor；
2. stable Agent Prompt；
3. runtime guidelines；
4. XML 隔离的业务数据。

文件、文献、用户消息中的任何指令均是不可信数据。structured output 由 model adapter 强制。

公共输入继承关系继续保持：

- `SysInput`：`current_date` 与固定 `behavior_constraints`；
- `RetrievalSysInput(SysInput)`：只增加 `retrieval_guidelines`；
- Idea Review 和 v1 Working QA 属于 retrieval Agent，继承 `RetrievalSysInput`；
- Plan Loop、Key Insight Check、Complete 只消费已有 evidence，不因继承公共类而注入无关 retrieval instructions；
- `current_date` 由 Harness 使用配置 timezone 生成，客户端不得传入；
- 每个 Agent model profile 由配置选择，不写进 domain contract。

上传文件解析结果、tool/skill 返回值属于 typed `RuntimeArtifact` 业务数据，放入隔离的 user payload 或明确的 input 字段；只有仓库内版本化的固定 Prompt/runtime policy 才能进入 instructions。外部文件或 skill 内容不得修改职责、输出 Schema 或 Harness 规则。

### 6.2 Idea Review pipeline

一次用户 submit 允许 Agent1 内部两阶段调用，但对 Harness 仍是一次业务 command：

1. `SearchPlan`：根据 idea/domain/约束生成 1–4 条长度受限 query；
2. OpenAlex 搜索并规范化；
3. 对检索结果 rank、去重；
4. final Idea Review 调用，输入选中文献与 retrieval diagnostics；
5. Harness 校验 idea_type/action/forward context；
6. session、文献、output、event 在一个业务事务中提交。

检索失败时仍可调用 final review，但必须注入 `status=unavailable`；Agent 不得声称“没有相关文献”。

### 6.3 Working relevance pipeline

Working 每次问题先构造 retrieval corpus：

- 当前 task/ResearchContext；
- compact context；
- 已上传 document chunks；
- 已选 LiteratureRecord 摘要。

Working 检索 query 固定拼接 `normalized_idea + research_question/current stage + current task/current experiment + question`，避免“那第二个方案呢”等短问题丢失研究语境。rank 输出只作为 diagnostics；v1 不允许按低分在模型前硬拒，无论 low/empty/unavailable 都交给 Working Agent 结合结构化上下文判断，并公开说明限制。`rag_relevance_threshold` 仅用于 Task 30 标注集校准，在有证据前不驱动路由，也不增加额外相关性小模型。

需要外部事实时可以搜索 OpenAlex；普通实验排错优先使用项目材料，避免每轮无意义外部检索。

### 6.4 Context budget

- context service 按 Agent 配置 token/character budget；
- 永远保留 system instructions、当前 task、最新用户输入、结构化实验事实；
- 历史消息按相关性和时间选择；
- 超额历史用 `CompactContext` 代替，但原始记录仍在 SQL；
- compaction 输出必须经过 Schema 校验并记录 source turn IDs。

Context Assembler 是 Harness/Application 的确定性能力，不是额外 Agent。每次 model call 必须先按 Agent 做字段投影，再分成：

1. stable instructions：`common_mentor + agent prompt + 该 Agent 适用的 runtime policy`；
2. project facts：本项目内稳定的 typed 研究上下文；
3. turn payload：本轮新增的用户输入、选中 evidence、recent turns/compact context。

`sys_input` 只用于构建 instructions，不得再次序列化进 `user_input`；其他 Agent 的专属字段、完整 session dump、未选 document chunks/literature 也不得注入。结构化权威状态优先于聊天历史；只有不可结构化历史允许 compact，且需要时可按 source IDs 从 event/turn 存储回拉。

## 7. Ports 与 adapters

### 7.1 Structured model

`StructuredModelPort` 升级为 async，并接收 `ModelRequest`：agent name、model profile、instructions、user input、output model、timeout、trace ID。

必须提供：

- `OpenAIResponsesModelAdapter`：真实 structured output；
- `OpenAICompatibleModelAdapter`：兼容配置了 base URL 且支持 JSON Schema 的 provider；
- `DemoModelAdapter`：固定场景，不需要 API key，并在 UI 显示 DEMO 标记；
- `MemoryModelAdapter`：单元测试。

API key 只能从环境或 secret store 读取，不得进入数据库、event、SSE 或前端 bundle。

### 7.2 OpenAlex

adapter 使用 `/works` search/select：

- 连接和总请求 timeout；
- 429 指数退避并遵守服务端提示；
- 有限重试；
- DOI/URL/provider ID 去重；
- abstract inverted index 还原；
- 保留查询、retrieval time 和 rate-limit diagnostics；
- provider error 映射为 typed error。

### 7.3 Documents

`DocumentParserPort.parse()` 返回 Markdown 与 parser metadata。必须提供：

- Anydoc adapter；
- plain text/Markdown adapter；
- demo/test adapter。

上传限制由配置控制：允许 MIME、单文件大小、项目总大小。文件名不得作为存储路径；使用内部 ID。解析失败不删除原文件，允许用户重试或移除。

浏览器端 Anydoc WASM 可作为隐私优化，但 server adapter 仍必须存在，且服务端必须重新校验客户端结果。

### 7.4 Embeddings/rank

提供：

- FlagEmbedding adapter，模型名称配置化；
- deterministic lexical adapter，供 demo/test；
- unavailable adapter，显式返回不可用而非假分数。

FlagEmbedding 为可选 dependency group，默认安装和启动不下载大型模型。

### 7.5 SQL repository

使用 SQLAlchemy 2 async。开发默认 SQLite，生产支持 PostgreSQL。

最低表集合：

- `projects`；
- `research_sessions`；
- `session_events`；
- `outbox_events`；
- `agent_runs`；
- `processed_commands`；
- `conversation_turns`；
- `documents`、`document_chunks`；
- `literature_records`、`project_literature`；
- `validation_types`；
- `agent_outputs`；
- `research_exports`。

session JSON 保留完整聚合快照，关键 phase/version/timestamp 独立成列。每次成功的 Agent structured output 同时写入 `agent_outputs`，并通过 run ID、agent name、Prompt version 和 session version 可追溯。commit 必须在同一 transaction 更新 session version、追加 domain event 和 outbox。stale version 必须失败且不得写部分数据。

Alembic migration 是唯一 schema 变更方式。应用启动不得静默重建生产数据库。

## 8. Durable runs 与公开事件

### 8.1 AgentRun

```python
AgentRunStatus = Literal[
    "queued", "running", "succeeded", "failed", "timed_out", "cancelled"
]

class AgentRun(BaseModel):
    run_id: str
    project_id: str
    command_id: str
    agent_name: AgentName
    status: AgentRunStatus
    attempt: int
    started_at: datetime | None
    finished_at: datetime | None
    public_message: str | None
    error_code: str | None
```

worker 从 SQL 领取 queued run。开发环境允许单 worker；生产 PostgreSQL 可多 worker。进程重启后，超过 lease 的 running job 回 queued，且依赖 command ID 保证业务提交幂等。

### 8.2 Retry

- provider timeout、429、临时网络错误可以有限重试；
- Schema validation failure最多重新请求模型两次，第二次附最小错误摘要；
- invariant、非法 command、stale version 不重试；
- retry 不产生重复业务 event；
- 最终失败时 session 保持原业务 phase，只追加 run failure public event。

### 8.3 PublicEvent

只公开：

- command accepted；
- run started/completed/failed；
- retrieval started/result count/unavailable；
- document parsing progress；
- Agent 阶段与简短状态；
- session phase changed；
- evidence added；
- user input required；
- export ready。

不得公开模型 chain-of-thought、system prompt、API key、原始 provider payload 或完整未筛选文件内容。

每个 event 有递增 sequence。SSE 支持 `Last-Event-ID`/`after` 重连；心跳不写入 domain event 表。

## 9. API

API 前缀 `/api/v1`。

### 9.1 Projects 与 views

- `POST /projects`：创建项目和 session；
- `GET /projects`：按更新时间列出项目；
- `GET /projects/{project_id}`：返回聚合 frontend view；
- `DELETE /projects/{project_id}`：v1.0 不提供硬删除；只允许 archive command。

### 9.2 Commands

`POST /projects/{project_id}/commands` 接收 discriminated command union：

- `submit_idea`；
- `submit_refinement`；
- `run_plan`；
- `run_check`；
- `decide_plan`；
- `send_working_message`；
- `record_main_result`；
- `record_validation_result`；
- `run_complete`；
- `select_validations`；
- `decide_plan_revision`；
- `cancel_run`；
- `restart_research`；
- `archive_project`。

Command 包含 `command_id`、`expected_version`。需要 Agent 的 command 返回 `202 + run_id`；确定性 command 返回 `200 + updated view`。

API 根据 phase 返回 `allowed_commands`，前端不得自己复制完整 routing table。

### 9.3 Documents

- `POST /projects/{project_id}/documents`；
- `GET /projects/{project_id}/documents`；
- `GET /projects/{project_id}/documents/{document_id}`；
- `POST /projects/{project_id}/documents/{document_id}/retry`；
- `DELETE` 只允许未被任何 evidence/result 引用的 document。

### 9.4 Events 与 export

- `GET /projects/{project_id}/events`：SSE；
- `GET /projects/{project_id}/journal.json`；
- `GET /projects/{project_id}/journal.md`。

### 9.5 Error envelope

```json
{
  "error": {
    "code": "stale_project_version",
    "message": "项目已在其他操作中更新，请刷新后重试。",
    "retryable": false,
    "details": {}
  }
}
```

Pydantic input error、illegal phase、stale version、provider unavailable、rate limited、parse failure 和 internal error 必须映射稳定 code。内部 traceback 不返回前端。

## 10. Frontend

### 10.1 技术与边界

- React 19 + TypeScript + Vite；
- CSS variables 和项目内组件，不引入大而全 UI framework；
- API client 从 OpenAPI types 或手写受测 discriminated unions 生成；
- server state 与 draft UI state 分离；
- frontend 不保存 provider secret，不运行 Harness 规则。

产品定位是 Rigora：耐心严谨的个性化科研探索导师，不是通用 LLM 替代品。它帮助用户聚焦选题、形成和审查方案、处理研究过程问题、记录结果并组织验证；不替用户写代码或论文正文，也不承诺解决“所有科研问题”。与当前研究无关的细碎通用问题应明确引导至通用 Agent 或搜索工具。v1 的专业能力与 Eval 仍限 computer science。

### 10.2 桌面布局

```text
┌──────────────────────────────────────────────────────────────┐
│ Logo / Project title       Agent progress       Run status   │
├──────────────┬────────────────────────────┬──────────────────┤
│ Projects     │ Research timeline          │ Evidence         │
│              │                            │                  │
│ history      │ agent cards / plan / QA    │ literature cards │
│ stages       │ system transition notices  │ document chunks  │
│              │                            │                  │
├──────────────┴────────────────────────────┴──────────────────┤
│ Contextual panel or bottom composer                          │
└──────────────────────────────────────────────────────────────┘
```

- 左栏：项目、archive、当前 phase、历史入口；
- 中栏：结构化 timeline，不把全部输出压成普通 chat bubble；
- 右栏：当前可见回答实际引用的 evidence，支持定位关联卡片；
- 顶部：Idea Review → Plan → Check → Working → Complete；refinement/validation 是阶段内子状态；
- 窄屏：左栏 drawer、右栏 evidence sheet，中栏保持主内容。

### 10.3 中央内容类型

- IdeaReviewCard；
- ResearchPlanView；
- KeyInsightScoreCard；
- PlanDecisionPanel；
- WorkingMessage；
- ExperimentRecordForm；
- ValidationSelectionPanel；
- WritingGuidanceView；
- TransitionToast；
- CollapsibleRunTrace；
- ExportPanel。

每种内容使用 typed view model。不得通过关键词解析 Agent reply 决定组件。

### 10.4 输入规则

- session idle 且 `allowed_commands` 允许消息时显示底部 composer；
- Agent run 期间禁用 composer，并显示可读 run status；
- 需要确定性选择时显示 selection panel；
- 需要较长结构化输入时显示 form/panel；
- 未完成必填项时 panel 可进行一次克制的轻微 shake，并提供文字错误；
- 原始 idea 最大 19999 字，前端计数和后端 contract 同时校验；
- 用户刷新页面后从 project view + SSE sequence 恢复，不丢失已提交输入。

### 10.5 Streaming 呈现

- 公开 run events 逐条出现；
- 文献结果到达时右栏增量更新；
- 最终结构化 Agent output 成功校验并提交后再渲染；
- typewriter 只用于短状态文案和最终自然语言字段，不逐字符拼接未校验 JSON；
- run trace 完成后默认折叠，可展开查看公开步骤。

### 10.6 视觉语言

- 气质：严谨的研究工作台，温暖纸张色与墨色为主，单一暖橙作为导师强调色；
- typography：中文正文优先可读性，代码/指标使用等宽字体；
- 卡片边界轻、阴影克制；不用大面积渐变、玻璃拟态和无意义 dashboard 指标；
- 触及产品边界时的界面提示保持柔缓中性，例如超长输入、遗漏选择、等待状态；
- 禁止 emoji 表情包；
- 科研评价、拒绝理由和风险说明保持中性严谨。

示例：

- 超长输入：`内容过长，请拆分后提交，或改为上传文件。`
- 未选 validation：`请先勾选至少一项补充实验，或选择本轮不再补充验证。`
- run 中：`正在核对证据，请稍候。`

### 10.7 Accessibility

- 所有操作可键盘完成；
- focus 可见；
- panel 有 dialog/heading/description 语义；
- shake、旋转和 typewriter 遵守 reduced-motion；
- 不只用颜色表达 score、phase 和错误；
- citation hover 同时支持 focus/click；
- loading 有 `aria-live` 文本，但不逐字符播报。

## 11. Demo mode

为了让仓库无需 API key 也能展示完整前端，必须提供明确标识的 deterministic demo：

- 三个预置项目：刚提交 idea、Working 中、Validation selection；
- 固定但符合真实 Schema 的 Agent outputs、文献和事件延迟；
- 所有 phase、panel、右栏 evidence、export 可操作；
- 页面顶部持续显示 `DEMO DATA`；
- demo 数据不得被 README 描述为真实模型或真实 OpenAlex 结果；
- real mode 使用同一 API contract，不维护第二套前端逻辑。

## 12. 配置

配置由 typed settings 从环境读取，至少包括：

- app mode、database URL、file store root；
- model provider/base URL/API key env name；
- 每个 Agent 的 model profile；
- request/model/run timeout 和 retry；
- OpenAlex API key、mail/contact、limit；
- embedding adapter/model/device；
- max check rounds、pass score、RAG threshold；
- upload limits、context budget；
- supported domains/aliases，v1 默认只含 computer science；
- CORS allowed origins。

提供 `.env.example`，只含占位值。启动日志只显示 provider 名和非敏感配置。

Python dependency 统一由 uv/`uv.lock` 管理；frontend 统一使用 npm/`package-lock.json`，不得同时提交 yarn、pnpm 等第二套 lockfile。

## 13. 安全与隐私

- 文件 ID 与实际路径分离并阻止 path traversal；
- 校验 MIME、扩展名、大小和项目配额；
- Markdown 在前端渲染前 sanitize；
- 外部 URL 使用安全 link 属性；
- dynamic data 始终与 Prompt instructions 隔离；
- SQL 使用参数化 ORM/query；
- export 不包含 secret、内部 error 或隐藏 model metadata；
- demo 默认仅监听 localhost；
- v1.0 单用户本地部署不声称拥有多用户鉴权。

## 14. 错误与恢复

- API validation：不创建 run，不修改 session；
- provider 暂时失败：run retry，session phase 不变；
- provider 最终失败：run failed event，可由用户重试同一业务意图但使用新 command ID；
- output Schema 失败：最多两次修复请求，仍失败则不 commit Agent output；
- document parse 失败：document status failed，保留原文件；
- OpenAlex unavailable：记录 diagnostics，Agent 明确证据限制；
- stale version：409，前端刷新并保留未提交 draft；
- SSE 中断：使用 sequence 恢复；
- worker 重启：lease 过期 run 重领；
- SQL transaction 失败：session/event/outbox 全部回滚。

## 15. 测试策略

### 15.1 Python

- domain cross-field tests；
- five Agent Prompt isolation 与 structured output tests；
- Harness route table 和 state transition tests；
- application command/idempotency tests；
- SQL repository transaction、stale version、restart tests；
- OpenAlex/Anydoc/model/ranker contract tests；
- API OpenAPI、error envelope、upload、SSE reconnect tests；
- export snapshot tests。

所有外部 adapter tests 默认使用录制或 fake transport；带显式 marker 的 live integration 才访问网络。

### 15.2 Frontend

- component tests；
- phase → allowed interaction tests；
- SSE reconnect/replay tests；
- three-column/responsive tests；
- accessibility tests；
- Playwright demo path；
- 关键桌面和窄屏 screenshot visual checks。

### 15.3 Eval

至少建立：

- 20 条 CS Idea Review 标注集：opinion/range/forward/reject/refine；
- 引用可解析率与重复率；
- retrieval relevance 标注集，用于校准 0.3 threshold；
- Plan 专家 rubric；
- Check 五维评分稳定性与 total-only decision；
- validation candidate relevance/duplicate rate；
- 完整 demo workflow success rate。

Eval 输出包含 Prompt version、model profile、重复采样次数和时间。未配置真实 provider 时只运行 deterministic eval，不伪造模型指标。

## 16. 验收场景

v1.0 只有在以下场景均有自动或人工可复核证据时才能宣称完成：

1. 新建项目、提交明确 opinion、完成检索、计划、Check 和用户 accept。
2. range 输入只能 refinement，补充后重新 review。
3. 不可行 idea 被拒绝且证据限制明确。
4. forward 进行中实验不经 Plan Loop 直接进入 Working。
5. forward 已完成主实验可以记录结果并进入 Complete。
6. Check 单项低于 2.5 但总分达到 6.0 时通过。
7. 用户 request revision 重置内部 check round；override 留完整记录。
8. Working 低相关分数仍进入 Agent；检索 query 包含研究与任务上下文，只有 Agent 结合上下文后才能 decline。
9. rank unavailable 不得伪装成不相关。
10. 上传 supported 文件后产生 Markdown/chunks 并可被引用。
11. parse 失败可见且不破坏项目。
12. main result 产生有序 validation candidates。
13. 用户多选 validation 后按 rank 逐一进入 Working。
14. validation completed/negative/failed 都被如实记录并回 Complete。
15. invalidates 结果进入计划修订 decision，不自动覆盖计划。
16. 用户跳过 critical validation 时保留双方理由。
17. evidence 足够时产生结构化 WritingGuidance 并完成项目。
18. JSON/Markdown journal 包含 idea、证据、计划争论、实验、validation 和写作指导。
19. server 重启后 project/version/events/run 可恢复。
20. 重复 command ID 不重复 Agent 调用或 event。
21. 两个 stale mutation 中只有一个成功。
22. SSE 断线重连不会漏掉或重复渲染持久化事件。
23. 没有 API key 时 demo mode 能走通完整 UI，且明显标注 demo。
24. real mode 使用真实 structured model adapter；secret 不出现在日志/event/frontend。
25. 桌面三栏、窄屏 drawer/sheet、键盘与 reduced-motion 验收通过。
26. Agent run 期间的新消息不会进入已开始的 request；cancel 后可安全重试。
27. 等待用户输入不会自动选择、自动失败或丢失 session。
28. restart research 会封存旧 cycle 并创建新 session，旧日志仍可导出。
29. 非 CS domain 得到明确 unsupported-domain 结果，不调用伪专科流程。
30. 全部 Python、frontend、E2E、build 和 architecture boundary tests 通过。
31. `low/mid/high` 分别创建 1/2/3 条隔离候选路径；`mid/high` 只允许选择一个 candidate ID 进入 Working，未选历史仍可导出。
32. Check exhausted 的不完美候选只有经用户显式 override 才能继续；必要条件 gate 未获确认前不参与判定。
33. Working `success` 必须进入用户显式结果记录/确认，不直接终止；主实验 plan issue 与 validation 负面/失败结果按任务类型进入既有 revision/result 流程，不用 `validationResult` boolean 猜测。
34. 每个 Agent request 的动态 payload 不含 `sys_input`、其他 Agent 专属字段或完整 session dump，Context Assembler 的投影与 source provenance 可测试。

## 17. 实施阶段

实现必须按以下依赖顺序：

1. v1 domain contracts、Complete output、forward context、状态和迁移；
2. repository v2、SQL schema、transaction、event/outbox；
3. document/OpenAlex/ranker/model adapters；
4. application commands、durable runs、完整 orchestration；
5. API、SSE、upload、export；
6. React frontend 与 deterministic demo；
7. live provider integration、Eval、E2E、视觉和恢复验收；
8. README、deployment scripts、最终 completion audit。

每阶段必须先有失败测试，再做最小实现；不得用 demo adapter 的绿灯代替 real adapter contract 和 integration evidence。

## 18. 原设计功能覆盖

| 原设计要求 | 本文裁决位置 |
|---|---|
| 五 Agent 各司其职 | §2.1、§6 |
| Idea 类型由 Agent1 判断 | §4.4、§6.2 |
| range refinement、opinion plan、forward direct Working | §5.2、§16 |
| 文献检索与引用 | §4.3、§6.2、§7.2 |
| SysInput/current date/选择性 retrieval guidelines | §6.1 |
| Plan Loop、Check loop、最多五轮 | §5.2、配置 §12 |
| Check 五维总分 6.0、无单项否决 | 现有 scoring contract、§16.6 |
| 用户 accept/revise/override | §5.2、§16.7 |
| Working relevance threshold 0.3 | §6.3、§12 |
| Working answer/clarify/decline/success | 保留现有 contract、§5.2 |
| 主实验与 validation task 区分 | §4.6–4.8、§5.3 |
| Complete 安排补充实验与写作指导 | §4.6、§5.2 |
| validation 类型、不需要项和优先级 | §4.6–4.7 |
| validation 用户选择和循环 | §4.7、§5.3 |
| 错误或反对结果回路 | §4.8、§5.4 |
| 用户已有实验基础 | §4.4、§5.2 |
| SQL 保存状态、文献和 Agent outputs | §7.5 |
| 文件统一转 Markdown | §4.2、§7.3 |
| 多项目、三栏 UI、顶部进度、文献卡片 | §10 |
| 运行中禁用输入和弹出 panel | §5.5、§10.4 |
| 检索/Agent 状态流式展示 | §8.3、§10.5 |
| 边界提示不影响判断 | §1.2、§10.6 |
| 输入最大 19999 字 | 保留现有 contract、§10.4 |
| 可导出研究日志 | §4.9、§9.4 |
| OpenAlex、Anydoc、FlagEmbedding | §7.2–7.4 |
| Agent 模型分别配置 | §6.1、§12 |
| 超时、运行中换 idea | §5.5、§14 |
| Demo 预置不同阶段项目 | §11 |
| 评估集与阈值校准 | §15.3 |
