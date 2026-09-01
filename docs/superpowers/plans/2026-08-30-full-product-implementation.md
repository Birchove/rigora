# 傲娇导师 v1.0 完整产品 Implementation Plan

> **2026-09-01 增量说明：** Task 2–15 的已完成历史保持不变。新版《AI+ 创新大赛》与已确认《Working RAG 与用户控制增量设计》调整 Task 16、18、19、20、28、30、31、32：加入 Context Assembler 投影、`low/mid/high` 候选路径、上下文化 Working 检索、无低分硬拒、完成确认、Working error 兼容路由和产品定位验收。必要条件 gate 因规则未定义而不实现。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前 deterministic Python core 扩展为具有真实 LLM/RAG、文件检索、SQL 持久化、可恢复工作流、FastAPI/SSE 与 React 前端的 v1.0 完整产品。

**Architecture:** 保持五 Agent 的 Agent-oriented modular monolith；Agent 只产生结构化建议，Harness 独占路由、评分、状态和事务裁决。外部模型、OpenAlex、Anydoc、ranker、SQL 与文件存储都通过 ports/adapters 接入，Web API 只调用 application commands，React 只消费稳定的 HTTP/SSE contract。

**Tech Stack:** Python 3.12、uv、Pydantic 2、FastAPI、SQLAlchemy async、Alembic、SQLite/PostgreSQL、OpenAI Responses API/OpenAI-compatible API、OpenAlex、Anydoc、FlagEmbedding（可选）、React 19、TypeScript、Vite、Vitest、Playwright。

---

## 0. 执行规则与完成定义

- 所有 Python 依赖只用 `uv add` 管理；frontend 依赖用 npm lockfile 固定。
- 每个任务按 RED → GREEN → regression → commit 执行；不得把多个任务合成一次大改。
- 开始实现前使用 `using-git-worktrees` 创建隔离 worktree；不得直接在设计分支写 production code。
- 每个 Agent 的固定 Prompt 文件保持静态；动态信息只通过 typed input 注入。
- 每次 commit 前运行该任务的定向测试和 `uv run pytest -q -p no:cacheprovider`。
- frontend 建立后，每次 frontend commit 前运行 `npm test -- --run` 与 `npm run build`。
- v1.0 完成条件：设计规格第 16 节 34 项场景全部自动化或人工可复验，Python/unit、frontend/unit、Playwright/E2E 全绿，README 可从空数据库启动。

## 1. 目标文件结构

```text
src/research_mentor/
├── api/                    # FastAPI composition、HTTP/SSE routes、DTO/error mapping
├── application/            # commands、queries、durable run worker、demo seed
├── agents/                 # 五 Agent contracts/prompting/runner
├── domain/                 # project、conversation、document、job、research models
├── harness/                # phase、routing、scoring、orchestrator、validation queue
├── ports/                  # model/retrieval/repository/parser/file/event abstractions
└── adapters/
    ├── documents/          # safe local storage、Anydoc/plain-text parser、chunker
    ├── llm/                # OpenAI Responses/OpenAI-compatible structured output
    ├── retrieval/          # OpenAlex、lexical/FlagEmbedding ranker
    └── sql/                # SQLAlchemy models、repositories、unit of work
frontend/
├── src/api/                # typed client、SSE、contract types
├── src/components/         # shell、timeline、evidence、task/result panels
├── src/features/           # idea、plan、working、completion phase views
└── tests/e2e/              # Playwright user journeys
migrations/                 # Alembic migrations
tests/                      # Python unit/integration/API/eval tests
evals/                      # versioned cases and deterministic runner
```

## Milestone A：Contracts 与 Harness 状态机

### Task 1: 固定 v1 依赖、配置与应用启动契约

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/research_mentor/config.py`
- Create: `src/research_mentor/application/__init__.py`
- Test: `tests/test_config_and_errors.py`

- [ ] **Step 1: 写配置失败测试**

```python
def test_settings_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_MODEL_PROVIDER", "unknown")
    with pytest.raises(ValidationError):
        Settings()

def test_settings_defaults_to_demo_and_sqlite(monkeypatch):
    monkeypatch.delenv("RESEARCH_MENTOR_MODEL_PROVIDER", raising=False)
    settings = Settings()
    assert settings.model_provider == "demo"
    assert settings.database_url.startswith("sqlite+aiosqlite:///")
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/test_config_and_errors.py -q -p no:cacheprovider`

Expected: FAIL，`Settings` 尚无 provider/database typed fields。

- [ ] **Step 3: 添加依赖并实现配置**

Run:

```powershell
uv add fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" aiosqlite alembic httpx anyio pydantic-settings python-multipart openai firecrawl-anydoc
uv add --group dev pytest-asyncio respx
uv lock --check
```

核心配置：

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESEARCH_MENTOR_", extra="forbid")
    model_provider: Literal["demo", "openai", "openai_compatible"] = "demo"
    model_name: str = "gpt-5-mini"
    model_base_url: HttpUrl | None = None
    model_api_key: SecretStr | None = None
    database_url: str = "sqlite+aiosqlite:///./research_mentor.db"
    upload_root: Path = Path("./data/uploads")
    public_base_url: HttpUrl = HttpUrl("http://localhost:8000")
    demo_mode: bool = True
```

- [ ] **Step 4: 运行 GREEN 与全量回归**

Run: `uv run pytest tests/test_config_and_errors.py -q -p no:cacheprovider`

Expected: PASS。

Run: `uv run pytest -q -p no:cacheprovider`

Expected: 原有测试全部 PASS。

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml uv.lock src/research_mentor/config.py src/research_mentor/application/__init__.py tests/test_config_and_errors.py
git commit -m "构建：加入 v1 应用依赖与类型化配置"
```

### Task 2: 增加项目、对话、文档与 AgentRun 领域模型

**Files:**
- Create: `src/research_mentor/domain/projects.py`
- Create: `src/research_mentor/domain/conversations.py`
- Create: `src/research_mentor/domain/documents.py`
- Create: `src/research_mentor/domain/jobs.py`
- Modify: `src/research_mentor/domain/__init__.py`
- Test: `tests/domain/test_projects.py`
- Test: `tests/domain/test_conversations.py`
- Test: `tests/domain/test_documents.py`
- Test: `tests/domain/test_jobs.py`

- [ ] **Step 1: 写四组规范 model 的失败测试**

```python
def test_research_project_requires_positive_version():
    with pytest.raises(ValidationError):
        ResearchProject(project_id="p1", title="缓存研究", domain="computer_science", session_id="s1", version=0, created_at=NOW, updated_at=NOW)

def test_conversation_turn_preserves_provenance():
    turn = ConversationTurn(turn_id="t1", role="assistant", content="结论", created_at=NOW, agent_name="working_qa_agent", evidence_ids=["e1"])
    assert turn.evidence_ids == ["e1"]

def test_uploaded_document_requires_digest_and_size():
    document = UploadedDocument(document_id="d1", project_id="p1", original_name="notes.md", media_type="text/markdown", size_bytes=7, sha256="a" * 64, status="uploaded", created_at=NOW)
    assert document.error_message is None

def test_agent_run_supports_timeout_as_public_status():
    run = AgentRun(run_id="r1", project_id="p1", command_id="c1", agent_name="idea_review", status="timed_out", attempt=1, started_at=NOW, finished_at=NOW, public_message="模型调用超时", error_code="model_timeout")
    assert run.status == "timed_out"
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/domain/test_projects.py tests/domain/test_conversations.py tests/domain/test_documents.py tests/domain/test_jobs.py -q -p no:cacheprovider`

Expected: FAIL，四个 v1 model 尚不存在。

- [ ] **Step 3: 按 confirmed spec 实现公开领域模型**

```python
class ResearchProject(BaseModel):
    project_id: str
    title: str
    domain: str
    session_id: str
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

class ConversationTurn(BaseModel):
    turn_id: str
    role: Literal["user", "assistant", "system_event"]
    content: str
    created_at: datetime
    agent_name: AgentName | None = None
    evidence_ids: list[str] = Field(default_factory=list)

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

AgentRunStatus = Literal["queued", "running", "succeeded", "failed", "timed_out", "cancelled"]

class AgentRun(BaseModel):
    run_id: str
    project_id: str
    command_id: str
    agent_name: AgentName
    status: AgentRunStatus
    attempt: int = Field(ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    public_message: str | None = None
    error_code: str | None = None
```

重试上限、lease 和 storage key 只作为 application/persistence 内部字段，不能替代这些公开字段。

- [ ] **Step 4: 运行 GREEN 与回归**

Run: `uv run pytest tests/domain/test_projects.py tests/domain/test_conversations.py tests/domain/test_documents.py tests/domain/test_jobs.py -q -p no:cacheprovider`

Expected: PASS。

Run: `uv run pytest -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/domain tests/domain
git commit -m "功能：增加 v1 项目对话文档与运行模型"
```

### Task 3: 固定 ForwardResearchContext、ResearchContext 与 Idea Review action

**Files:**
- Modify: `src/research_mentor/domain/research.py`
- Modify: `src/research_mentor/agents/idea_review/contracts.py`
- Modify: `src/research_mentor/agents/idea_review/prompting.py`
- Modify: `src/research_mentor/agents/idea_review/prompt.md`
- Test: `tests/domain/test_research_context.py`
- Test: `tests/agents/test_idea_review.py`
- Test: `tests/agents/test_prompt_contracts.py`

- [ ] **Step 1: 写 action、stage 与恰一上下文测试**

```python
def test_proceed_to_working_requires_complete_forward_context():
    with pytest.raises(ValidationError):
        make_review(action="proceed_to_working", forward_context=make_forward(missing_fields=["main_result"]))

def test_validation_in_progress_requires_main_result_and_current_experiment():
    with pytest.raises(ValidationError):
        ForwardResearchContext(stage="validation_in_progress", research_question="缓存策略是否降低尾延迟？", main_result=MAIN_RESULT)

def test_research_context_requires_exactly_one_source():
    with pytest.raises(ValidationError):
        ResearchContext(normalized_idea="缓存研究", research_question="是否降低尾延迟？")
    with pytest.raises(ValidationError):
        ResearchContext(normalized_idea="缓存研究", research_question="是否降低尾延迟？", plan=PLAN, forward_context=FORWARD_CONTEXT)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/domain/test_research_context.py tests/agents/test_idea_review.py tests/agents/test_prompt_contracts.py -q -p no:cacheprovider`

Expected: FAIL，forward stage/cross-field/ResearchContext 尚未实现。

- [ ] **Step 3: 实现唯一规范 contract 与 validators**

```python
ForwardStage = Literal["experiment_in_progress", "main_experiment_completed", "validation_in_progress", "research_completed"]

class ForwardResearchContext(BaseModel):
    stage: ForwardStage
    research_question: str
    current_experiment: ExperimentInfo | None = None
    main_result: MainExperimentResult | None = None
    completed_validations: list[ValidationResult] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_stage_payload(self) -> Self:
        has_current = self.current_experiment is not None and bool((self.current_experiment.current_experiment or "").strip())
        if self.stage == "experiment_in_progress" and not has_current:
            raise ValueError("experiment_in_progress requires current_experiment")
        if self.stage in {"main_experiment_completed", "research_completed"} and self.main_result is None:
            raise ValueError("completed stage requires main_result")
        if self.stage == "validation_in_progress" and (self.main_result is None or not has_current):
            raise ValueError("validation_in_progress requires main_result and current_experiment")
        return self

class ResearchContext(BaseModel):
    normalized_idea: str
    research_question: str
    plan: ResearchPlan | None = None
    forward_context: ForwardResearchContext | None = None

    @model_validator(mode="after")
    def validate_exactly_one_source(self) -> Self:
        if (self.plan is None) == (self.forward_context is None):
            raise ValueError("exactly one of plan or forward_context is required")
        return self
```

给现有 `IdeaReviewOutput` 增加 `forward_context: ForwardResearchContext | None`；保留 `idea_type: opinion|range|forward` 和 `action: proceed_to_plan|proceed_to_working|request_refinement|reject`。只有 `proceed_to_working` 可携带 forward context，且必须 `missing_fields == []`；其余 action 必须无该字段。Prompt 明确范围不清使用 `request_refinement`，forward 信息不足也只能 refinement。

- [ ] **Step 4: 运行 GREEN 与 Prompt isolation 回归**

Run: `uv run pytest tests/domain/test_research_context.py tests/agents/test_idea_review.py tests/agents/test_prompt_contracts.py -q -p no:cacheprovider`

Expected: PASS；四个 stage、四个 action 和不可信附件隔离均有断言。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/domain/research.py src/research_mentor/agents/idea_review tests/domain/test_research_context.py tests/agents
git commit -m "功能：固定 forward 与研究上下文契约"
```

### Task 4: 完整化 Complete、validation selection 与实验结果影响

**Files:**
- Create: `src/research_mentor/domain/completion.py`
- Modify: `src/research_mentor/domain/experiments.py`
- Modify: `src/research_mentor/domain/__init__.py`
- Modify: `src/research_mentor/agents/complete/contracts.py`
- Modify: `src/research_mentor/agents/complete/prompt.md`
- Modify: `src/research_mentor/agents/complete/prompting.py`
- Test: `tests/domain/test_completion.py`
- Test: `tests/domain/test_experiments.py`
- Test: `tests/agents/test_working_and_complete.py`

- [ ] **Step 1: 写三种 mode、selection 和科学结果测试**

```python
def test_validation_mode_requires_ranked_unique_candidates():
    with pytest.raises(ValidationError):
        CompleteAgentOutput(mode="validation", plan=PLAN, final_hint="选择验证", validation_candidates=[])

def test_finish_without_validation_requires_reason_and_no_selection():
    with pytest.raises(ValidationError):
        ValidationSelection(selected_candidate_ids=["v1"], finish_without_more_validation=True, user_reason="资源不足")

def test_negative_scientific_finding_is_completed_execution():
    result = MainExperimentResult(objective="比较延迟", method="基准测试", actual_result="尾延迟升高", conclusion="不支持预期", execution_status="completed", impact="contradicts")
    assert result.failure_reason is None

def test_result_enums_are_exact():
    assert set(get_args(ResultImpact)) == {"supports", "neutral", "contradicts", "invalidates"}
    assert set(get_args(ExecutionStatus)) == {"completed", "failed", "cancelled"}
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/domain/test_completion.py tests/domain/test_experiments.py tests/agents/test_working_and_complete.py -q -p no:cacheprovider`

Expected: FAIL，Complete/selection/result v1 contract 尚未实现。

- [ ] **Step 3: 实现规范 models 与全部 cross-field validators**

```python
ValidationPriority = Literal["critical", "high", "medium", "low"]
CompletionMode = Literal["validation", "plan_revision", "writing"]
ResultImpact = Literal["supports", "neutral", "contradicts", "invalidates"]
ExecutionStatus = Literal["completed", "failed", "cancelled"]

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

class CompleteAgentOutput(BaseModel):
    mode: CompletionMode
    plan: ResearchPlan | None
    final_hint: str
    validation_candidates: list[ValidationCandidate] = Field(default_factory=list)
    excluded_validations: list[ExcludedValidation] = Field(default_factory=list)
    writing_guidance: WritingGuidance | None = None
    revision_reason: str | None = None

class ValidationSelection(BaseModel):
    selected_candidate_ids: list[str] = Field(default_factory=list)
    skipped_candidate_ids: list[str] = Field(default_factory=list)
    finish_without_more_validation: bool = False
    user_reason: str | None = None
```

`CompleteAgentOutput` validator 强制：validation 至少一个 candidate 且没有 writing/revision payload；plan revision 必须只有非空 reason；writing 必须只有 guidance。candidate ID/rank 均唯一。`ValidationSelection` 强制 selected/skipped 不重叠，结束选择时 selected 为空且 reason 非空。给 `MainExperimentResult`、`ValidationResult` 增加 `execution_status`、`impact`、`failure_reason`；Complete output 不包含结果影响或完成布尔值。

- [ ] **Step 4: 运行 GREEN 与全量回归**

Run: `uv run pytest tests/domain/test_completion.py tests/domain/test_experiments.py tests/agents/test_working_and_complete.py -q -p no:cacheprovider`

Expected: PASS。

Run: `uv run pytest -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/domain src/research_mentor/agents/complete tests/domain tests/agents/test_working_and_complete.py
git commit -m "功能：补全 Complete 与实验结果契约"
```

### Task 5: 迁移 SessionPhase、PlanLoop round 与 Harness 权威评分

**Files:**
- Modify: `src/research_mentor/config.py`
- Modify: `src/research_mentor/agents/plan_loop/contracts.py`
- Modify: `src/research_mentor/domain/checks.py`
- Modify: `src/research_mentor/harness/state.py`
- Create: `src/research_mentor/harness/task_factory.py`
- Modify: `src/research_mentor/harness/scoring.py`
- Test: `tests/agents/test_plan_and_check.py`
- Test: `tests/harness/test_state_v1.py`
- Test: `tests/harness/test_scoring.py`

- [ ] **Step 1: 写精确 phase、round 与 total-only decision 测试**

```python
def test_session_phase_values_are_exact():
    assert {phase.value for phase in SessionPhase} == {"awaiting_idea", "awaiting_idea_refinement", "planning", "checking_key_insight", "awaiting_plan_decision", "awaiting_working_context", "working", "awaiting_result_record", "completing", "awaiting_validation_selection", "awaiting_plan_revision_decision", "completed", "rejected", "check_loop_exhausted"}

def test_plan_loop_round_fields_are_explicit():
    value = PlanLoopInput(idea=IDEA, sys_input=SYS, review_result=REVIEW, check_round=0, max_check_rounds=5)
    assert value.check_round == 0 and value.max_check_rounds == 5

def test_harness_score_has_no_dimension_veto():
    decision = score_check(scores(research_fit=8, novelty=8, research_value=8, testability_feasibility=8, evidence_support=1), pass_score=6.0)
    assert decision.final_score == 6.9 and decision.passed is True
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/agents/test_plan_and_check.py tests/harness/test_state_v1.py tests/harness/test_scoring.py -q -p no:cacheprovider`

Expected: FAIL，新增 revision decision phase、round fields 与 Harness score authority 尚不存在。

- [ ] **Step 3: 实现唯一 SessionPhase 和权威 check record**

```python
class SessionPhase(StrEnum):
    AWAITING_IDEA = "awaiting_idea"
    AWAITING_IDEA_REFINEMENT = "awaiting_idea_refinement"
    PLANNING = "planning"
    CHECKING_KEY_INSIGHT = "checking_key_insight"
    AWAITING_PLAN_DECISION = "awaiting_plan_decision"
    AWAITING_WORKING_CONTEXT = "awaiting_working_context"  # 只读迁移旧 session
    WORKING = "working"
    AWAITING_RESULT_RECORD = "awaiting_result_record"
    COMPLETING = "completing"
    AWAITING_VALIDATION_SELECTION = "awaiting_validation_selection"
    AWAITING_PLAN_REVISION_DECISION = "awaiting_plan_revision_decision"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CHECK_LOOP_EXHAUSTED = "check_loop_exhausted"

class CheckRound(BaseModel):
    check_round: int = Field(ge=1)
    output: KeyInsightCheckOutput
    final_score: float = Field(ge=0, le=10)
    passed: bool

def score_check(scores: KeyInsightScores, pass_score: float) -> CheckDecision:
    total = round(0.20 * scores.research_fit.score + 0.25 * scores.novelty.score + 0.20 * scores.research_value.score + 0.20 * scores.testability_feasibility.score + 0.15 * scores.evidence_support.score, 1)
    return CheckDecision(final_score=total, passed=total >= pass_score)
```

把 Plan Loop 轮次字段统一为 `check_round: int = Field(ge=0)` 与 `max_check_rounds: int = Field(ge=1)`；Settings 增加 `max_check_rounds=5`、`check_pass_score=6.0`。`KeyInsightCheckOutput` 只保留语义 assessment/revision request，删除模型侧权威总分与决策。`TaskFactory` 是新 task ID/status/default fields 的唯一来源，新 session 永不写入兼容 phase。

- [ ] **Step 4: 运行 GREEN 与全量回归**

Run: `uv run pytest tests/agents/test_plan_and_check.py tests/harness/test_state_v1.py tests/harness/test_scoring.py -q -p no:cacheprovider`

Expected: PASS，模型输出无法覆盖 Harness 分数或 pass decision。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/config.py src/research_mentor/agents/plan_loop/contracts.py src/research_mentor/domain/checks.py src/research_mentor/harness tests/agents/test_plan_and_check.py tests/harness
git commit -m "功能：校准 v1 phase 与 Check 权威评分"
```

### Task 6: 实现规范 completion routing 与 validation queue

**Files:**
- Modify: `src/research_mentor/harness/routing.py`
- Create: `src/research_mentor/harness/validation.py`
- Test: `tests/harness/test_completion_routing.py`
- Test: `tests/harness/test_validation_queue.py`

- [ ] **Step 1: 写三路路由与 selection 失败测试**

```python
@pytest.mark.parametrize(("mode", "phase"), [("validation", SessionPhase.AWAITING_VALIDATION_SELECTION), ("plan_revision", SessionPhase.AWAITING_PLAN_REVISION_DECISION), ("writing", SessionPhase.COMPLETED)])
def test_complete_mode_routes_deterministically(mode, phase):
    output = make_complete_output(mode=mode, final_hint="下一步")
    decision = route_complete(output)
    assert decision.next_phase is phase and decision.reason == "下一步"

def test_selected_candidates_are_queued_by_rank_not_request_order():
    queue = ValidationQueue.from_candidates(CANDIDATES)
    selected = queue.apply(ValidationSelection(selected_candidate_ids=["v3", "v1"], skipped_candidate_ids=["v2"]))
    assert [item.candidate.candidate_id for item in selected.selected] == ["v1", "v3"]

def test_finish_override_requires_user_reason():
    with pytest.raises(ValidationSelectionError):
        ValidationQueue.from_candidates(CANDIDATES).apply(ValidationSelection(finish_without_more_validation=True))
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_completion_routing.py tests/harness/test_validation_queue.py -q -p no:cacheprovider`

Expected: FAIL，新路由与 candidate-ID queue 尚未实现。

- [ ] **Step 3: 实现 pure routing、rank queue 和永久选择记录**

```python
def route_complete(output: CompleteAgentOutput) -> RoutingDecision:
    phase_by_mode = {"validation": SessionPhase.AWAITING_VALIDATION_SELECTION, "plan_revision": SessionPhase.AWAITING_PLAN_REVISION_DECISION, "writing": SessionPhase.COMPLETED}
    return RoutingDecision(next_phase=phase_by_mode[output.mode], reason=output.final_hint)

class ValidationQueue(BaseModel):
    offered: list[ValidationCandidate]
    selected: list[QueuedValidation] = Field(default_factory=list)
    skipped: list[SkippedValidation] = Field(default_factory=list)
```

`apply(selection)` 只接受当前 candidate ID，拒绝未知、重复、selected/skipped 重叠；selected 按 `candidate.rank` 排序。拒绝 critical candidate 时永久保存 candidate、导师 rationale 和 user reason。结束选择返回 `COMPLETING` 与 override record；普通选择只激活队首并进入 `WORKING`。创建新 candidates 时排除已排队或已完成 task。

- [ ] **Step 4: 运行 GREEN 与回归**

Run: `uv run pytest tests/harness/test_completion_routing.py tests/harness/test_validation_queue.py -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/harness/routing.py src/research_mentor/harness/validation.py tests/harness/test_completion_routing.py tests/harness/test_validation_queue.py
git commit -m "功能：实现规范完成路由与验证队列"
```

## Milestone B：持久化、文档与检索 Providers

### Task 7: 定义 repository、unit of work 与 event ports

**Files:**
- Modify: `src/research_mentor/ports/repository.py`
- Create: `src/research_mentor/ports/events.py`
- Create: `src/research_mentor/ports/files.py`
- Create: `src/research_mentor/ports/documents.py`
- Test: `tests/ports/test_repository_contract.py`

- [ ] **Step 1: 写 command identity、version 与规范 port contract test**

```python
async def test_uow_finds_processed_command_by_command_id(repository_uow):
    async with repository_uow() as uow:
        await uow.processed_commands.add(PROCESSED_COMMAND)
    async with repository_uow() as uow:
        found = await uow.processed_commands.find("p1", "c1")
    assert found.receipt == PROCESSED_COMMAND.receipt

def test_expected_version_rejects_zero():
    with pytest.raises(ValidationError):
        ExpectedVersion(expected_version=0)

def test_ports_use_v1_boundary_names():
    assert all(value is not None for value in (RepositoryPort, FileStorePort, DocumentParserPort, PublicEventPublisherPort))
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/ports/test_repository_contract.py -q -p no:cacheprovider`

Expected: FAIL，UoW/event/file/parser contracts 不存在。

- [ ] **Step 3: 定义唯一 v1 ports 与 version wrapper**

```python
class ExpectedVersion(BaseModel):
    expected_version: int = Field(ge=1)

class RepositoryPort(Protocol):
    projects: ProjectRepository
    sessions: SessionRepository
    processed_commands: ProcessedCommandRepository
    runs: AgentRunRepository
    documents: DocumentRepository
    literature: LiteratureRepository
    events: SessionEventRepository
    outbox: OutboxRepository
    agent_outputs: AgentOutputRepository
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...

class ProcessedCommandRepository(Protocol):
    async def find(self, project_id: str, command_id: str) -> ProcessedCommand | None: ...
    async def add(self, command: ProcessedCommand) -> None: ...

class FileStorePort(Protocol):
    async def put(self, project_id: str, document_id: str, content: AsyncIterator[bytes]) -> StoredFile: ...
    async def open(self, stored_file: StoredFile) -> AsyncIterator[bytes]: ...
    async def remove(self, stored_file: StoredFile) -> None: ...

class DocumentParserPort(Protocol):
    async def parse(self, stored_file: StoredFile, media_type: str) -> ParsedDocument: ...

class PublicEventPublisherPort(Protocol):
    async def publish_pending(self, events: Sequence[OutboxEvent]) -> None: ...
```

重复 `(project_id, command_id)` 返回已保存 receipt/run；任何 mutation 的合法 `expected_version` 不匹配时抛 `ConcurrencyConflict`，且不产生部分写入。

- [ ] **Step 4: 运行 GREEN 与 memory adapter 回归**

Run: `uv run pytest tests/ports/test_repository_contract.py tests/adapters/test_memory_repository.py -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/ports src/research_mentor/adapters/memory tests/ports tests/adapters/test_memory_repository.py
git commit -m "架构：定义 v1 持久化与文件端口"
```

### Task 8: 建立 SQLAlchemy schema 与 Alembic migration

**Files:**
- Create: `src/research_mentor/adapters/sql/base.py`
- Create: `src/research_mentor/adapters/sql/models.py`
- Create: `src/research_mentor/adapters/sql/session.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/versions/20260830_0001_v1_schema.py`
- Test: `tests/adapters/sql/test_migrations.py`

- [ ] **Step 1: 写 migration smoke test**

```python
def test_upgrade_head_creates_v1_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    run_migrations(url, "head")
    assert expected_tables(url) == {
        "alembic_version", "projects", "research_sessions", "session_events",
        "outbox_events", "agent_runs", "processed_commands", "conversation_turns",
        "documents", "document_chunks", "literature_records", "project_literature",
        "validation_types", "agent_outputs", "research_exports",
    }
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/sql/test_migrations.py -q -p no:cacheprovider`

Expected: FAIL，migration config 不存在。

- [ ] **Step 3: 实现 schema 与初始 migration**

必须包含 UUID/text primary key、project foreign keys、`research_sessions.version/phase/updated_at/payload`、JSON payload 和 UTC timestamps。`processed_commands(project_id,command_id)` 唯一；`session_events(project_id,sequence)` 唯一；`outbox_events` 关联对应 session event 并记录 publish state；documents/chunks cascade delete。`agent_outputs` 包含 run ID、agent name、Prompt version、session version 与 structured payload。SQLAlchemy rows 只负责 persistence mapping，不继承 domain models。

关键约束：

```python
UniqueConstraint("project_id", "command_id", name="uq_processed_command")
UniqueConstraint("project_id", "sequence", name="uq_session_event_sequence")
CheckConstraint("version >= 1", name="ck_research_session_version_positive")
ForeignKeyConstraint(["session_event_id"], ["session_events.event_id"], name="fk_outbox_session_event")
```

- [ ] **Step 4: 运行 upgrade/downgrade/GREEN**

Run: `uv run pytest tests/adapters/sql/test_migrations.py -q -p no:cacheprovider`

Expected: PASS，`upgrade head → downgrade base → upgrade head` 均成功。

- [ ] **Step 5: Commit**

```powershell
git add alembic.ini migrations src/research_mentor/adapters/sql tests/adapters/sql/test_migrations.py
git commit -m "功能：建立 v1 SQL 持久化结构"
```

### Task 9: 实现 SQL UnitOfWork、乐观并发与 outbox event

**Files:**
- Create: `src/research_mentor/adapters/sql/mappers.py`
- Create: `src/research_mentor/adapters/sql/repositories.py`
- Create: `src/research_mentor/adapters/sql/uow.py`
- Test: `tests/adapters/sql/test_uow.py`
- Test: `tests/adapters/sql/test_concurrency.py`

- [ ] **Step 1: 写原子性和并发测试**

```python
async def test_uow_rolls_back_state_and_event_on_error(sql_uow):
    with pytest.raises(RuntimeError):
        async with sql_uow() as uow:
            await uow.sessions.save(UPDATED_SESSION, expected_version=1)
            await uow.events.append(SESSION_EVENT)
            await uow.outbox.append(OUTBOX_EVENT)
            raise RuntimeError("abort")
    assert await session_version(sql_uow, "s1") == 1
    assert await count_rows(sql_uow, "session_events") == 0
    assert await count_rows(sql_uow, "outbox_events") == 0

async def test_stale_session_update_raises_conflict(sql_uow, seeded_session):
    async with sql_uow() as uow:
        with pytest.raises(ConcurrencyConflict):
            await uow.sessions.save(seeded_session, expected_version=1)

async def test_successful_agent_commit_is_one_transaction(sql_uow):
    async with sql_uow() as uow:
        await uow.sessions.save(UPDATED_SESSION, expected_version=1)
        await uow.events.append(SESSION_EVENT)
        await uow.outbox.append(OUTBOX_EVENT)
        await uow.agent_outputs.add(AGENT_OUTPUT)
    assert await session_version(sql_uow, "s1") == 2
    assert await count_rows(sql_uow, "session_events") == 1
    assert await count_rows(sql_uow, "outbox_events") == 1
    assert await count_rows(sql_uow, "agent_outputs") == 1
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/sql/test_uow.py tests/adapters/sql/test_concurrency.py -q -p no:cacheprovider`

Expected: FAIL，repositories/uow 不存在。

- [ ] **Step 3: 实现 transaction 与 compare-and-swap**

```python
stmt = (
    update(ResearchSessionRow)
    .where(ResearchSessionRow.session_id == session.session_id, ResearchSessionRow.version == expected_version)
    .values(payload=session.model_dump(mode="json"), phase=session.phase.value, updated_at=now, version=expected_version + 1)
)
result = await self._db.execute(stmt)
if result.rowcount != 1:
    raise ConcurrencyConflict(session.id, expected_version)
```

UoW `__aexit__` 在无异常时 commit，有异常时 rollback。CAS update、`session_events`、`outbox_events`、`processed_commands` 与成功的 `agent_outputs` 必须使用同一 `AsyncSession`；stale CAS 在追加任何 event/output 前失败。outbox publisher 只在 transaction commit 后发布，重试 publish 不重写 domain event。

- [ ] **Step 4: 运行 GREEN 与 repository contract suite**

Run: `uv run pytest tests/adapters/sql tests/ports/test_repository_contract.py -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/adapters/sql tests/adapters/sql
git commit -m "功能：实现 SQL 事务与乐观并发"
```

### Task 10: 实现安全文件存储、解析与 chunking

**Files:**
- Create: `src/research_mentor/adapters/filestore/local.py`
- Create: `src/research_mentor/adapters/documents/plain_text.py`
- Create: `src/research_mentor/adapters/documents/anydoc.py`
- Create: `src/research_mentor/adapters/documents/chunking.py`
- Test: `tests/adapters/documents/test_storage.py`
- Test: `tests/adapters/documents/test_parsers.py`
- Test: `tests/adapters/documents/test_chunking.py`

- [ ] **Step 1: 写安全与 deterministic chunk 测试**

```python
async def test_local_store_never_uses_user_name_as_path(tmp_path):
    store = LocalFileStore(tmp_path)
    saved = await store.put("p1", "d1", bytes_stream(b"hello"))
    assert saved.path == tmp_path / "p1" / "d1" / "source.bin"

def test_chunker_returns_normative_document_chunks():
    chunks = MarkdownChunker(max_chars=12, overlap_chars=3).split("d1", "# 方法\n第一段内容。\n\n第二段内容。")
    assert chunks[0].chunk_id
    assert chunks[0].ordinal == 0
    assert chunks[0].heading_path == ["方法"]
    assert chunks[0].markdown
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/documents -q -p no:cacheprovider`

Expected: FAIL，document adapters 不存在。

- [ ] **Step 3: 实现 storage/parser/chunker**

`LocalFileStore` 路径固定为 `{root}/{safe_project_id}/{document_id}/source.bin`，文件名只进入 database metadata，不参与路径；拒绝越界 ID 且不执行用户文件。`PlainTextParser` 支持 `text/plain` 与 Markdown；`AnydocParser` 在线程池中转换为规范 Markdown，解析异常映射为 typed `DocumentParseFailed`。`MarkdownChunker` 使用标题/段落优先边界，内部可以保留 offset metadata，但公开 domain output 只能使用下列字段：

```python
class ParsedDocument(BaseModel):
    markdown: str
    parser_metadata: dict[str, JsonValue] = Field(default_factory=dict)

class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    ordinal: int = Field(ge=0)
    heading_path: list[str] = Field(default_factory=list)
    markdown: str
```

- [ ] **Step 4: 运行 GREEN 与 traversal regression**

Run: `uv run pytest tests/adapters/documents -q -p no:cacheprovider`

Expected: PASS，包括绝对路径、`..`、Unicode 文件名与空文件。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/adapters/filestore src/research_mentor/adapters/documents tests/adapters/documents
git commit -m "功能：实现安全文档存储解析与切块"
```

### Task 11: 实现 OpenAlex 文献检索 adapter

**Files:**
- Create: `src/research_mentor/adapters/openalex/client.py`
- Create: `src/research_mentor/adapters/openalex/mapping.py`
- Modify: `src/research_mentor/domain/evidence.py`
- Modify: `src/research_mentor/ports/retrieval.py`
- Test: `tests/adapters/retrieval/test_openalex.py`

- [ ] **Step 1: 写 HTTP contract tests**

```python
async def test_openalex_maps_work_to_literature_record(respx_mock):
    respx_mock.get("https://api.openalex.org/works").mock(return_value=Response(200, json=OPENALEX_PAGE))
    records = await OpenAlexRetriever(httpx.AsyncClient(), mailto="dev@example.com").search("cache invalidation", limit=2)
    assert records[0].title == "A Cache Study"
    assert records[0].doi == "https://doi.org/10.1/example"
    assert records[0].provider == "openalex"
    assert records[0].provider_id == "https://openalex.org/W1"
    assert records[0].publication_date == date(2025, 6, 1)
    assert records[0].cited_by_count == 12
    assert records[0].query_id == "q1"

async def test_openalex_retries_429_once(respx_mock):
    route = respx_mock.get("https://api.openalex.org/works").mock(side_effect=[Response(429), Response(200, json=EMPTY_PAGE)])
    await OpenAlexRetriever(httpx.AsyncClient(), sleep=immediate_sleep).search("x")
    assert route.call_count == 2

def test_retrieval_diagnostics_distinguishes_empty_and_unavailable():
    assert RetrievalDiagnostics(query="x", provider="openalex", candidate_count=0, selected_count=0, top_relevance=None, status="empty").status == "empty"
    assert RetrievalDiagnostics(query="x", provider="openalex", candidate_count=0, selected_count=0, top_relevance=None, status="unavailable", limitation="timeout").status == "unavailable"
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/retrieval/test_openalex.py -q -p no:cacheprovider`

Expected: FAIL，OpenAlex adapter 不存在。

- [ ] **Step 3: 实现 query、mapping 与错误分类**

```python
params = {
    "search": query,
    "per-page": min(limit, 50),
    "select": "id,doi,title,publication_date,cited_by_count,authorships,primary_location,abstract_inverted_index",
    "mailto": self._mailto,
}
```

扩展现有 `LiteratureRecord`，保留原文献字段并新增 `record_id/provider/provider_id/publication_date/cited_by_count/retrieved_at/query_id`。定义：

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

只重试 429、502、503、504，最多 3 次并遵守 `Retry-After`；4xx 语义错误不重试。还原 abstract inverted index，缺失字段保留 `None`，不得生成 DOI/URL。映射时生成内部 `record_id/query_id/retrieved_at`，并依次按 provider ID、规范 DOI、规范 URL 去重；多 query 返回 `list[RetrievalDiagnostics]`，不改写单条 diagnostics schema。

- [ ] **Step 4: 运行 GREEN 与 network isolation test**

Run: `uv run pytest tests/adapters/retrieval/test_openalex.py -q -p no:cacheprovider`

Expected: PASS，测试不访问真实网络。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/adapters/openalex src/research_mentor/domain/evidence.py src/research_mentor/ports/retrieval.py tests/adapters/retrieval
git commit -m "功能：接入 OpenAlex 文献检索"
```

### Task 12: 实现项目 chunk 检索与可选 FlagEmbedding ranker

**Files:**
- Create: `src/research_mentor/application/retrieval_service.py`
- Create: `src/research_mentor/adapters/embeddings/flag_embedding.py`
- Create: `src/research_mentor/adapters/embeddings/lexical.py`
- Create: `src/research_mentor/adapters/embeddings/unavailable.py`
- Modify: `src/research_mentor/ports/retrieval.py`
- Modify: `pyproject.toml`
- Test: `tests/adapters/retrieval/test_project_chunks.py`
- Test: `tests/adapters/retrieval/test_ranking.py`

- [ ] **Step 1: 写 fallback 与 rank test**

```python
def test_lexical_ranker_is_deterministic():
    ranked = LexicalRanker().rank("缓存 延迟", CHUNKS, limit=2)
    assert [item.chunk.chunk_id for item in ranked.items] == ["c2", "c1"]
    assert all(0.0 <= item.score <= 1.0 for item in ranked.items)

def test_real_mode_uses_unavailable_ranker_without_optional_dependency(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)
    result = UnavailableRanker("FlagEmbedding 未安装").rank("x", CHUNKS, limit=2)
    assert result.status == "unavailable" and result.items == []

def test_ranker_port_has_one_result_contract():
    assert isinstance(LexicalRanker(), RetrievalRankerPort)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/retrieval/test_project_chunks.py tests/adapters/retrieval/test_ranking.py -q -p no:cacheprovider`

Expected: FAIL，ranker/retriever 不存在。

- [ ] **Step 3: 实现 SQL candidate query 和两种 ranker**

Run: `uv add --optional local-ranking FlagEmbedding`

定义唯一 port/result：

```python
class RankedChunk(BaseModel):
    chunk: DocumentChunk
    score: float = Field(ge=0.0, le=1.0)

class RankResult(BaseModel):
    status: Literal["ok", "unavailable"]
    items: list[RankedChunk] = Field(default_factory=list)
    limitation: str | None = None

@runtime_checkable
class RetrievalRankerPort(Protocol):
    def rank(self, query: str, chunks: Sequence[DocumentChunk], *, limit: int) -> RankResult: ...
```

`RetrievalService` 先按 `project_id` 召回 SQL candidates，再调用 ranker。real mode 未配置可选模型时使用 `UnavailableRanker`，不得用 lexical 低分触发真实 decline；`LexicalRanker` 只供 demo/test。`EvidenceRef.support` 必须由使用证据的 Agent/caller 写入具体判断，ranker 只返回相关度与 chunk provenance。

- [ ] **Step 4: 运行 GREEN 与 optional import regression**

Run: `uv run pytest tests/adapters/retrieval/test_project_chunks.py tests/adapters/retrieval/test_ranking.py -q -p no:cacheprovider`

Expected: PASS，默认环境不下载模型。

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml uv.lock src/research_mentor/application/retrieval_service.py src/research_mentor/adapters/embeddings src/research_mentor/ports/retrieval.py tests/adapters/retrieval
git commit -m "功能：实现项目文档检索与可选重排"
```

## Milestone C：真实 Structured Model 与 RAG 上下文

### Task 13: 将 StructuredModelPort 迁移为 async typed call

**Files:**
- Modify: `src/research_mentor/ports/model.py`
- Modify: `src/research_mentor/adapters/memory/model.py`
- Modify: `src/research_mentor/agents/*/runner.py`
- Test: `tests/ports/test_model_contract.py`
- Modify: `tests/agents/test_idea_review.py`
- Modify: `tests/agents/test_plan_and_check.py`
- Modify: `tests/agents/test_working_and_complete.py`

- [ ] **Step 1: 写 async contract test**

```python
async def test_scripted_model_validates_requested_schema():
    model = ScriptedStructuredModel([REJECT_REVIEW.model_dump(mode="json")])
    request = ModelRequest(agent_name="idea_review_agent", model_profile="test", instructions="mentor", user_input="<idea>x</idea>", output_model=IdeaReviewOutput, timeout=10.0, trace_id="trace-1")
    result = await model.generate(request)
    assert isinstance(result, IdeaReviewOutput)

async def test_scripted_model_rejects_wrong_schema():
    model = ScriptedStructuredModel([{"unexpected": True}])
    with pytest.raises(ModelOutputInvalid):
        await model.generate(ModelRequest(agent_name="idea_review_agent", model_profile="test", instructions="s", user_input="u", output_model=IdeaReviewOutput, timeout=10.0, trace_id="trace-2"))
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/ports/test_model_contract.py -q -p no:cacheprovider`

Expected: FAIL，现有 port 是同步且没有 `ModelRequest`。

- [ ] **Step 3: 实现 generic async port 并迁移 runners**

```python
OutputT = TypeVar("OutputT", bound=BaseModel)

class ModelRequest(BaseModel, Generic[OutputT]):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    agent_name: AgentName
    model_profile: str
    instructions: str
    user_input: str
    output_model: type[OutputT]
    timeout: float = Field(gt=0)
    trace_id: str

class StructuredModelPort(Protocol):
    async def generate(self, request: ModelRequest[OutputT]) -> OutputT: ...
```

五个 runner 都改成 `async def run(...)`，从 Harness 注入 `agent_name/model_profile/timeout/trace_id` 后构造一个 `ModelRequest` 并 `await model.generate(request)`；Prompt builder 保持 pure/sync。`MemoryModelAdapter` 只按 `request.output_model` 校验固定响应，不读取 provider 配置。

- [ ] **Step 4: 运行 GREEN 与 Agent regression**

Run: `uv run pytest tests/ports/test_model_contract.py tests/agents -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/ports/model.py src/research_mentor/adapters/memory/model.py src/research_mentor/agents tests/ports tests/agents
git commit -m "架构：迁移异步结构化模型端口"
```

### Task 14: 实现 OpenAI Responses 与 compatible adapters

**Files:**
- Create: `src/research_mentor/adapters/model/openai_responses.py`
- Create: `src/research_mentor/adapters/model/openai_compatible.py`
- Create: `src/research_mentor/adapters/model/errors.py`
- Test: `tests/adapters/llm/test_openai_responses.py`
- Test: `tests/adapters/llm/test_openai_compatible.py`

- [ ] **Step 1: 写 structured output mapping tests**

```python
async def test_responses_adapter_returns_parsed_model(fake_openai):
    fake_openai.responses.parse.return_value.output_parsed = REVIEW_OUTPUT
    result = await OpenAIResponsesModelAdapter(fake_openai).generate(REVIEW_REQUEST)
    assert result == REVIEW_OUTPUT
    kwargs = fake_openai.responses.parse.call_args.kwargs
    assert kwargs["model"] == REVIEW_REQUEST.model_profile
    assert kwargs["text_format"] is IdeaReviewOutput
    assert kwargs["timeout"] == REVIEW_REQUEST.timeout

async def test_compatible_adapter_maps_invalid_json(fake_http):
    fake_http.post.return_value = Response(200, json=INVALID_JSON_RESPONSE)
    with pytest.raises(ModelOutputInvalid):
        await OpenAICompatibleModelAdapter(fake_http, base_url="https://provider.test/v1").generate(REVIEW_REQUEST)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/llm -q -p no:cacheprovider`

Expected: FAIL，adapters 不存在。

- [ ] **Step 3: 实现 provider adapters**

`OpenAIResponsesModelAdapter` 使用 SDK `responses.parse(model=request.model_profile, instructions=request.instructions, input=request.user_input, text_format=request.output_model, timeout=request.timeout)`；`OpenAICompatibleModelAdapter` 发送 `request.output_model.model_json_schema()` 并用 `request.output_model.model_validate_json(content)`。两者以 `request.trace_id` 关联 provider request ID、model、latency 和 usage，但不记录 API key、完整文档或 instructions。Memory 与后续 Demo adapter 实现同一 `generate(request)` port。

```python
except (APITimeoutError, RateLimitError, APIConnectionError) as exc:
    raise ModelTemporarilyUnavailable(str(exc)) from exc
except ValidationError as exc:
    raise ModelOutputInvalid(errors=exc.errors()) from exc
```

- [ ] **Step 4: 运行 GREEN**

Run: `uv run pytest tests/adapters/llm -q -p no:cacheprovider`

Expected: PASS，全部用 fake/mock，无真实 API 调用。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/adapters/model tests/adapters/llm
git commit -m "功能：接入结构化 LLM providers"
```

### Task 15: 构建 Idea Review 两阶段检索上下文

**Files:**
- Create: `src/research_mentor/harness/retrieval_context.py`
- Modify: `src/research_mentor/agents/idea_review/runner.py`
- Modify: `src/research_mentor/agents/idea_review/contracts.py`
- Test: `tests/harness/test_idea_review_retrieval.py`

- [ ] **Step 1: 写 SearchPlan → retrieve/rank → review 的两调用测试**

```python
async def test_idea_review_uses_exactly_two_model_calls(spy_model, spy_retriever):
    result = await pipeline.review(project_id="p1", initial_input=INITIAL_INPUT)
    assert [call.output_model for call in spy_model.requests] == [SearchPlan, IdeaReviewOutput]
    assert spy_retriever.queries == list(SEARCH_PLAN.queries)
    assert result.evidence[0].support == "支撑尾延迟可测量性判断"

def test_search_plan_has_one_to_four_bounded_queries():
    plan = SearchPlan(queries=["cache invalidation tail latency"])
    assert 1 <= len(plan.queries) <= 4

async def test_unavailable_is_not_reported_as_empty(spy_model, unavailable_retriever):
    await pipeline_with(unavailable_retriever, spy_model).review(project_id="p1", initial_input=INITIAL_INPUT)
    final_request = spy_model.requests[-1]
    assert '"status":"unavailable"' in final_request.user_input
    assert '"limitation":"openalex_timeout"' in final_request.user_input
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_idea_review_retrieval.py -q -p no:cacheprovider`

Expected: FAIL，pipeline/context 不存在。

- [ ] **Step 3: 实现 bounded 两阶段 pipeline**

```python
search_plan = await model.generate(build_search_plan_request(initial_input, settings.idea_review_model_profile))
search_results = await openalex.search_many(search_plan.queries, limit_per_query=settings.openalex_limit)
ranked = await retrieval_service.rank_literature(initial_input.original_idea, search_results.records)
review_request = build_review_request(
    initial_input=initial_input,
    literature_records=deduplicate_literature(ranked.records),
    retrieval_diagnostics=search_results.diagnostics,
    model_profile=settings.idea_review_model_profile,
)
review = await model.generate(review_request)
return IdeaReviewTransaction(review=review, literature_records=search_results.records, diagnostics=search_results.diagnostics)
```

`SearchPlan` 根据 `InitialInput` 的 idea/domain/约束生成 1–4 条长度受限 query；不存在单独 normalization 模型调用，规范化 idea 由最终 `IdeaReviewOutput.normalized_idea` 产生。合并结果按 provider ID/DOI/URL 去重并为每条 query 保留 `RetrievalDiagnostics`；成功无结果写 `empty`，provider 失败写 `unavailable + limitation`。只有实际支撑判断的记录进入 `EvidenceRef`，但所有检索所得保留为 `LiteratureRecord`。

- [ ] **Step 4: 运行 GREEN 与 prompt injection regression**

Run: `uv run pytest tests/harness/test_idea_review_retrieval.py tests/agents/test_prompt_contracts.py -q -p no:cacheprovider`

Expected: PASS，文献/附件中的指令仅作为 quoted evidence。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/harness/retrieval_context.py src/research_mentor/agents/idea_review tests/harness/test_idea_review_retrieval.py
git commit -m "功能：实现 Idea Review 两阶段 RAG"
```

### Task 16: 构建 Working QA 的相关性选择与上下文压缩

**Files:**
- Create: `src/research_mentor/application/context_service.py`
- Modify: `src/research_mentor/config.py`
- Modify: `src/research_mentor/agents/working_qa/contracts.py`
- Modify: `src/research_mentor/agents/working_qa/runner.py`
- Test: `tests/harness/test_working_context.py`

- [ ] **Step 1: 写上下文预算和 evidence 测试**

```python
async def test_working_context_keeps_current_task_and_recent_results(builder):
    context = await builder.build(SESSION_WITH_LONG_HISTORY, "为什么延迟升高？", character_budget=12000)
    assert context.current_task.task_id == SESSION_WITH_LONG_HISTORY.current_task.task_id
    assert context.compact_context is not None
    assert context.compact_context.source_turn_ids
    assert all(ref.source_id for ref in context.evidence_refs)

async def test_compaction_preserves_facts_and_unresolved_questions(builder):
    context = await builder.build(SESSION_WITH_LONG_HISTORY, "下一步是什么？", character_budget=12000)
    assert context.compact_context.facts == ["主实验尾延迟升高 8%"]
    assert context.compact_context.unresolved_questions == ["是否为数据倾斜导致？"]

async def test_rank_unavailable_does_not_decline_question(builder_with_unavailable_ranker):
    context = await builder_with_unavailable_ranker.build(SESSION, "比较另一种缓存策略", character_budget=12000)
    assert context.rank_status == "unavailable"
    assert context.decline_as_unrelated is False

async def test_low_rank_is_diagnostic_and_never_short_circuits(builder):
    context = await builder.build(SESSION, "那第二个方案呢？", character_budget=12000)
    assert "缓存策略" in builder.ranker.last_query
    assert "当前实验" in builder.ranker.last_query
    assert context.top_relevance == 0.12 and context.decline_as_unrelated is False
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_working_context.py -q -p no:cacheprovider`

Expected: FAIL，working context builder 不存在。

- [ ] **Step 3: 实现 deterministic context policy**

顺序固定为：`ResearchContext`/current task → 结构化实验事实 → 最新用户输入 → recent `ConversationTurn` → selected document chunks/literature → `CompactContext`。检索 query 拼接 normalized idea、research question/forward stage、current task/current experiment 和 question。Working QA 继续继承 `RetrievalSysInput`；不得为其他三个非 retrieval Agent 注入 retrieval guidelines。rank score 只写 diagnostics，任何低分/empty/unavailable 都不得在模型前拒绝；`Settings.rag_relevance_threshold` 保留给 Task 30 校准，不驱动 v1 路由。

本 Task 同时固定 `ContextAssembler` 边界：每个 Agent 先做字段投影，再分别构造 stable instructions、project facts 和 turn payload。`sys_input` 只传给 instructions builder，严禁重复出现在序列化 `user_input`；也不得传入其他 Agent 专属字段、完整 session dump 或未选检索结果。为五个 runner 增加 prompt isolation regression，断言动态 JSON 中不存在 `sys_input`、`behavior_constraints`、`retrieval_guidelines` 等 instructions-only key。

```python
class CompactContext(BaseModel):
    summary: str
    source_turn_ids: list[str]
    facts: list[str]
    unresolved_questions: list[str]

class WorkingContext(BaseModel):
    research_context: ResearchContext
    current_task: ExperimentTaskContext
    recent_turns: list[ConversationTurn]
    compact_context: CompactContext | None
    evidence_refs: list[EvidenceRef]
    retrieval_diagnostics: list[RetrievalDiagnostics]
    rank_status: Literal["ok", "unavailable"]
    top_relevance: float | None
    decline_as_unrelated: bool
```

把 `WorkingQAInput` 的 plan/normalized idea/字符串列表压缩字段替换为 `research_context`、`conversation_turns` 和 `compact_context: CompactContext | None`。compaction 由 Harness application service 负责，不新增压缩 Agent 或第六个 Agent runner；它只能总结已有 turn，必须记录 source IDs，不能创造实验事实；原始 turns 永久保存在 SQL。

- [ ] **Step 4: 运行 GREEN 与长上下文 regression**

Run: `uv run pytest tests/harness/test_working_context.py -q -p no:cacheprovider`

Expected: PASS，并确保同输入产生相同排序和 summary boundary。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/application/context_service.py src/research_mentor/config.py src/research_mentor/agents/working_qa tests/harness/test_working_context.py
git commit -m "功能：实现 Working QA 上下文选择"
```

## Milestone D：完整 Orchestrator 与 Application Commands

### Task 17: 完成 Idea Review 四种 action 的 orchestration

**Files:**
- Modify: `src/research_mentor/harness/orchestrator.py`
- Modify: `src/research_mentor/harness/routing.py`
- Test: `tests/harness/test_orchestrator_idea_review_v1.py`

- [ ] **Step 1: 写四路集成测试**

```python
@pytest.mark.parametrize(("action", "phase"), [
    ("proceed_to_plan", SessionPhase.PLANNING),
    ("proceed_to_working", SessionPhase.WORKING),
    ("request_refinement", SessionPhase.AWAITING_IDEA_REFINEMENT),
    ("reject", SessionPhase.REJECTED),
])
async def test_review_action_has_single_route(action, phase, orchestrator_factory):
    session = await orchestrator_factory(review_output(action)).submit_idea(PROJECT_ID, INITIAL_INPUT)
    assert session.phase is phase

@pytest.mark.parametrize("stage", ["experiment_in_progress", "main_experiment_completed", "validation_in_progress", "research_completed"])
async def test_forward_initializes_research_context_and_stage_task(stage, orchestrator_factory):
    output = forward_output(stage)
    session = await orchestrator_factory(output).submit_idea(PROJECT_ID, INITIAL_INPUT)
    assert session.phase is SessionPhase.WORKING
    assert session.research_context.forward_context == output.forward_context
    assert session.research_context.plan is None
    assert session.current_task.origin == "forward"
    if stage in {"main_experiment_completed", "research_completed"}:
        assert session.current_task.experiment_info.current_experiment == "核对已有结果与补充验证需求"

async def test_non_cs_domain_returns_refinement_without_model(command_service, model_spy):
    view = await command_service.submit_idea(PROJECT_ID, NON_CS_INPUT, command_id="c1", expected_version=1)
    assert view.phase is SessionPhase.AWAITING_IDEA_REFINEMENT
    assert view.refinement.code == "unsupported_domain"
    assert model_spy.requests == []

async def test_range_clarification_can_be_resubmitted(orchestrator_factory):
    session = await orchestrator_factory(RANGE_CLARIFY_THEN_PLAN).submit_idea(PROJECT_ID, RANGE_INPUT)
    revised = await orchestrator_factory.submit_refinement(session.session_id, "限定为数据库缓存一致性")
    assert revised.phase is SessionPhase.PLANNING
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_orchestrator_idea_review_v1.py -q -p no:cacheprovider`

Expected: FAIL，forward 尚有旧停点或未初始化 task。

- [ ] **Step 3: 实现单事务状态转换**

application service 先用 `supported_domains/aliases` 判断领域；不支持时写 `unsupported_domain` refinement event，既不调用模型也不伪装专科判断。Agent run 成功后在一个 UoW transaction 写 `ConversationTurn`、Agent output、literature、session、session event 与 outbox。`proceed_to_working` 构造 `ResearchContext(normalized_idea, research_question, forward_context=...)` 并直接进入 `WORKING`；兼容 phase 只在读取旧 session 时迁移。

`TaskFactory.from_forward_context()` 是纯函数：进行中 stage 导入非空 current experiment；已有主结果 stage 创建 main review task，固定目标为“核对已有结果与补充验证需求”，让用户先在 Working 确认事实。它不调用 LLM、不根据文件名推断结果。refinement 保存具体问题供 `submit_refinement`；reject 保存原因和可执行改进方向。

- [ ] **Step 4: 运行 GREEN 与旧 orchestrator regression**

Run: `uv run pytest tests/harness/test_orchestrator_idea_review_v1.py tests/harness/test_orchestrator_working.py -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/harness tests/harness/test_orchestrator_idea_review_v1.py tests/harness/test_orchestrator_working.py
git commit -m "功能：闭合 Idea Review 四路状态转换"
```

### Task 18: 完成 plan/check/revision/confirmation loop

**Files:**
- Modify: `src/research_mentor/domain/research.py`
- Modify: `src/research_mentor/harness/orchestrator.py`
- Modify: `src/research_mentor/harness/state.py`
- Test: `tests/harness/test_orchestrator_plan_loop_v1.py`

- [ ] **Step 1: 写通过、修订和上限测试**

```python
async def test_run_plan_runs_one_agent_then_waits_for_check(orchestrator, run_spy):
    session = await orchestrator.run_plan(PROJECT_ID)
    assert session.phase is SessionPhase.CHECKING_KEY_INSIGHT
    assert run_spy.agent_names == ["plan_loop_agent"]

async def test_run_check_pass_waits_for_user_decision(orchestrator, run_spy):
    session = await orchestrator.run_check(PROJECT_ID)
    assert session.phase is SessionPhase.AWAITING_PLAN_DECISION
    assert run_spy.agent_names == ["key_insight_check_agent"]

async def test_low_dimension_does_not_veto_passing_total(orchestrator):
    session = await orchestrator.with_check(scores_for_total(6.0, evidence_support=2.4)).run_check(PROJECT_ID)
    assert session.check_rounds[-1].passed is True

async def test_failed_check_below_limit_returns_to_planning(orchestrator):
    session = await orchestrator.with_failed_check(check_round=2, max_check_rounds=5).run_check(PROJECT_ID)
    assert session.phase is SessionPhase.PLANNING and session.check_round == 3

async def test_failed_check_at_limit_enters_exhausted(orchestrator):
    session = await orchestrator.with_failed_check(check_round=4, max_check_rounds=5).run_check(PROJECT_ID)
    assert session.phase is SessionPhase.CHECK_LOOP_EXHAUSTED and session.check_round == 5

async def test_user_revision_resets_round_and_override_is_audited(orchestrator):
    revised = await orchestrator.decide_plan(PROJECT_ID, UserPlanDecision(decision="request_revision", user_reason="减少实验规模"))
    assert revised.phase is SessionPhase.PLANNING and revised.check_round == 0
    overridden = await orchestrator.decide_plan(PROJECT_ID, override_decision(reason="资源窗口即将关闭"))
    assert overridden.override_record.user_reason == "资源窗口即将关闭"

@pytest.mark.parametrize(("mode", "count"), [("low", 1), ("mid", 2), ("high", 3)])
async def test_plan_mode_creates_isolated_candidate_paths(orchestrator, mode, count):
    session = await orchestrator.run_plan(PROJECT_ID, mode=mode)
    assert len(session.plan_candidates) == count
    assert len({item.candidate_id for item in session.plan_candidates}) == count
    assert all(item.check_round == 0 for item in session.plan_candidates)

async def test_high_mode_selects_exactly_one_candidate_and_preserves_others(orchestrator):
    session = await orchestrator.with_ready_candidates(3).decide_plan(
        PROJECT_ID, UserPlanDecision(decision="accept"), candidate_id="candidate-2"
    )
    assert session.active_plan == session.plan_candidates[1].plan
    assert session.phase is SessionPhase.WORKING
    assert len(session.plan_candidates) == 3

async def test_exhausted_candidate_requires_explicit_override(orchestrator):
    session = await orchestrator.with_exhausted_candidate("candidate-1").continue_imperfect_plan(
        PROJECT_ID, "candidate-1", user_reason="资源窗口有限"
    )
    assert session.plan_candidates[0].disposition == "override"
    assert session.override_records[-1].user_reason == "资源窗口有限"
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_orchestrator_plan_loop_v1.py -q -p no:cacheprovider`

Expected: FAIL，round history/risk acknowledgement 未完整实现。

- [ ] **Step 3: 实现 Harness-owned loop**

`PlanGenerationMode` 固定为 `low/mid/high`，默认 `low`，由 Harness 映射为 1/2/3 条 `PlanCandidatePath`。每条路径保存稳定 candidate ID/index、冻结的 model profile/focus hint、独立 plan、Check history 和 round。Harness 可以并发调度不同路径，但每个 AgentRun 只调用一个现有 Agent；不得新增 Agent 类型，也不得用完全相同 request 的随机重复冒充差异。

`run_plan` 对每条 active path 分别创建 Plan Loop run，成功后该路径进入 Check；`run_check` 对指定路径创建一个 Check run，再由 Harness 计算 total。所有仍可产出候选的路径到达 pass 或 exhausted 决策点后，`mid/high` 才进入候选选择 gate；用户必须按 candidate ID 选且只能选一个。未选路径及历史继续持久化和导出。fail 且未达上限只修订该路径；达到上限后用户只能显式选择带警告 override 继续该候选，或封存本轮并返回 Idea Review。必要条件 gate 未定义，不加入判定，权威条件仍只有总分 `>= 6.0`。

`decide_plan` 处理现有 `accept/override/request_revision`：accept/override 由 TaskFactory 从 active plan 创建 main task并进入 Working；request revision 保存 feedback、重置 `check_round=0` 并回 Planning。首次 plan 和用户主动 revision 都把 `check_round=0` 传给 Plan Loop；只有 Harness 在一次失败 Check 后递增。

沿用现有 plan command 名：`RunPlanCommand` 增加默认 `mode="low"`；`RunCheckCommand` 在多路径时携带 `candidate_id`；`DecidePlanCommand` 在 `mid/high` 必须携带一个已就绪 candidate ID，在 `low` 可省略并确定性指向唯一候选。Task 20 另加入确定性的 `resume_working`，只用于驳回 completion proposal，不与 plan decision 重叠。

- [ ] **Step 4: 运行 GREEN 与 scoring eval**

Run: `uv run pytest tests/harness/test_orchestrator_plan_loop_v1.py tests/evals/test_key_insight_check_eval.py -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/harness tests/harness/test_orchestrator_plan_loop_v1.py
git commit -m "功能：完成方案检查与修订闭环"
```

### Task 19: 完成 Working → result → Complete 三路闭环

**Files:**
- Modify: `src/research_mentor/agents/working_qa/contracts.py`
- Modify: `src/research_mentor/harness/orchestrator.py`
- Modify: `src/research_mentor/harness/validation.py`
- Modify: `src/research_mentor/application/context_service.py`
- Modify: `src/research_mentor/agents/complete/contracts.py`
- Test: `tests/harness/test_orchestrator_completion_v1.py`
- Test: `tests/harness/test_working_context.py`

- [ ] **Step 1: 写结果和三路状态测试**

```python
async def test_working_plan_issue_waits_for_user_revision_decision(orchestrator):
    session = await orchestrator.send_working_message(PROJECT_ID, PLAN_ISSUE_MESSAGE)
    assert session.phase is SessionPhase.AWAITING_PLAN_REVISION_DECISION

async def test_success_requires_result_panel_confirmation(orchestrator):
    proposed = await orchestrator.send_working_message(PROJECT_ID, "差不多做完了")
    assert proposed.phase is SessionPhase.AWAITING_RESULT_RECORD
    assert proposed.current_task.status == "in_progress"
    resumed = await orchestrator.resume_working(PROJECT_ID)
    assert resumed.phase is SessionPhase.WORKING

async def test_forward_without_plan_reaches_complete(orchestrator):
    session = await orchestrator.with_forward_context(plan=None).record_main_result(PROJECT_ID, MAIN_RESULT)
    assert session.research_context.plan is None
    assert (await orchestrator.run_complete(PROJECT_ID)).phase in COMPLETE_OUTPUT_PHASES

async def test_main_result_then_explicit_run_complete(orchestrator):
    recorded = await orchestrator.record_main_result(PROJECT_ID, MAIN_RESULT)
    assert recorded.phase is SessionPhase.COMPLETING
    assert orchestrator.complete_agent.calls == 0
    completed = await orchestrator.run_complete(PROJECT_ID)
    assert completed.phase is SessionPhase.AWAITING_VALIDATION_SELECTION

async def test_invalidating_result_waits_for_revision_decision(orchestrator):
    await orchestrator.record_main_result(PROJECT_ID, main_result(execution_status="completed", impact="invalidates"))
    session = await orchestrator.run_complete(PROJECT_ID)
    assert session.phase is SessionPhase.AWAITING_PLAN_REVISION_DECISION
    assert session.latest_complete_output.revision_reason

async def test_skip_critical_validation_preserves_both_reasons(orchestrator):
    selection = ValidationSelection(skipped_candidate_ids=["critical-v1"], finish_without_more_validation=True, user_reason="没有第二块 GPU")
    session = await orchestrator.select_validations(PROJECT_ID, selection)
    skipped = session.validation_queue.skipped_by_id("critical-v1")
    assert skipped.user_reason == "没有第二块 GPU"
    assert skipped.mentor_rationale

@pytest.mark.parametrize(("execution_status", "impact"), [("completed", "supports"), ("completed", "contradicts"), ("failed", "neutral")])
async def test_validation_outcomes_return_to_completing(orchestrator, execution_status, impact):
    session = await orchestrator.record_validation_result(PROJECT_ID, validation_result(execution_status=execution_status, impact=impact))
    assert session.phase is SessionPhase.COMPLETING

async def test_existing_selected_queue_precedes_new_candidates(orchestrator):
    await orchestrator.select_validations(PROJECT_ID, ValidationSelection(selected_candidate_ids=["v2", "v1"]))
    await orchestrator.record_validation_result(PROJECT_ID, VALIDATION_V1_RESULT)
    session = await orchestrator.run_complete(PROJECT_ID, output=complete_with_candidates([NEW_V3]))
    assert session.current_task.task_id == task_id_for("v2")
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_orchestrator_completion_v1.py -q -p no:cacheprovider`

Expected: FAIL，completion modes 未完全接线。

- [ ] **Step 3: 实现结果影响和 loop**

先修正 Task 16 已被新裁决替代的行为：Working query 使用研究/阶段/任务/问题组合，低分只做 diagnostics，`decline_as_unrelated` 不再由 ranker 置 true。给 Working output 增加精确 `report_plan_issue` action；`answer/clarify/decline` 留在 Working，`success` 进入 `AWAITING_RESULT_RECORD` 但不完成 task。`resume_working` 可无模型调用返回 Working；`record_main_result`/`record_validation_result` 是用户确认点，在同一事务中完成 current task 并进入 `COMPLETING`，随后必须显式 `run_complete`。Complete input 接受 `plan=None` 的 forward ResearchContext。

新版流程图中的 `error` 作为兼容术语，不新增第五种含义重叠的 Working action：主实验中“能证明当前结论有误”映射为 `report_plan_issue`；validation 中的错误、负面结论或执行失败仍等待用户通过 `record_validation_result(execution_status, impact, failure_reason)` 明确记录，然后回 Complete。不得增加或推断 `validationResult: bool`，避免混淆“执行失败”和“完成但反对预期”。`success` 后的 `AWAITING_RESULT_RECORD` 及结果表单就是用户确认 gate；未确认时不得完成任务或调用 Complete。

Complete 的 validation mode 进入 selection gate；`ValidationSelection` 按 rank 生成队列并逐项进入 Working。每个 validation 结果记录后回 Complete；若已有 selected queue，Harness 优先继续队首并拒绝新建议中的 queued/completed duplicate，除非 Complete 输出 plan revision。plan revision mode 等待 `decide_plan_revision`：`revise` 把不可改写实验事实传给 Plan Loop并重置 round；`continue_with_warning` 保存双方理由后回 Complete；`end_project` 保留负面结果并进入 Completed。writing mode 保存 `WritingGuidance` 后完成。每个结果使用 `execution_status/impact/failure_reason` 和 evidence files，不把科学反对结论当作执行失败。

- [ ] **Step 4: 运行 GREEN 与完整 harness suite**

Run: `uv run pytest tests/harness -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/agents/working_qa/contracts.py src/research_mentor/harness tests/harness/test_orchestrator_completion_v1.py
git commit -m "功能：闭合实验结果与完成路由"
```

### Task 20: 建立 application command bus、幂等与 phase guard

**Files:**
- Create: `src/research_mentor/application/commands.py`
- Create: `src/research_mentor/application/handlers.py`
- Create: `src/research_mentor/application/command_bus.py`
- Create: `src/research_mentor/application/allowed_commands.py`
- Test: `tests/application/test_command_bus.py`
- Test: `tests/application/test_allowed_commands.py`

- [ ] **Step 1: 写 command ID、完整 union 与 phase guard 测试**

```python
async def test_same_command_id_returns_original_receipt(command_bus):
    command = SubmitIdeaCommand(project_id="p1", command_id="c1", expected_version=1, idea=INITIAL_INPUT)
    first = await command_bus.dispatch(command)
    second = await command_bus.dispatch(command)
    assert second.command_id == "c1"
    assert second.run_id == first.run_id

def test_command_union_names_are_exact():
    assert command_type_names() == {"submit_idea", "submit_refinement", "run_plan", "run_check", "decide_plan", "send_working_message", "resume_working", "record_main_result", "record_validation_result", "run_complete", "select_validations", "decide_plan_revision", "cancel_run", "restart_research", "archive_project"}

def test_result_phase_exposes_only_matching_record_command():
    assert allowed_commands(session_with_current_task("main")) == ("record_main_result", "resume_working", "cancel_run", "restart_research", "archive_project")
    assert allowed_commands(session_with_current_task("validation")) == ("record_validation_result", "resume_working", "cancel_run", "restart_research", "archive_project")

def test_restart_research_requires_explicit_confirmation():
    with pytest.raises(ValidationError):
        RestartResearchCommand(project_id="p1", command_id="c2", expected_version=2, confirm_restart=False, idea=NEW_IDEA)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/application/test_command_bus.py tests/application/test_allowed_commands.py -q -p no:cacheprovider`

Expected: FAIL，application layer 不存在。

- [ ] **Step 3: 实现 command union 与 dispatch**

```python
class CommandBase(BaseModel):
    project_id: str
    command_id: str
    expected_version: int = Field(ge=1)

Command = Annotated[
    SubmitIdeaCommand | SubmitRefinementCommand | RunPlanCommand | RunCheckCommand |
    DecidePlanCommand | SendWorkingMessageCommand | ResumeWorkingCommand | RecordMainResultCommand |
    RecordValidationResultCommand | RunCompleteCommand | SelectValidationsCommand |
    DecidePlanRevisionCommand | CancelRunCommand | RestartResearchCommand |
    ArchiveProjectCommand,
    Field(discriminator="type"),
]

# RunPlanCommand.mode: Literal["low", "mid", "high"] = "low"
# RunCheckCommand.candidate_id / DecidePlanCommand.candidate_id: str | None
# 多路径 session 由 Harness 要求 candidate_id 非空且引用当前候选；command 名称不变。

class CommandBus:
    async def dispatch(self, command: Command) -> AgentCommandReceipt | DeterministicCommandResult:
        async with self._uow_factory() as uow:
            existing = await uow.processed_commands.find(command.project_id, command.command_id)
            if existing is not None:
                return existing.result
            project = await uow.projects.get(command.project_id)
            assert_expected_version(project.version, command.expected_version)
            session = await uow.sessions.get(project.session_id)
            assert_allowed(command.type, session)
            return await self._handlers[type(command)](command, uow)
```

所有 mutation 都必须携带 `command_id` 和必填 `expected_version`。phase/version guard 在创建 run 前执行；需要 Agent 的 commands 返回 run receipt，确定性 commands 直接返回 updated view。`restart_research` 要求 `confirm_restart: Literal[True]`，封存当前 cycle 并创建同 project 下的新 session，旧 events/results/exports 仍可查。等待用户输入没有自动选择、自动失败或超时 command。

- [ ] **Step 4: 运行 GREEN 与 application regression**

Run: `uv run pytest tests/application -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/application tests/application
git commit -m "功能：建立幂等应用命令总线"
```

### Task 21: 实现 durable run worker、retry、cancel 与重启恢复

**Files:**
- Create: `src/research_mentor/application/run_worker.py`
- Create: `src/research_mentor/application/recovery.py`
- Test: `tests/application/test_run_worker.py`
- Test: `tests/application/test_recovery.py`

- [ ] **Step 1: 写 lease/retry/cancel/recovery 测试**

```python
async def test_worker_retries_transient_failure(worker, run_repo):
    run_repo.seed(run(status="queued", attempt=0))
    worker.handler.side_effect = [ModelTemporarilyUnavailable("429"), SUCCESS]
    await worker.drain_once()
    await worker.drain_once()
    assert (await run_repo.get("r1")).status == "succeeded"
    assert (await run_repo.get("r1")).attempt == 2

async def test_recovery_requeues_expired_running_lease(recovery, run_repo):
    run_repo.seed(run(status="running", lease_expires_at=PAST))
    assert await recovery.requeue_expired() == ("r1",)

async def test_running_agent_uses_frozen_input_snapshot(worker, message_repo):
    await worker.start_run("r1")
    await message_repo.append(USER_MESSAGE_ARRIVING_LATE)
    await worker.finish_run("r1")
    assert USER_MESSAGE_ARRIVING_LATE.id not in worker.model_input_message_ids("r1")

async def test_waiting_phase_is_not_failed_by_recovery(recovery, session_repo):
    session_repo.seed(session(phase=SessionPhase.AWAITING_PLAN_DECISION, updated_at=PAST))
    await recovery.requeue_expired()
    assert (await session_repo.get("s1")).phase is SessionPhase.AWAITING_PLAN_DECISION

async def test_timeout_is_terminal_and_preserves_business_phase(worker, run_repo, session_repo):
    await worker.execute(run(status="running"), handler=never_completes, timeout=0.01)
    stored = await run_repo.get("r1")
    assert stored.status == "timed_out" and stored.finished_at is not None and stored.error_code == "run_timeout"
    assert (await session_repo.get("s1")).phase is ORIGINAL_PHASE

async def test_schema_failure_allows_two_repair_requests(worker, model_spy):
    model_spy.side_effect = [ModelOutputInvalid([]), ModelOutputInvalid([]), VALID_OUTPUT]
    await worker.drain_once()
    assert len(model_spy.requests) == 3
    assert "schema_errors" in model_spy.requests[1].user_input

async def test_cancel_unlocks_only_after_worker_confirms(run_service, worker):
    await run_service.request_cancel("r1")
    assert await run_service.has_active_run("p1") is True
    await worker.confirm_cancelled("r1")
    assert await run_service.has_active_run("p1") is False

async def test_long_call_renews_lease_and_cas_completes_once(worker, competing_worker, run_repo):
    await worker.renew_lease("r1")
    assert (await run_repo.get("r1")).lease_owner == worker.worker_id
    assert await competing_worker.claim("r1") is False
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/application/test_run_worker.py tests/application/test_recovery.py -q -p no:cacheprovider`

Expected: FAIL，worker/recovery 不存在。

- [ ] **Step 3: 实现数据库 lease state machine**

```python
QUEUED -> RUNNING -> SUCCEEDED
QUEUED -> CANCELLED
RUNNING -> QUEUED      # transient error 且 attempt < retry_limit
RUNNING -> FAILED      # permanent error 或耗尽重试
RUNNING -> TIMED_OUT   # model/run timeout
RUNNING -> CANCELLED   # cooperative cancellation boundary
```

worker 用 compare-and-swap 获取配置化 lease，长 provider 调用期间按固定间隔续租，并使用 lease owner/version CAS 写 terminal result，防止过期后双执行。每次 provider 调用前后检查 cancel request；只有 worker 写入 `cancelled` 后 application 才解除 `run_in_progress`。timeout/最终失败只写 run failure event并保持原业务 phase，最终状态写 `finished_at/public_message/error_code`。

provider timeout、429 和临时网络错误按配置有限重试；Schema validation error 最多追加两次修复请求，后续请求只携带最小错误摘要。retry delay 为 `min(2 ** attempt, 30)` 秒并存储 `available_at`，不在请求线程 sleep。启动 recovery 只重排过期 lease，不重复成功 run；业务 commit 仍由 command ID 保证幂等。

- [ ] **Step 4: 运行 GREEN 与并发 worker test**

Run: `uv run pytest tests/application/test_run_worker.py tests/application/test_recovery.py -q -p no:cacheprovider`

Expected: PASS，两个 worker 竞争时同一 run 只执行一次。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/application tests/application
git commit -m "功能：实现可恢复 Agent 运行队列"
```

## Milestone E：FastAPI、SSE 与 Demo

### Task 22: 建立 composition root 与 FastAPI lifecycle

**Files:**
- Create: `src/research_mentor/api/__init__.py`
- Create: `src/research_mentor/api/app.py`
- Create: `src/research_mentor/api/dependencies.py`
- Create: `src/research_mentor/bootstrap.py`
- Test: `tests/api/test_app.py`

- [ ] **Step 1: 写 health/lifespan 测试**

```python
async def test_health_reports_provider_and_database(api_client):
    response = await api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "model_provider": "demo"}
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/api/test_app.py -q -p no:cacheprovider`

Expected: FAIL，API package 不存在。

- [ ] **Step 3: 实现 composition 与 lifespan**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    container = await build_container(app.state.settings)
    app.state.container = container
    await container.recovery.requeue_expired()
    await container.worker.start()
    yield
    await container.worker.stop()
    await container.engine.dispose()

def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Research Mentor API", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings or Settings()
    app.include_router(api_router, prefix="/api/v1")
    return app
```

`build_container` 根据同一个注入 settings 选择 demo/真实 providers；测试传入的 settings 不得被 lifespan 重新读取环境覆盖。routes 不直接 new repository/provider。

- [ ] **Step 4: 运行 GREEN**

Run: `uv run pytest tests/api/test_app.py -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/api src/research_mentor/bootstrap.py tests/api/test_app.py
git commit -m "功能：建立 FastAPI 应用组合根"
```

### Task 23: 实现 project、command、view 与错误 API

**Files:**
- Create: `src/research_mentor/api/schemas.py`
- Create: `src/research_mentor/api/projects.py`
- Create: `src/research_mentor/api/commands.py`
- Create: `src/research_mentor/api/errors.py`
- Create: `src/research_mentor/application/views.py`
- Test: `tests/api/test_projects.py`
- Test: `tests/api/test_commands.py`

- [ ] **Step 1: 写 HTTP contract tests**

```python
async def test_create_project_and_fetch_view(api_client):
    created = await api_client.post("/api/v1/projects", json={"title": "缓存研究", "domain": "computer_science"})
    assert created.status_code == 201
    assert created.json()["title"] == "缓存研究"
    view = await api_client.get(f"/api/v1/projects/{created.json()['project_id']}")
    assert view.json()["allowed_commands"] == ["submit_idea"]

async def test_stale_command_returns_409(api_client, seeded_project):
    response = await api_client.post(
        f"/api/v1/projects/{seeded_project}/commands",
        json={"type": "submit_idea", "command_id": "c1", "expected_version": 99, "idea": INITIAL_INPUT_JSON},
    )
    assert response.status_code == 409
    assert response.json()["error"] == {"code": "stale_project_version", "message": "项目已在其他操作中更新，请刷新后重试。", "retryable": False, "details": {}}

async def test_agent_and_deterministic_commands_have_distinct_responses(api_client, project_for_commands):
    queued = await api_client.post(f"/api/v1/projects/{project_for_commands}/commands", json=RUN_PLAN_JSON)
    assert queued.status_code == 202 and queued.json()["run_id"]
    decided = await api_client.post(f"/api/v1/projects/{project_for_commands}/commands", json=DECIDE_PLAN_JSON)
    assert decided.status_code == 200 and decided.json()["project_id"] == project_for_commands
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/api/test_projects.py tests/api/test_commands.py -q -p no:cacheprovider`

Expected: FAIL，routes/views 不存在。

- [ ] **Step 3: 实现稳定 endpoint contracts**

Endpoints：

```text
POST /api/v1/projects
GET  /api/v1/projects
GET  /api/v1/projects/{project_id}
POST /api/v1/projects/{project_id}/commands
```

command body 使用 Task 20 的 discriminated union，包含 `command_id/expected_version`；cancel 只通过 `cancel_run` command，不增加 run cancel endpoint。需要 Agent 的 command 返回 `202 + {command_id,run_id}`；确定性 command 返回 `200 + ProjectView`；重复 command ID 返回最初同类型结果。错误统一 `{error:{code,message,retryable,details}}`：validation=422、not found=404、illegal phase/stale version=409、provider unavailable=503；内部 traceback 不返回。ProjectView 使用 `project_id/title/domain/version/phase/allowed_commands`。

- [ ] **Step 4: 运行 GREEN 与 OpenAPI snapshot**

Run: `uv run pytest tests/api/test_projects.py tests/api/test_commands.py -q -p no:cacheprovider`

Expected: PASS，OpenAPI 包含四个 project/command endpoints、完整 command discriminator、两类成功响应和稳定 error envelope。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/api src/research_mentor/application/views.py tests/api
git commit -m "功能：提供项目与命令 API"
```

### Task 24: 实现文档上传、状态、retry/delete 与研究日志导出

**Files:**
- Create: `src/research_mentor/api/documents.py`
- Create: `src/research_mentor/api/exports.py`
- Create: `src/research_mentor/application/documents.py`
- Create: `src/research_mentor/application/journal.py`
- Test: `tests/api/test_documents.py`
- Test: `tests/application/test_journal.py`

- [ ] **Step 1: 写 upload 和 journal tests**

```python
async def test_upload_returns_document_status(api_client, project_id):
    response = await api_client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("notes.md", b"# Experiment", "text/markdown")},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "uploaded"

async def test_failed_document_can_retry_but_referenced_document_cannot_delete(api_client, failed_document, referenced_document):
    retried = await api_client.post(f"/api/v1/projects/p1/documents/{failed_document}/retry")
    assert retried.status_code == 202
    deleted = await api_client.delete(f"/api/v1/projects/p1/documents/{referenced_document}")
    assert deleted.status_code == 409 and deleted.json()["error"]["code"] == "document_in_use"

def test_journal_markdown_is_rendered_from_research_journal(renderer):
    journal = ResearchJournal(project=PROJECT, initial_input=IDEA, idea_review=REVIEW, literature=[LITERATURE], plans=[PLAN_OUTPUT], checks=[CHECK_OUTPUT], plan_decisions=[PLAN_DECISION], override_records=[], experiment_tasks=[MAIN_TASK], main_result=MAIN_RESULT, validation_results=[VALIDATION_RESULT], complete_outputs=[COMPLETE_OUTPUT], writing_guidance=WRITING_GUIDANCE, generated_at=NOW)
    text = renderer.to_markdown(journal)
    assert "## 实验结果" in text
    assert "OpenAlex" in text
    assert "EvidenceRef" not in text
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/api/test_documents.py tests/application/test_journal.py -q -p no:cacheprovider`

Expected: FAIL，routes/service/renderer 不存在。

- [ ] **Step 3: 实现限制、异步 parse job 与 exports**

允许 MIME/扩展名、单文件大小和项目总大小全部读取 typed Settings；stream 写入并计算 sha256，任一 quota 超限立即移除 incomplete blob。上传后创建独立 `DocumentParseJob`，不得伪装成要求 `AgentName` 的 `AgentRun`；状态按 uploaded → parsing → ready/failed。失败保留原文件，retry 创建新 parse attempt；DELETE 只允许没有被 evidence/result 引用的 document。Endpoints：

```text
POST   /api/v1/projects/{project_id}/documents
GET    /api/v1/projects/{project_id}/documents
GET    /api/v1/projects/{project_id}/documents/{document_id}
POST   /api/v1/projects/{project_id}/documents/{document_id}/retry
DELETE /api/v1/projects/{project_id}/documents/{document_id}
GET    /api/v1/projects/{project_id}/journal.json
GET    /api/v1/projects/{project_id}/journal.md
```

`ExportService` 从 repositories 构造规范 `ResearchJournal(project, initial_input, idea_review, literature, plans, checks, plan_decisions, override_records, experiment_tasks, main_result, validation_results, complete_outputs, writing_guidance, generated_at)`；JSON 是该 model 的权威序列化，Markdown 只从该 model 确定性渲染，不能解析聊天正文猜字段。Markdown 按 idea、证据、plan/check 争论、tasks/results、validation、WritingGuidance 排列。

- [ ] **Step 4: 运行 GREEN 与 file security suite**

Run: `uv run pytest tests/api/test_documents.py tests/application/test_journal.py tests/adapters/documents -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/api src/research_mentor/application tests/api/test_documents.py tests/application/test_journal.py
git commit -m "功能：提供文档处理与研究日志导出"
```

### Task 25: 实现 public event SSE 与 Last-Event-ID 恢复

**Files:**
- Create: `src/research_mentor/api/events.py`
- Create: `src/research_mentor/application/event_stream.py`
- Test: `tests/api/test_events.py`

- [ ] **Step 1: 写 reconnect/heartbeat test**

```python
async def test_sse_resumes_after_last_event_id(api_client, seeded_events):
    response = await api_client.get(
        "/api/v1/projects/p1/events",
        headers={"Last-Event-ID": "2"},
    )
    body = response.text
    assert "id: 3" in body
    assert "id: 1" not in body

async def test_event_payload_never_contains_prompt_or_secret(api_client, seeded_events):
    body = (await api_client.get("/api/v1/projects/p1/events?after=1")).text
    assert "system_prompt" not in body
    assert "api_key" not in body

async def test_after_replay_has_strictly_increasing_unique_sequence(api_client, seeded_events):
    body = (await api_client.get("/api/v1/projects/p1/events?after=1")).text
    assert parse_sse_ids(body) == [2, 3]

def test_public_event_types_are_whitelisted():
    assert PUBLIC_EVENT_TYPES == {"command.accepted", "run.started", "run.completed", "run.failed", "retrieval.started", "retrieval.results", "retrieval.unavailable", "document.parsing_progress", "agent.stage", "session.phase_changed", "evidence.added", "user_input.required", "export.ready"}
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/api/test_events.py -q -p no:cacheprovider`

Expected: FAIL，event stream 不存在。

- [ ] **Step 3: 实现 persisted replay + live polling**

格式固定：

```text
id: {sequence}
event: {type}
data: {compact JSON public payload}

```

endpoint 是 `GET /api/v1/projects/{project_id}/events`。把 header `Last-Event-ID` 与 query `after` 解析为 sequence cursor（两者同时出现取较大值），先查询 `sequence > cursor` 的持久事件，再每 1 秒轮询新事件；每个 project 的 sequence 严格递增。15 秒无 event 发送 comment heartbeat，但 heartbeat 不入 event/outbox 表。

只允许：command accepted、run started/completed/failed、retrieval started/result count/unavailable、document parsing progress、Agent stage/status、session phase changed、evidence added、user input required、export ready。cancelled/timed_out 作为 run event payload 的公开 status，不另建敏感 event 类别；不公开原始消息、Prompt、chain-of-thought、provider payload、secret 或未筛选文件内容。

- [ ] **Step 4: 运行 GREEN**

Run: `uv run pytest tests/api/test_events.py -q -p no:cacheprovider`

Expected: PASS，断线重连无漏项；客户端按 sequence 去重后不会重复渲染。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/api/events.py src/research_mentor/application/event_stream.py tests/api/test_events.py
git commit -m "功能：提供可恢复 SSE 事件流"
```

### Task 26: 建立 deterministic demo mode 与三阶段样例

**Files:**
- Create: `src/research_mentor/application/demo.py`
- Create: `src/research_mentor/adapters/demo/model.py`
- Create: `src/research_mentor/adapters/demo/retrieval.py`
- Test: `tests/application/test_demo.py`

- [ ] **Step 1: 写 deterministic seed tests**

```python
async def test_demo_seed_creates_three_named_projects(demo_service):
    projects = await demo_service.ensure_seeded()
    assert [p.demo_stage for p in projects] == ["submitted_idea", "working", "validation_selection"]
    assert [p.phase for p in projects] == [SessionPhase.PLANNING, SessionPhase.WORKING, SessionPhase.AWAITING_VALIDATION_SELECTION]

async def test_demo_seed_is_idempotent(demo_service):
    first = await demo_service.ensure_seeded()
    second = await demo_service.ensure_seeded()
    assert [p.project_id for p in first] == [p.project_id for p in second]

async def test_demo_fixtures_share_real_schema_and_support_panels_and_export(demo_service):
    project = (await demo_service.ensure_seeded())[2]
    assert CompleteAgentOutput.model_validate(project.latest_complete_output)
    assert project.visible_evidence
    assert project.validation_candidates
    assert (await demo_service.export(project.project_id, "json")).writing_guidance

def test_demo_event_delays_are_deterministic(demo_event_script):
    assert [item.delay_ms for item in demo_event_script] == [0, 120, 240, 360]
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/application/test_demo.py -q -p no:cacheprovider`

Expected: FAIL，demo service/adapters 不存在。

- [ ] **Step 3: 实现固定 fixture 脚本**

三个项目分别实际停在：已提交 idea 后的 `PLANNING`、`WORKING`、`AWAITING_VALIDATION_SELECTION`。`DemoModelAdapter.generate(ModelRequest)` 按 command/phase 返回通过同一生产 Pydantic Schema 的固定输出；demo retrieval 返回 `provider="demo"` 且明确 `demo://` provenance。固定 event script 提供可复现延迟，三个 project 都可展示 phase panel、右栏 evidence 与 journal export。ProjectView 包含 `is_demo=true`，页面持续显示 `DEMO DATA`；real mode 复用同一 API/frontend contract。

- [ ] **Step 4: 运行 GREEN 与 bootstrap test**

Run: `uv run pytest tests/application/test_demo.py tests/api/test_app.py -q -p no:cacheprovider`

Expected: PASS，重复启动不重复 seed。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/application/demo.py src/research_mentor/adapters/demo tests/application/test_demo.py
git commit -m "功能：加入可复现完整流程 Demo"
```

## Milestone F：React 前端展示

### Task 27: 建立 React/Vite/TypeScript 前端与 typed API client

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/events.ts`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/global.css`
- Test: `frontend/src/api/client.test.ts`

- [x] **Step 1: 初始化依赖并写 `/api/v1` command body RED test**

Run:

```powershell
Set-Location frontend
npm init -y
npm install react@19 react-dom@19
npm install -D typescript vite @vitejs/plugin-react vitest jsdom @testing-library/react @testing-library/jest-dom @types/react @types/react-dom
```

Test：

```typescript
it("sends command_id and current expected_version in the body", async () => {
  const fetcher = vi.fn().mockResolvedValue(okJson({ command_id: "c1", run_id: "r1" }));
  await createClient(fetcher).dispatchCommand("p1", { type: "submit_idea", command_id: "c1", expected_version: 3, idea: INITIAL_INPUT });
  expect(fetcher.mock.calls[0][0]).toBe("/api/v1/projects/p1/commands");
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toMatchObject({ command_id: "c1", expected_version: 3 });
});
```

- [x] **Step 2: 运行 RED**

Run: `npm test -- --run src/api/client.test.ts`

Expected: FAIL，client 不存在。

- [x] **Step 3: 实现最小 shell、types 和 client**

```typescript
export type Phase =
  | "awaiting_idea" | "awaiting_idea_refinement" | "planning"
  | "checking_key_insight" | "awaiting_plan_decision"
  | "awaiting_working_context" | "working" | "awaiting_result_record"
  | "completing" | "awaiting_validation_selection"
  | "awaiting_plan_revision_decision" | "completed" | "rejected"
  | "check_loop_exhausted";

export interface ProjectView {
  project_id: string;
  title: string;
  domain: string;
  version: number;
  phase: Phase;
  allowed_commands: CommandType[];
  is_demo: boolean;
  active_run: AgentRunView | null;
  last_event_sequence: number;
}
```

API client 固定 base `/api/v1`，command 接受 Task 20 的 discriminated union，不通过 header 建第二套 identity。非 2xx 解析为含 `code/message/retryable/details` 的 `ApiError`；SSE client 保存最后 sequence，以 `?after={sequence}` 重连并刷新一次 ProjectView。

同步实现 frontend 基础安全与恢复 primitives：外部链接统一使用 `noopener/noreferrer` 安全打开；Markdown 必须先清理再渲染；本地 draft storage 按 `project_id + phase` 隔离。前端不保存 API Key，不在浏览器重算评分、路由或 Harness 规则。Idea 输入显示 `0/19999` 计数并在超限时于发请求前阻止提交；后端 `InitialInput` 的 19999 字上限仍是最终权威。

- [x] **Step 4: 运行 GREEN/build**

Run: `npm test -- --run && npm run build`

Expected: PASS，`frontend/dist` 生成。

- [x] **Step 5: Commit**

```powershell
git add frontend
git commit -m "功能：建立 React 前端与类型化 API client"
```

### Task 28: 实现项目工作台、阶段视图、证据面板与导师 microcopy

**Files:**
- Create: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/components/ProjectSidebar.tsx`
- Create: `frontend/src/components/PhaseTimeline.tsx`
- Create: `frontend/src/components/RunStatus.tsx`
- Create: `frontend/src/components/EvidencePanel.tsx`
- Create: `frontend/src/components/DocumentPanel.tsx`
- Create: `frontend/src/components/IdeaReviewCard.tsx`
- Create: `frontend/src/components/ResearchPlanView.tsx`
- Create: `frontend/src/components/KeyInsightScoreCard.tsx`
- Create: `frontend/src/components/PlanDecisionPanel.tsx`
- Create: `frontend/src/components/ExperimentRecordForm.tsx`
- Create: `frontend/src/components/ValidationSelectionPanel.tsx`
- Create: `frontend/src/components/WritingGuidanceView.tsx`
- Create: `frontend/src/components/CollapsibleRunTrace.tsx`
- Create: `frontend/src/components/ExportPanel.tsx`
- Create: `frontend/src/ui/mentorMicrocopy.ts`
- Create: `frontend/src/features/idea/IdeaView.tsx`
- Create: `frontend/src/features/plan/PlanView.tsx`
- Create: `frontend/src/features/working/WorkingView.tsx`
- Create: `frontend/src/features/completion/CompletionView.tsx`
- Create: `frontend/src/features/project/ProjectWorkspace.tsx`
- Test: `frontend/src/features/project/ProjectWorkspace.test.tsx`
- Test: `frontend/src/ui/mentorMicrocopy.test.ts`

- [x] **Step 1: 写 phase/command/a11y 和 microcopy tests**

```typescript
it.each([
  ["awaiting_idea", "submit_idea", "提交研究想法"],
  ["awaiting_plan_decision", "decide_plan", "确认方案"],
  ["awaiting_result_record", "record_main_result", "记录主实验结果"],
  ["awaiting_validation_selection", "select_validations", "选择验证任务"],
])("renders server-allowed %s primary action", (phase, command, label) => {
  render(<ProjectWorkspace project={project({ phase, allowed_commands: [command] })} />);
  expect(screen.getByRole("button", { name: label })).toBeEnabled();
});

it("does not infer an action from phase when server does not allow it", () => {
  render(<ProjectWorkspace project={project({ phase: "awaiting_plan_decision", allowed_commands: [] })} />);
  expect(screen.queryByRole("button", { name: "确认方案" })).not.toBeInTheDocument();
});

it("marks demo content visibly", () => {
  render(<ProjectWorkspace project={project({ is_demo: true })} />);
  expect(screen.getByText("DEMO DATA")).toBeVisible();
});
```

`frontend/src/ui/mentorMicrocopy.test.ts`：

```typescript
import { describe, expect, it } from "vitest";

import { MENTOR_MICROCOPY } from "./mentorMicrocopy";

describe("MENTOR_MICROCOPY", () => {
  it("keeps mentor microcopy limited to non-substantive UI states", () => {
    expect(MENTOR_MICROCOPY).toEqual({
      inputTooLong: "这么多内容我可不会假装一眼看完。请拆分或上传文件。",
      validationRequired: "至少先决定这一轮做什么。空着可不算选择。",
      runCheckingEvidence: "正在核对证据，先别急着催。",
    });
    expect(MENTOR_MICROCOPY).not.toHaveProperty("reviewDecision");
    expect(MENTOR_MICROCOPY).not.toHaveProperty("riskExplanation");
  });
});
```

- [x] **Step 2: 运行 RED**

Run: `npm test -- --run src/features/project/ProjectWorkspace.test.tsx src/ui/mentorMicrocopy.test.ts`

Expected: FAIL，workspace components 和 `MENTOR_MICROCOPY` 不存在。

- [x] **Step 3: 实现 responsive research workspace**

Desktop 三栏：project/nav 240px、main minmax(0,1fr)、evidence 360px；窄屏左栏变 drawer、右栏变 evidence sheet，中栏始终是主内容，不改成 tabs 替代。主视图按精确 `Phase` exhaustive switch 渲染 typed cards；按钮只从 server `allowed_commands` 产生。证据卡显示 source/support/provenance/安全外链；Check 卡明确区分模型五维分数与 Harness final score；run trace 只呈现公开 events。全局中文 UI，技术标识保留英文。

证据栏必须区分“检索到”与“本轮实际采用”，采用状态随当前 view/event 更新，不能永久绑定首次检索结果；默认列表设可见数量上限与内部滚动，详情视图可查看受限总量，并按 adopted/discarded 筛选。结构化方案、评分、validation 和 writing guidance 必须在后端校验/提交完成后整块渲染，禁止流式拼接 JSON。仅短状态文案和已校验自然语言可使用 typewriter；panel、选择项和表单不得使用。dialog/panel 打开时锁定背景滚动，toast 与状态提示不得遮挡确认按钮，composer 与 panel 不能同时可编辑。

首次使用与空状态要明确产品边界：这是管理科研判断和推进的导师工作台，帮助聚焦选题、审查方案、处理研究过程问题、记录结果和组织验证；不替用户写代码或论文正文，不承诺解决所有科研问题；与当前研究无关的细碎问题引导至通用 Agent/搜索。竞品说明只能表述工作流差异，不得声称基础模型能力优于 ChatGPT、Claude、Deep Research、ResearchAgent、AI Scientist、Co-Scientist、Google Scholar 或 Semantic Scholar。

视觉 token：

```css
:root {
  --ink: #16221d; --paper: #f4f1e8; --panel: #fffdf7;
  --mentor-accent: #b45f24; --line: #cfc8b8;
  --font-ui: "IBM Plex Sans", "Noto Sans SC", sans-serif;
  --font-reading: "Noto Serif SC", serif;
}
```

暖橙是唯一强调色；phase/score/error 同时使用文字、图标和边框形态，不增加第二强调色。dialog/sheet 具有 heading/description，citation hover 同时支持 focus/click，所有动画和 typewriter 在 `prefers-reduced-motion` 下关闭。

在 `frontend/src/ui/mentorMicrocopy.ts` 中只导出确定性的非实质状态文案：

```typescript
export const MENTOR_MICROCOPY = {
  inputTooLong: "这么多内容我可不会假装一眼看完。请拆分或上传文件。",
  validationRequired: "至少先决定这一轮做什么。空着可不算选择。",
  runCheckingEvidence: "正在核对证据，先别急着催。",
} as const;
```

组件只能在超长输入、遗漏确定性选择和等待状态中按固定 key 使用这些文案。科研评价、Agent action、评分、证据、拒绝理由和风险说明必须直接呈现 server view 中的实质内容，不得经过 microcopy 层改写。v1 不建立独立语气 Agent。

- [x] **Step 4: 运行 GREEN/build 与 keyboard check**

Run: `npm test -- --run && npm run build`

Expected: PASS；所有 form 有 label，焦点可见，dialog 可 Esc 关闭，颜色不作为唯一状态提示；microcopy 只覆盖已声明的非实质状态，不处理 server 返回的科研内容。

- [x] **Step 5: Commit**

```powershell
git add frontend/src
git commit -m "功能：实现科研导师项目工作台"
```

### Task 29: 接通上传、SSE、命令反馈与完整用户操作

**Files:**
- Create: `frontend/src/hooks/useProject.ts`
- Create: `frontend/src/hooks/useProjectEvents.ts`
- Create: `frontend/src/hooks/useCommand.ts`
- Modify: `frontend/src/features/project/ProjectWorkspace.tsx`
- Test: `frontend/src/hooks/useProjectEvents.test.tsx`
- Test: `frontend/src/features/project/ProjectActions.test.tsx`

- [ ] **Step 1: 写 SSE refresh 和 double-submit tests**

```typescript
it("refreshes view after phase.changed", async () => {
  const api = fakeApi();
  renderHook(() => useProjectEvents("p1", api));
  fakeEvents.emit({ id: "4", type: "phase.changed", data: { phase: "working" } });
  await waitFor(() => expect(api.getProject).toHaveBeenCalledWith("p1"));
});

it("drops replayed sequences and reconnects with after", async () => {
  const api = fakeApi();
  renderHook(() => useProjectEvents(project({ last_event_sequence: 4 }), api));
  fakeEvents.emit({ id: "4", type: "session.phase_changed", data: {} });
  fakeEvents.emit({ id: "5", type: "session.phase_changed", data: { phase: "working" } });
  await waitFor(() => expect(api.applyEvent).toHaveBeenCalledTimes(1));
  expect(fakeEvents.lastUrl).toContain("/api/v1/projects/p1/events?after=5");
});

it("locks ordinary mutations for the full active run", async () => {
  render(<ProjectWorkspace project={project({ active_run: runningRun(), allowed_commands: ["cancel_run"] })} />);
  expect(screen.getByRole("textbox", { name: "研究消息" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "取消运行" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "提交研究想法" })).not.toBeInTheDocument();
});

it("submits validation candidate IDs in rank-independent UI order", async () => {
  const api = fakeApi();
  render(<ValidationSelectionPanel candidates={CANDIDATES_REORDERED_FOR_DISPLAY} api={api} />);
  await user.click(screen.getByLabelText("鲁棒性验证"));
  await user.click(screen.getByRole("button", { name: "确认选择" }));
  expect(api.dispatchCommand).toHaveBeenCalledWith(expect.objectContaining({ type: "select_validations", selection: { selected_candidate_ids: ["candidate-v2"], skipped_candidate_ids: [], finish_without_more_validation: false, user_reason: null } }));
});
```

- [ ] **Step 2: 运行 RED**

Run: `npm test -- --run src/hooks/useProjectEvents.test.tsx src/features/project/ProjectActions.test.tsx`

Expected: FAIL，hooks/connected actions 不存在。

- [ ] **Step 3: 实现 connected UI**

`useCommand` 在一次用户动作开始时生成 UUID `command_id`，读取当前 ProjectView `version` 作为 `expected_version`，同一 pending/retry action 复用 command ID；新业务意图生成新 ID。receipt 后保持 `active_run` lock，直到 SSE/project refresh 显示 terminal run；run 期间禁用 composer 和全部普通 mutations，只保留本地 draft 与显式 `cancel_run`。

`useProjectEvents` 以 sequence 严格去重，只应用 `sequence > lastApplied`，断线按 1/2/4/8/15 秒退避并用 `after` 重连，恢复后刷新 view。validation 提交 candidate ID；上传显示 transfer 与 parse status；刷新/断线/stale version 后从 server view 恢复已提交内容，同时按 project/phase 恢复未提交 draft。运行、检索和版本冲突错误显示稳定 code/retryability 与明确 retry 入口，不展示 stack trace，retry 不清除 draft。证据 adopted/discarded filter 只过滤 server 提供的状态，不由 UI 猜测引用关系。

- [ ] **Step 4: 运行 GREEN/build**

Run: `npm test -- --run && npm run build`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add frontend/src
git commit -m "功能：接通前端命令上传与实时事件"
```

## Milestone G：Evals、E2E、文档与发布审计

### Task 30: 扩充五 Agent eval datasets 与 runner

**Files:**
- Create: `evals/idea_review_cases.json`
- Create: `evals/plan_loop_cases.json`
- Modify: `evals/key_insight_check_cases.json`
- Create: `evals/working_qa_cases.json`
- Create: `evals/complete_cases.json`
- Create: `evals/retrieval_relevance_cases.json`
- Create: `evals/citation_cases.json`
- Create: `evals/demo_workflow_cases.json`
- Create: `src/research_mentor/evals/runner.py`
- Create: `tests/evals/test_agent_evals.py`
- Modify: `evals/README.md`

- [ ] **Step 1: 写 dataset schema 与 threshold test**

```python
@pytest.mark.parametrize("dataset", sorted(Path("evals").glob("*_cases.json")))
def test_eval_dataset_is_versioned_and_has_metadata(dataset):
    suite = EvalSuite.model_validate_json(dataset.read_text(encoding="utf-8"))
    assert suite.version == "1.0"
    assert suite.prompt_version and suite.domain == "computer_science"

def test_idea_review_has_at_least_twenty_labeled_cases():
    suite = load_suite("evals/idea_review_cases.json")
    assert len(suite.cases) >= 20
    assert {case.expected_idea_type for case in suite.cases} == {"opinion", "range", "forward"}

def test_retrieval_threshold_is_calibrated_at_point_three():
    report = evaluate_retrieval(load_suite("evals/retrieval_relevance_cases.json"), threshold=0.3)
    assert report.threshold == 0.3 and report.labeled_case_count >= 20

def test_demo_model_passes_required_eval_thresholds():
    report = run_all_evals(build_demo_agents())
    assert report.contract_pass_rate == 1.0
    assert report.behavior_pass_rate >= 0.90
    assert report.metadata.prompt_versions
    assert report.metadata.model_profiles
    assert report.metadata.repetitions >= 1
    assert report.metadata.run_at.tzinfo is not None
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/evals/test_agent_evals.py -q -p no:cacheprovider`

Expected: FAIL，四个 datasets/runner 不存在。

- [ ] **Step 3: 写固定 cases 与 deterministic evaluator**

Idea Review 至少 20 条 CS 标注，覆盖 opinion/range/forward、reject/refinement、四种 forward stage、证据不足、prompt injection 与用户错误自称 type。其余四 Agent 各覆盖正常、边界、事实冲突和 injection；Plan 用专家 rubric；Check 重复采样评五维稳定性与 total-only 5.9/6.0 boundary；Complete 评 validation relevance/duplicate、plan revision 和 WritingGuidance。

Plan eval 还必须覆盖 low/mid/high 的 1/2/3 路径数、candidate ID 唯一性、跨路径状态隔离、差异 profile 可追溯、单选 gate 和 exhausted override；Working eval 覆盖 success 未确认不推进、主实验 plan issue 与 validation `completed+contradicts`/`failed+neutral` 的不同路由。Prompt isolation eval 断言动态 payload 不重复 `sys_input`。必要条件 gate 不进入 dataset 或通过条件。

retrieval suite 提供人工 relevance label，用于校准 0.3；citation suite 计算可解析率和 DOI/URL/provider-ID duplicate rate；demo workflow suite 计算完整流程 success rate。`EvalReport.metadata` 必含 Prompt version、model profile、重复采样次数和带 timezone 时间。runner 只评 schema/routing/rubric/稳定指标，不用另一个 LLM 当发布 gate；无真实 provider 时仅报告 deterministic 指标并明确 `provider_mode="demo"`，不伪造真实模型表现。

- [ ] **Step 4: 运行 GREEN 与全量 Python suite**

Run: `uv run pytest -q -p no:cacheprovider`

Expected: PASS，eval thresholds 达标。

- [ ] **Step 5: Commit**

```powershell
git add evals src/research_mentor/evals tests/evals
git commit -m "测试：扩充五 Agent 行为评估集"
```

### Task 31: 建立 Playwright E2E 与 34 项验收覆盖

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/demo-flow.spec.ts`
- Create: `frontend/tests/e2e/forward-stages.spec.ts`
- Create: `frontend/tests/e2e/validation-loop.spec.ts`
- Create: `frontend/tests/e2e/recovery.spec.ts`
- Create: `frontend/tests/e2e/documents.spec.ts`
- Create: `frontend/tests/e2e/accessibility.spec.ts`
- Create: `frontend/tests/e2e/visual.spec.ts`
- Create: `frontend/tests/e2e/security.spec.ts`
- Create: `frontend/tests/e2e/visual.spec.ts-snapshots/workspace-desktop-chromium-win32.png`
- Create: `frontend/tests/e2e/visual.spec.ts-snapshots/workspace-mobile-chromium-win32.png`
- Create: `tests/integration/test_acceptance_matrix.py`
- Create: `tests/integration/test_forward_stages.py`
- Create: `tests/integration/test_validation_workflow.py`
- Modify: `tests/test_architecture_boundaries.py`

- [ ] **Step 1: 安装并写第一个 failing journey**

Run:

```powershell
Set-Location frontend
npm install -D @playwright/test @axe-core/playwright
npx playwright install chromium
```

```typescript
test("demo idea reaches working after plan confirmation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /Idea 阶段/ }).click();
  await page.getByRole("button", { name: "提交研究想法" }).click();
  await expect(page.getByText("方案检查")).toBeVisible();
  await page.getByRole("button", { name: "确认方案" }).click();
  await expect(page.getByRole("heading", { name: "实验进行中" })).toBeVisible();
});

test("desktop and narrow layouts match reviewed snapshots", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?project=demo-working");
  await expect(page).toHaveScreenshot("workspace-desktop.png", { animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page).toHaveScreenshot("workspace-mobile.png", { animations: "disabled" });
});
```

- [ ] **Step 2: 运行 RED**

Run: `npm run e2e -- --project=chromium`

Expected: FAIL，Playwright config/完整连接尚未验证。

- [ ] **Step 3: 实现四组 E2E**

实现真实 tests，而不是只登记 node ID：

- `demo-flow`：opinion 全路径、range refinement、reject、Plan/Check user decisions、WritingGuidance；
- `forward-stages`：四个 ForwardStage 都跳过 Plan Loop，进行中导入 task，已有结果先进入 fact-review Working；
- `validation-loop`：candidate rank 入队、多选逐一执行、completed+contradicts 与 execution failed 分离、invalidates revision decision、critical skip 双方理由、selected queue 优先且无 duplicate；
- `recovery`：database restart、重复 command ID、CAS 单赢家、SSE header/query reconnect 和 sequence 去重、run snapshot/cancel/timeout、等待 phase、restart research；
- `documents`：supported parse/chunk/evidence、失败/retry/delete guard、JSON/Markdown journal；
- `accessibility`：project list 与所有交互 phase 的 axe、keyboard、focus、drawer/sheet、`prefers-reduced-motion`；
- `security`：real adapter request、log/event/export sanitization、frontend bundle 不含 secret、非 CS 不调用 model；
- `visual`：1440×1000 三栏与 390×844 drawer/sheet screenshot，固定 demo data、字体与 animations disabled；
- Python integration：四个 forward stage、result/validation boundary、OpenAlex empty/unavailable、rank 0.3 boundary、worker recovery；architecture test 禁止 Agent 导入其他 Agent、repository/provider 或直接修改 Harness 状态。

`test_acceptance_matrix.py` 对规格 1..34 各绑定至少一个实际 pytest/Playwright test，并读取 pytest/Playwright JUnit reports 验证节点本次确实 PASS；缺号、节点不存在、未执行或失败均使 gate 失败。新增场景 31–34 分别覆盖 plan mode 候选隔离与单选、exhausted override/未定义 gate、Working success/error 兼容路由、Context Assembler payload 隔离。

- [ ] **Step 4: 运行 GREEN**

Run:

```powershell
uv run pytest tests/integration/test_acceptance_matrix.py -q -p no:cacheprovider
Set-Location frontend
npm test -- --run
npm run build
npm run e2e -- --project=chromium
```

Expected: 全部 PASS；30 个 acceptance 场景都有本次执行 evidence，两个 visual snapshots 无非预期差异，bundle/architecture boundary 检查通过。

- [ ] **Step 5: Commit**

```powershell
git add frontend tests/integration/test_acceptance_matrix.py
git commit -m "测试：覆盖 v1 完整流程与前端验收"
```

### Task 32: 更新 README、开发命令与最终发布审计

**Files:**
- Modify: `README.md`
- Create: `.env.example`
- Create: `scripts/dev.ps1`
- Create: `scripts/check.ps1`
- Modify: `.gitignore`
- Test: `tests/test_documentation.py`

- [ ] **Step 1: 写文档命令有效性测试**

```python
def test_readme_documents_required_start_commands():
    readme = Path("README.md").read_text(encoding="utf-8")
    for command in ("uv sync --all-groups", "alembic upgrade head", "uvicorn research_mentor.api.app:create_app", "npm run dev"):
        assert command in readme

def test_env_example_has_no_secret_values():
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "RESEARCH_MENTOR_MODEL_API_KEY=" in text
    assert "sk-" not in text
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/test_documentation.py -q -p no:cacheprovider`

Expected: FAIL，README 尚为 v0.1 且脚本不存在。

- [ ] **Step 3: 完成操作文档与 scripts**

README 必须包含：产品截图位置、五 Agent 架构、low/mid/high 候选模式与默认 low、demo quickstart、真实 OpenAI/OpenAI-compatible 配置、OpenAlex mailto、Anydoc/FlagEmbedding 可选安装、SQLite/PostgreSQL、文件限制、API/SSE contract、测试矩阵、已知 v1 scope，以及“不替写代码/论文正文、不解决无关细碎问题”的产品边界。`scripts/dev.ps1` 启动 API worker 和 Vite；`scripts/check.ps1` 顺序执行 migration smoke、Python tests、frontend tests/build、Playwright。

`.gitignore` 加入 `.env`、`data/`、SQLite 文件、frontend node_modules/dist、Playwright artifacts，不忽略 migrations、lockfiles 或 evals。

- [ ] **Step 4: 运行最终验证**

Run:

```powershell
uv lock --check
uv run alembic upgrade head
uv run pytest -q -p no:cacheprovider
Set-Location frontend
npm ci
npm test -- --run
npm run build
npm run e2e -- --project=chromium
Set-Location ..
git diff --check
git status --short
```

Expected: 所有命令 exit 0；仅预期文件有改动；无真实 secret、database、upload 或 test artifact 被跟踪。

- [ ] **Step 5: Commit**

```powershell
git add README.md .env.example .gitignore scripts tests/test_documentation.py
git commit -m "文档：完成 v1 启动与验收指南"
```

## 2. 规格验收场景映射

| 规格第 16 节场景 | 主要任务 | 自动验证 |
|---:|---:|---|
| 1 opinion 完整路径 | 15, 17, 18 | idea/plan orchestrator + E2E |
| 2 range refinement | 3, 17 | `test_range_clarification_can_be_resubmitted` |
| 3 不可行 Idea reject | 3, 17 | review 四路测试 |
| 4 forward 进入 Working | 3, 17 | `test_forward_initializes_working_context_and_task` |
| 5 forward completed → Complete | 17, 19 | completion orchestrator E2E |
| 6 低单项但总分 6.0 通过 | 5, 18 | `test_low_dimension_does_not_veto_passing_total` |
| 7 revision reset/override audit | 18, 20 | plan loop/audit tests |
| 8 低分仍进入上下文判断 | 16, 19, 30 | working relevance/calibration tests |
| 9 rank unavailable 不伪装 | 16 | `test_rank_unavailable_does_not_decline_question` |
| 10 supported file 可引用 | 10, 12, 24 | document adapter/API/E2E |
| 11 parse 失败隔离 | 10, 24 | parser/API failure tests |
| 12 有序 validation candidates | 4, 6, 19 | validation queue tests |
| 13 多选按 rank 进入 Working | 6, 19 | validation selection tests |
| 14 validation 三种 outcome | 19 | `test_validation_outcome_returns_to_complete` |
| 15 invalidates 进入 revision decision | 4, 19 | completion revision tests |
| 16 跳过 critical 保留双方理由 | 19, 20 | `test_skip_critical_validation_preserves_both_reasons` |
| 17 WritingGuidance | 4, 19 | writing completion tests |
| 18 JSON/Markdown journal | 24 | journal/API tests |
| 19 restart 后恢复 | 8, 9, 21 | migration/recovery tests |
| 20 command 幂等 | 20 | command bus/API tests |
| 21 stale mutation 单赢家 | 9, 23 | concurrency/API tests |
| 22 SSE 重连不漏/不重复渲染 | 25, 29 | SSE + frontend hook tests |
| 23 无 key demo 全流程 | 22, 26, 31 | demo bootstrap/E2E |
| 24 real structured adapter/secret | 14, 25 | LLM adapter/event tests |
| 25 responsive/keyboard/reduced-motion | 28, 31 | component/axe/keyboard E2E |
| 26 新消息不进入运行中 snapshot | 21 | `test_running_agent_uses_frozen_input_snapshot` |
| 27 等待用户不自动选择/失败 | 20, 21 | phase guard/recovery tests |
| 28 restart research 封存旧 cycle | 20, 24 | command/journal tests |
| 29 非 CS 明确 unsupported | 17 | `test_non_cs_domain_is_rejected_before_specialist_pipeline` |
| 30 全测试/build/boundary | 30–32 | final check script |

## 3. Milestone gates

1. **A gate:** 原有 core tests + 新 contract/harness tests 全绿；不引入外部 I/O。
2. **B gate:** SQLite migration、UoW、文档与 retrieval adapter tests 全绿；真实网络被 mock。
3. **C gate:** 五 Agent 全部 async structured model；demo 与 provider adapter contract tests 全绿。
4. **D gate:** 从 idea 到 writing/validation/revision 的 application-level journeys 全绿。
5. **E gate:** API、SSE、restart/idempotency tests 全绿，demo 可从空数据库 seed。
6. **F gate:** React unit/build 全绿，可在桌面和窄屏完成主要命令。
7. **G gate:** 34 项 acceptance mapping、eval、Playwright、accessibility 与 README quickstart 全部通过。

只有当前 gate 全绿才能进入下一 milestone；provider credential 缺失不应阻止 demo gate，但真实 provider smoke test 必须在有凭据的发布环境单独执行并记录 request id，不能写入仓库。
