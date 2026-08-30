# 傲娇导师 v1.0 完整产品 Implementation Plan

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
- v1.0 完成条件：设计规格第 17 节 30 项场景全部自动化或人工可复验，Python/unit、frontend/unit、Playwright/E2E 全绿，README 可从空数据库启动。

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

### Task 2: 增加项目、对话、文档与 Job 领域模型

**Files:**
- Create: `src/research_mentor/domain/projects.py`
- Create: `src/research_mentor/domain/documents.py`
- Create: `src/research_mentor/domain/jobs.py`
- Modify: `src/research_mentor/domain/__init__.py`
- Test: `tests/domain/test_projects.py`
- Test: `tests/domain/test_documents.py`
- Test: `tests/domain/test_jobs.py`

- [ ] **Step 1: 写领域不变量测试**

```python
def test_project_version_must_be_positive():
    with pytest.raises(ValidationError):
        Project(id="p1", name="研究", version=0, created_at=NOW, updated_at=NOW)

def test_document_rejects_parent_traversal_name():
    with pytest.raises(ValidationError):
        Document.create(project_id="p1", original_name="../secret.txt", media_type="text/plain")

def test_run_attempt_cannot_exceed_max_attempts():
    with pytest.raises(ValidationError):
        AgentRun(id="r1", project_id="p1", command_id="c1", status="queued", attempt=4, max_attempts=3)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/domain/test_projects.py tests/domain/test_documents.py tests/domain/test_jobs.py -q -p no:cacheprovider`

Expected: FAIL，三个模块不存在。

- [ ] **Step 3: 实现最小 immutable models**

```python
class Project(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str = Field(min_length=1, max_length=120)
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

class Conversation(BaseModel):
    id: str
    project_id: str
    messages: tuple[ConversationMessage, ...] = ()

class Document(BaseModel):
    id: str
    project_id: str
    original_name: str
    media_type: str
    status: Literal["uploaded", "parsing", "ready", "failed"]
    storage_key: str | None = None
    error: str | None = None

class AgentRun(BaseModel):
    id: str
    project_id: str
    command_id: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
```

`Document.create()` 必须仅保留 `Path(name).name` 后再验证其与输入相等，拒绝 `/`、`\\`、空名和 `.`/`..`。

- [ ] **Step 4: 运行 GREEN 与回归**

Run: `uv run pytest tests/domain/test_projects.py tests/domain/test_documents.py tests/domain/test_jobs.py -q -p no:cacheprovider`

Expected: PASS。

Run: `uv run pytest -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/domain tests/domain
git commit -m "功能：增加项目文档与运行领域模型"
```

### Task 3: 固定 ForwardResearchContext 与 Idea Review 输出

**Files:**
- Modify: `src/research_mentor/domain/research.py`
- Modify: `src/research_mentor/agents/idea_review/contracts.py`
- Modify: `src/research_mentor/agents/idea_review/prompting.py`
- Modify: `src/research_mentor/agents/idea_review/prompt.md`
- Test: `tests/agents/test_idea_review.py`
- Test: `tests/agents/test_prompt_contracts.py`

- [ ] **Step 1: 写 forward contract 测试**

```python
def test_forward_requires_research_context():
    with pytest.raises(ValidationError):
        IdeaReviewOutput(decision="forward", reason="继续工作")

def test_forward_context_preserves_normalized_claims():
    output = IdeaReviewOutput(
        decision="forward",
        reason="已有方案进入执行辅导",
        idea_type="working",
        forward_context=ForwardResearchContext(
            normalized_idea="研究缓存失效策略",
            core_claims=("新策略降低尾延迟",),
            constraints=("单机实验",),
            open_questions=("数据集规模未知",),
        ),
    )
    assert output.forward_context.core_claims == ("新策略降低尾延迟",)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/agents/test_idea_review.py tests/agents/test_prompt_contracts.py -q -p no:cacheprovider`

Expected: FAIL，`ForwardResearchContext` 或条件校验不存在。

- [ ] **Step 3: 实现 discriminated output 约束**

```python
class ForwardResearchContext(BaseModel):
    normalized_idea: str = Field(min_length=1)
    core_claims: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()

class IdeaReviewOutput(BaseModel):
    decision: Literal["plan", "forward", "clarify", "reject"]
    reason: str
    idea_type: Literal["idea", "working", "opinion", "range"]
    forward_context: ForwardResearchContext | None = None

    @model_validator(mode="after")
    def require_decision_payload(self):
        if self.decision == "forward" and self.forward_context is None:
            raise ValueError("forward requires forward_context")
        if self.decision != "forward" and self.forward_context is not None:
            raise ValueError("forward_context is only valid for forward")
        return self
```

同步 Prompt：`forward` 直接进入 `working_qa_agent`，Agent 不判断额外前置条件；`opinion` 与 `range` 均由模型判断，不可行可拒绝，范围不明确或过大用 `clarify` 请求更具体方向。

- [ ] **Step 4: 运行 GREEN 与 prompt snapshot 回归**

Run: `uv run pytest tests/agents/test_idea_review.py tests/agents/test_prompt_contracts.py -q -p no:cacheprovider`

Expected: PASS，且 Prompt 中包含四种 decision 的必要条件。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/domain/research.py src/research_mentor/agents/idea_review tests/agents
git commit -m "功能：固定 Idea Review forward 上下文契约"
```

### Task 4: 完整化 Complete 输出与结果影响

**Files:**
- Modify: `src/research_mentor/agents/complete/contracts.py`
- Modify: `src/research_mentor/agents/complete/prompt.md`
- Modify: `src/research_mentor/agents/complete/prompting.py`
- Modify: `src/research_mentor/domain/experiments.py`
- Test: `tests/agents/test_working_and_complete.py`
- Test: `tests/domain/test_experiments.py`

- [ ] **Step 1: 写三种 completion mode 测试**

```python
@pytest.mark.parametrize("mode", ["validation", "plan_revision", "writing"])
def test_complete_output_accepts_supported_mode(mode):
    value = CompleteOutput(mode=mode, summary="结论", result_impact="supports")
    assert value.mode == mode

def test_result_impact_is_explicit():
    assert set(get_args(ResultImpact)) == {"supports", "weakens", "mixed", "inconclusive"}
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/agents/test_working_and_complete.py tests/domain/test_experiments.py -q -p no:cacheprovider`

Expected: FAIL，当前输出未覆盖三种 mode/impact。

- [ ] **Step 3: 实现 union payload**

```python
ResultImpact = Literal["supports", "weakens", "mixed", "inconclusive"]

class CompleteOutput(BaseModel):
    mode: Literal["validation", "plan_revision", "writing"]
    summary: str
    result_impact: ResultImpact
    validation_tasks: tuple[ValidationTaskDraft, ...] = ()
    revision_brief: PlanRevisionBrief | None = None
    writing_brief: WritingBrief | None = None
```

用 `model_validator` 强制只有与 `mode` 对应的 payload 非空；validation 至少一个 draft，plan_revision 必须有 revision brief，writing 必须有 writing brief。

- [ ] **Step 4: 运行 GREEN 与全量回归**

Run: `uv run pytest tests/agents/test_working_and_complete.py tests/domain/test_experiments.py -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/agents/complete src/research_mentor/domain/experiments.py tests/agents/test_working_and_complete.py tests/domain/test_experiments.py
git commit -m "功能：补全实验完成模式与结果影响"
```

### Task 5: 扩展 phase、task factory 与 check round

**Files:**
- Modify: `src/research_mentor/harness/state.py`
- Create: `src/research_mentor/harness/tasks.py`
- Modify: `src/research_mentor/harness/scoring.py`
- Test: `tests/harness/test_state_v1.py`
- Test: `tests/harness/test_scoring.py`

- [ ] **Step 1: 写状态与 round 测试**

```python
def test_factory_creates_typed_task_ids():
    factory = TaskFactory(id_factory=SequenceIds("task"))
    assert factory.validation("复现实验").kind == "validation"

def test_check_round_records_harness_score():
    round_ = CheckRound.from_agent_output(output=CHECK_OUTPUT, threshold=6.0)
    assert round_.final_score == 6.4
    assert round_.passed is True
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_state_v1.py tests/harness/test_scoring.py -q -p no:cacheprovider`

Expected: FAIL，factory/round 尚不存在。

- [ ] **Step 3: 实现显式 phase 与 task types**

```python
Phase = Literal[
    "idea_review", "awaiting_clarification", "planning", "checking",
    "awaiting_plan_confirmation", "working", "completing",
    "awaiting_validation_selection", "awaiting_result_record", "finished",
]

class CheckRound(BaseModel):
    round_number: int = Field(ge=1)
    output: KeyInsightCheckOutput
    final_score: float = Field(ge=0, le=10)
    passed: bool

class ValidationTask(ExperimentTask):
    kind: Literal["validation"] = "validation"
    source_result_id: str
```

`TaskFactory` 是唯一创建 task id/status/default fields 的位置。

- [ ] **Step 4: 运行 GREEN 与全量回归**

Run: `uv run pytest tests/harness/test_state_v1.py tests/harness/test_scoring.py -q -p no:cacheprovider`

Expected: PASS，`final_score >= 6.0` 仍是唯一通过条件。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/harness tests/harness
git commit -m "功能：扩展 v1 状态与任务工厂"
```

### Task 6: 实现 completion routing 与 validation queue

**Files:**
- Modify: `src/research_mentor/harness/routing.py`
- Create: `src/research_mentor/harness/validation.py`
- Test: `tests/harness/test_completion_routing.py`
- Test: `tests/harness/test_validation_queue.py`

- [ ] **Step 1: 写路由测试**

```python
@pytest.mark.parametrize(
    ("mode", "phase"),
    [("validation", "awaiting_validation_selection"),
     ("plan_revision", "planning"),
     ("writing", "finished")],
)
def test_complete_mode_routes_deterministically(mode, phase):
    assert route_complete(make_complete(mode)).next_phase == phase

def test_queue_selects_only_known_pending_tasks():
    queue = ValidationQueue.from_drafts(RESULT_ID, DRAFTS, SequenceIds("v"))
    with pytest.raises(UnknownValidationTask):
        queue.select(("missing",))
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_completion_routing.py tests/harness/test_validation_queue.py -q -p no:cacheprovider`

Expected: FAIL，新模块和 route 不存在。

- [ ] **Step 3: 实现 pure routing**

```python
def route_complete(output: CompleteOutput) -> RoutingDecision:
    phase_by_mode = {
        "validation": "awaiting_validation_selection",
        "plan_revision": "planning",
        "writing": "finished",
    }
    return RoutingDecision(next_phase=phase_by_mode[output.mode], reason=output.summary)
```

`ValidationQueue.select(ids)` 返回新 queue，不允许未知、重复、已完成 id；选中项按原顺序变成 `selected`，未选中项保持 `pending`。

- [ ] **Step 4: 运行 GREEN 与回归**

Run: `uv run pytest tests/harness/test_completion_routing.py tests/harness/test_validation_queue.py -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/harness tests/harness
git commit -m "功能：实现完成路由与验证任务队列"
```

## Milestone B：持久化、文档与检索 Providers

### Task 7: 定义 repository、unit of work 与 event ports

**Files:**
- Modify: `src/research_mentor/ports/repository.py`
- Create: `src/research_mentor/ports/events.py`
- Create: `src/research_mentor/ports/files.py`
- Create: `src/research_mentor/ports/documents.py`
- Test: `tests/ports/test_repository_contract.py`

- [ ] **Step 1: 写 contract test fake**

```python
async def test_uow_commits_session_and_events_atomically(repository_uow):
    async with repository_uow as uow:
        session = await uow.sessions.get("s1")
        await uow.sessions.save(session.model_copy(update={"phase": "working"}), expected_version=1)
        await uow.events.append(PublicEvent(project_id="p1", type="phase.changed", payload={"phase": "working"}))
    saved = await repository_uow.sessions.get("s1")
    assert saved.version == 2
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/ports/test_repository_contract.py -q -p no:cacheprovider`

Expected: FAIL，UoW/event/file/parser contracts 不存在。

- [ ] **Step 3: 定义 ports**

```python
class UnitOfWork(Protocol):
    sessions: SessionRepository
    projects: ProjectRepository
    documents: DocumentRepository
    runs: RunRepository
    events: EventRepository
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...

class SessionRepository(Protocol):
    async def get(self, session_id: str) -> ResearchSession: ...
    async def save(self, session: ResearchSession, expected_version: int) -> None: ...

class FileStore(Protocol):
    async def put(self, project_id: str, document_id: str, name: str, content: AsyncIterator[bytes]) -> StoredFile: ...

class DocumentParser(Protocol):
    async def parse(self, stored_file: StoredFile) -> ParsedDocument: ...
```

重复 `(project_id, idempotency_key)` 必须由 repository 返回已有 command/run；version 不匹配抛 `ConcurrencyConflict`。

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
        "alembic_version", "projects", "sessions", "conversations", "messages",
        "documents", "document_chunks", "agent_runs", "commands", "events",
    }
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/sql/test_migrations.py -q -p no:cacheprovider`

Expected: FAIL，migration config 不存在。

- [ ] **Step 3: 实现 schema 与初始 migration**

必须包含：UUID/text primary key、project foreign keys、`sessions.version`、JSON payload、UTC timestamps；`commands(project_id,idempotency_key)` unique；`events(project_id,sequence)` unique；documents/chunks cascade delete。SQLAlchemy models 仅负责 persistence mapping，不继承 domain models。

关键约束：

```python
UniqueConstraint("project_id", "idempotency_key", name="uq_command_idempotency")
UniqueConstraint("project_id", "sequence", name="uq_event_sequence")
CheckConstraint("version >= 1", name="ck_session_version_positive")
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
            await uow.projects.add(PROJECT)
            await uow.events.append(EVENT)
            raise RuntimeError("abort")
    assert await count_rows(sql_uow, "projects") == 0
    assert await count_rows(sql_uow, "events") == 0

async def test_stale_session_update_raises_conflict(sql_uow, seeded_session):
    async with sql_uow() as uow:
        with pytest.raises(ConcurrencyConflict):
            await uow.sessions.save(seeded_session, expected_version=0)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/sql/test_uow.py tests/adapters/sql/test_concurrency.py -q -p no:cacheprovider`

Expected: FAIL，repositories/uow 不存在。

- [ ] **Step 3: 实现 transaction 与 compare-and-swap**

```python
stmt = (
    update(SessionRow)
    .where(SessionRow.id == session.id, SessionRow.version == expected_version)
    .values(payload=session.model_dump(mode="json"), version=expected_version + 1)
)
result = await self._db.execute(stmt)
if result.rowcount != 1:
    raise ConcurrencyConflict(session.id, expected_version)
```

UoW `__aexit__` 在无异常时 commit，有异常时 rollback。public event 与 aggregate 更新必须使用同一 `AsyncSession`。

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
- Create: `src/research_mentor/adapters/documents/storage.py`
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
    saved = await store.put("p1", "d1", "paper.md", bytes_stream(b"hello"))
    assert saved.path == tmp_path / "p1" / "d1" / "source.bin"

def test_chunker_preserves_offsets_and_overlap():
    chunks = MarkdownChunker(max_chars=12, overlap_chars=3).split("第一段内容。\n\n第二段内容。")
    assert chunks[0].start_offset == 0
    assert all(c.end_offset > c.start_offset for c in chunks)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/documents -q -p no:cacheprovider`

Expected: FAIL，document adapters 不存在。

- [ ] **Step 3: 实现 storage/parser/chunker**

`LocalFileStore` 路径固定为 `{root}/{safe_project_id}/{document_id}/source.bin`，同时写 metadata 到数据库，不执行用户文件。`PlainTextParser` 支持 `text/plain`、Markdown；`AnydocParser` 用 `await anyio.to_thread.run_sync(anydoc.to_markdown_bytes, content, format_name)` 返回规范化 Markdown，解析异常映射为 typed `DocumentParseFailed`。`MarkdownChunker` 使用标题/段落优先边界，输出稳定 `chunk_id = sha256(document_id:index:text)`、offset 与 heading path。

```python
class ParsedDocument(BaseModel):
    markdown: str
    title: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

class DocumentChunk(BaseModel):
    id: str
    document_id: str
    ordinal: int
    text: str
    start_offset: int
    end_offset: int
    heading_path: tuple[str, ...] = ()
```

- [ ] **Step 4: 运行 GREEN 与 traversal regression**

Run: `uv run pytest tests/adapters/documents -q -p no:cacheprovider`

Expected: PASS，包括绝对路径、`..`、Unicode 文件名与空文件。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/adapters/documents tests/adapters/documents
git commit -m "功能：实现安全文档存储解析与切块"
```

### Task 11: 实现 OpenAlex 文献检索 adapter

**Files:**
- Create: `src/research_mentor/adapters/retrieval/openalex.py`
- Create: `src/research_mentor/adapters/retrieval/http.py`
- Modify: `src/research_mentor/ports/retrieval.py`
- Test: `tests/adapters/retrieval/test_openalex.py`

- [ ] **Step 1: 写 HTTP contract tests**

```python
async def test_openalex_maps_work_to_literature_record(respx_mock):
    respx_mock.get("https://api.openalex.org/works").mock(return_value=Response(200, json=OPENALEX_PAGE))
    records = await OpenAlexRetriever(httpx.AsyncClient(), mailto="dev@example.com").search("cache invalidation", limit=2)
    assert records[0].title == "A Cache Study"
    assert records[0].doi == "https://doi.org/10.1/example"
    assert records[0].source == "openalex"

async def test_openalex_retries_429_once(respx_mock):
    route = respx_mock.get("https://api.openalex.org/works").mock(side_effect=[Response(429), Response(200, json=EMPTY_PAGE)])
    await OpenAlexRetriever(httpx.AsyncClient(), sleep=immediate_sleep).search("x")
    assert route.call_count == 2
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/retrieval/test_openalex.py -q -p no:cacheprovider`

Expected: FAIL，OpenAlex adapter 不存在。

- [ ] **Step 3: 实现 query、mapping 与错误分类**

```python
params = {
    "search": query,
    "per-page": min(limit, 50),
    "select": "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index",
    "mailto": self._mailto,
}
```

只重试 429、502、503、504，最多 3 次并 respect `Retry-After`；4xx 语义错误不重试。反转 abstract 转为纯文本，缺失字段保留 `None`，不得生成 DOI/URL。

- [ ] **Step 4: 运行 GREEN 与 network isolation test**

Run: `uv run pytest tests/adapters/retrieval/test_openalex.py -q -p no:cacheprovider`

Expected: PASS，测试不访问真实网络。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/adapters/retrieval src/research_mentor/ports/retrieval.py tests/adapters/retrieval
git commit -m "功能：接入 OpenAlex 文献检索"
```

### Task 12: 实现项目 chunk 检索与可选 FlagEmbedding ranker

**Files:**
- Create: `src/research_mentor/adapters/retrieval/project_chunks.py`
- Create: `src/research_mentor/adapters/retrieval/ranking.py`
- Modify: `pyproject.toml`
- Test: `tests/adapters/retrieval/test_project_chunks.py`
- Test: `tests/adapters/retrieval/test_ranking.py`

- [ ] **Step 1: 写 fallback 与 rank test**

```python
def test_lexical_ranker_is_deterministic():
    ranked = LexicalRanker().rank("缓存 延迟", CHUNKS, limit=2)
    assert [item.chunk.id for item in ranked] == ["c2", "c1"]

def test_flag_ranker_reports_unavailable_without_optional_dependency(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)
    with pytest.raises(ProviderUnavailable, match="FlagEmbedding"):
        FlagEmbeddingRanker("BAAI/bge-reranker-v2-m3")
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/retrieval/test_project_chunks.py tests/adapters/retrieval/test_ranking.py -q -p no:cacheprovider`

Expected: FAIL，ranker/retriever 不存在。

- [ ] **Step 3: 实现 SQL candidate query 和两种 ranker**

Run: `uv add --optional local-ranking FlagEmbedding`

`ProjectChunkRetriever` 先按 `project_id` 和 SQL 文本候选召回，再调用 `Ranker.rank()`；不配置 local ranking 时使用无模型的 `LexicalRanker`。返回：

```python
class RankedChunk(BaseModel):
    chunk: DocumentChunk
    score: float
    citation: EvidenceRef
```

`EvidenceRef.support` 必须由调用侧传入具体判断，不得由 ranker 伪造；ranker 只给相关度和 chunk provenance。

- [ ] **Step 4: 运行 GREEN 与 optional import regression**

Run: `uv run pytest tests/adapters/retrieval/test_project_chunks.py tests/adapters/retrieval/test_ranking.py -q -p no:cacheprovider`

Expected: PASS，默认环境不下载模型。

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml uv.lock src/research_mentor/adapters/retrieval tests/adapters/retrieval
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
    model = ScriptedStructuredModel([{"decision": "reject", "reason": "不可行", "idea_type": "idea"}])
    result = await model.generate(system="s", user="u", output_type=IdeaReviewOutput)
    assert isinstance(result, IdeaReviewOutput)

async def test_scripted_model_rejects_wrong_schema():
    model = ScriptedStructuredModel([{"unexpected": True}])
    with pytest.raises(ModelOutputInvalid):
        await model.generate(system="s", user="u", output_type=IdeaReviewOutput)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/ports/test_model_contract.py -q -p no:cacheprovider`

Expected: FAIL，现有 port 是同步或不接受 generic output type。

- [ ] **Step 3: 实现 generic async port 并迁移 runners**

```python
OutputT = TypeVar("OutputT", bound=BaseModel)

class StructuredModelPort(Protocol):
    async def generate(
        self,
        *,
        system: str,
        user: str,
        output_type: type[OutputT],
        trace: ModelTraceContext,
    ) -> OutputT: ...
```

五个 runner 都改成 `async def run(...)` 并 `await model.generate(...)`；Prompt builder 保持 pure/sync。

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
- Create: `src/research_mentor/adapters/llm/openai_responses.py`
- Create: `src/research_mentor/adapters/llm/openai_compatible.py`
- Create: `src/research_mentor/adapters/llm/errors.py`
- Test: `tests/adapters/llm/test_openai_responses.py`
- Test: `tests/adapters/llm/test_openai_compatible.py`

- [ ] **Step 1: 写 structured output mapping tests**

```python
async def test_responses_adapter_returns_parsed_model(fake_openai):
    fake_openai.responses.parse.return_value.output_parsed = REVIEW_OUTPUT
    result = await OpenAIResponsesModel(fake_openai, "gpt-5-mini").generate(
        system="mentor", user="idea", output_type=IdeaReviewOutput, trace=TRACE
    )
    assert result == REVIEW_OUTPUT

async def test_compatible_adapter_maps_invalid_json(fake_http):
    fake_http.post.return_value = Response(200, json=INVALID_JSON_RESPONSE)
    with pytest.raises(ModelOutputInvalid):
        await compatible_model(fake_http).generate(system="s", user="u", output_type=IdeaReviewOutput, trace=TRACE)
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/adapters/llm -q -p no:cacheprovider`

Expected: FAIL，adapters 不存在。

- [ ] **Step 3: 实现 provider adapters**

Responses adapter 使用 SDK `responses.parse(..., text_format=output_type)`；compatible adapter 发送 JSON Schema 并用 `output_type.model_validate_json(content)`。两者记录 provider request id、model、latency 和 usage 到 trace metadata，但不记录 API key 或完整上传文档。

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
git add src/research_mentor/adapters/llm tests/adapters/llm
git commit -m "功能：接入结构化 LLM providers"
```

### Task 15: 构建 Idea Review 两阶段检索上下文

**Files:**
- Create: `src/research_mentor/harness/retrieval_context.py`
- Modify: `src/research_mentor/agents/idea_review/runner.py`
- Modify: `src/research_mentor/agents/idea_review/contracts.py`
- Test: `tests/harness/test_idea_review_retrieval.py`

- [ ] **Step 1: 写 normalize → retrieve → judge 顺序测试**

```python
async def test_idea_review_retrieves_after_normalization(spy_model, spy_retriever):
    result = await pipeline.review(INITIAL_INPUT)
    assert spy_model.calls[0].output_type is IdeaNormalization
    assert spy_retriever.queries == ["normalized cache invalidation tail latency"]
    assert spy_model.calls[1].output_type is IdeaReviewOutput
    assert result.evidence_refs[0].support == "支撑尾延迟可测量性判断"

def test_search_plan_has_one_to_four_bounded_queries():
    plan = SearchPlan(queries=("cache invalidation tail latency",))
    assert 1 <= len(plan.queries) <= 4
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_idea_review_retrieval.py -q -p no:cacheprovider`

Expected: FAIL，pipeline/context 不存在。

- [ ] **Step 3: 实现 bounded 两阶段 pipeline**

```python
normalization = await normalizer.run(initial_input)
search_plan = await planner.run(normalization)
literature = await literature_retriever.search_many(search_plan.queries, limit_per_query=12)
project_chunks = await project_retriever.search_many(project_id, search_plan.queries, limit_per_query=8)
return await reviewer.run(
    IdeaReviewInput(
        idea=initial_input,
        sys_input=sys_input,
        normalization=normalization,
        literature_records=tuple(deduplicate_and_rank(literature)),
        project_evidence=tuple(project_chunks),
        retrieval_diagnostics=RetrievalDiagnostics.from_results(search_plan, literature, project_chunks),
    )
)
```

Idea normalization 只产出 normalized idea、claims、constraints 和 query terms，不做最终 `idea_type/decision`。`SearchPlan` 强制 1–4 条长度受限 query；合并结果按 work id/DOI 去重并记录每条 query 的命中数、rank availability 和 provider error。只有实际支撑判断的记录进入 `EvidenceRef`；所有检索结果保留为 `LiteratureRecord`。

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
- Create: `src/research_mentor/harness/working_context.py`
- Modify: `src/research_mentor/agents/working_qa/contracts.py`
- Modify: `src/research_mentor/agents/working_qa/runner.py`
- Test: `tests/harness/test_working_context.py`

- [ ] **Step 1: 写上下文预算和 evidence 测试**

```python
async def test_working_context_keeps_current_task_and_recent_results(builder):
    context = await builder.build(SESSION_WITH_LONG_HISTORY, "为什么延迟升高？", token_budget=2400)
    assert context.current_task.id == SESSION_WITH_LONG_HISTORY.current_task_id
    assert len(context.history_summary) < 3000
    assert all(ref.source_id for ref in context.evidence_refs)

async def test_no_retrieval_guidelines_when_no_retrieval_needed(builder):
    context = await builder.build(SESSION, "当前任务是什么？", token_budget=2400)
    assert context.sys_input.retrieval_guidelines == ()

async def test_rank_unavailable_does_not_decline_question(builder_with_unavailable_ranker):
    context = await builder_with_unavailable_ranker.build(SESSION, "比较另一种缓存策略", token_budget=2400)
    assert context.relevance.status == "unknown"
    assert context.relevance.reason == "ranker_unavailable"
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_working_context.py -q -p no:cacheprovider`

Expected: FAIL，working context builder 不存在。

- [ ] **Step 3: 实现 deterministic context policy**

顺序固定为：current task/plan → relevant recorded results → recent messages → selected project chunks/literature → compacted older history。是否检索由 Harness 的 query classifier 决定；不检索时构造基础 `SysInput`，检索时才构造 `RetrievalSysInput`。只有 rank 正常且相关度低于固定阈值才能 decline；ranker unavailable 时状态为 unknown，继续回答并披露证据限制。

```python
class WorkingContext(BaseModel):
    current_task: ExperimentTask
    active_plan: ResearchPlan | None
    relevant_results: tuple[ExperimentResult, ...]
    recent_messages: tuple[ConversationMessage, ...]
    history_summary: str
    evidence_refs: tuple[EvidenceRef, ...]
```

- [ ] **Step 4: 运行 GREEN 与长上下文 regression**

Run: `uv run pytest tests/harness/test_working_context.py -q -p no:cacheprovider`

Expected: PASS，并确保同输入产生相同排序和 summary boundary。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/harness/working_context.py src/research_mentor/agents/working_qa tests/harness/test_working_context.py
git commit -m "功能：实现 Working QA 上下文选择"
```

## Milestone D：完整 Orchestrator 与 Application Commands

### Task 17: 完成 Idea Review 到 plan/forward/clarify/reject 的 orchestration

**Files:**
- Modify: `src/research_mentor/harness/orchestrator.py`
- Modify: `src/research_mentor/harness/routing.py`
- Test: `tests/harness/test_orchestrator_idea_review_v1.py`

- [ ] **Step 1: 写四路集成测试**

```python
@pytest.mark.parametrize(
    ("decision", "phase"),
    [("plan", "planning"), ("forward", "working"),
     ("clarify", "awaiting_clarification"), ("reject", "finished")],
)
async def test_review_decision_has_single_route(decision, phase, orchestrator_factory):
    session = await orchestrator_factory(review_output(decision)).submit_idea(PROJECT_ID, INITIAL_INPUT)
    assert session.phase == phase

async def test_forward_initializes_working_context_and_task(orchestrator_factory):
    session = await orchestrator_factory(FORWARD_OUTPUT).submit_idea(PROJECT_ID, INITIAL_INPUT)
    assert session.research_context == FORWARD_OUTPUT.forward_context
    assert session.current_task.kind == "working"

async def test_non_cs_domain_is_rejected_before_specialist_pipeline(orchestrator_factory):
    session = await orchestrator_factory(NON_CS_OUTPUT).submit_idea(PROJECT_ID, NON_CS_INPUT)
    assert session.terminal_reason == "unsupported_domain"
    assert orchestrator_factory.plan_agent.call_count == 0

async def test_range_clarification_can_be_resubmitted(orchestrator_factory):
    session = await orchestrator_factory(RANGE_CLARIFY_THEN_PLAN).submit_idea(PROJECT_ID, RANGE_INPUT)
    revised = await orchestrator_factory.answer_clarification(session.id, "限定为数据库缓存一致性")
    assert revised.phase == "planning"
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_orchestrator_idea_review_v1.py -q -p no:cacheprovider`

Expected: FAIL，forward 尚有旧停点或未初始化 task。

- [ ] **Step 3: 实现单事务状态转换**

`submit_idea` 在 UoW 内写 conversation message、agent run result、session phase/task 与 public events。forward 不再进入 `AWAITING_WORKING_CONTEXT`；由 `TaskFactory.working(forward_context)` 直接初始化。clarify 保存问题并等待 `answer_clarification` command；reject 保存具体原因和改进方向。

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
- Modify: `src/research_mentor/harness/orchestrator.py`
- Modify: `src/research_mentor/harness/state.py`
- Test: `tests/harness/test_orchestrator_plan_loop_v1.py`

- [ ] **Step 1: 写通过、修订和上限测试**

```python
async def test_check_pass_waits_for_user_confirmation(orchestrator):
    session = await orchestrator.generate_plan(PROJECT_ID)
    assert session.phase == "awaiting_plan_confirmation"
    assert session.check_rounds[-1].passed is True

async def test_failed_check_revises_until_max_rounds(orchestrator_with_failures):
    session = await orchestrator_with_failures.generate_plan(PROJECT_ID)
    assert len(session.check_rounds) == session.max_check_rounds
    assert session.phase == "awaiting_plan_confirmation"
    assert session.requires_risk_acknowledgement is True

async def test_low_dimension_does_not_veto_passing_total(orchestrator):
    session = await orchestrator.with_check(scores(evidence_support=2.4, final=6.0)).generate_plan(PROJECT_ID)
    assert session.check_rounds[-1].passed is True

async def test_user_revision_resets_internal_round_and_override_is_audited(orchestrator):
    revised = await orchestrator.request_plan_revision(PROJECT_ID, "减少实验规模")
    assert revised.current_check_round == 0
    overridden = await orchestrator.override_plan(PROJECT_ID, reason="资源窗口即将关闭")
    assert overridden.audit[-1].reason == "资源窗口即将关闭"
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_orchestrator_plan_loop_v1.py -q -p no:cacheprovider`

Expected: FAIL，round history/risk acknowledgement 未完整实现。

- [ ] **Step 3: 实现 Harness-owned loop**

每轮顺序固定 `plan_loop → key_insight_check → harness score`。分数 `>= 6.0` 结束；否则把 structured `revision_advice` 注入下一次 plan revision；达到 `max_check_rounds` 后展示最高分方案并要求用户确认风险。Agent 不能修改 round/threshold/pass。

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
- Modify: `src/research_mentor/harness/orchestrator.py`
- Modify: `src/research_mentor/harness/validation.py`
- Test: `tests/harness/test_orchestrator_completion_v1.py`

- [ ] **Step 1: 写结果和三路状态测试**

```python
async def test_record_result_requires_user_payload(orchestrator):
    with pytest.raises(InvalidCommandForPhase):
        await orchestrator.complete_without_result(PROJECT_ID)

async def test_validation_selection_creates_tasks_in_order(orchestrator):
    await orchestrator.record_result(PROJECT_ID, RESULT)
    session = await orchestrator.select_validations(PROJECT_ID, ("v2", "v1"))
    assert [t.id for t in session.validation_tasks if t.status == "selected"] == ["v2", "v1"]

async def test_plan_revision_returns_to_check_loop(orchestrator):
    session = await orchestrator.record_result(PROJECT_ID, RESULT_TRIGGERING_REVISION)
    assert session.phase == "planning"
    assert session.plan_revision_brief is not None

async def test_skip_critical_validation_preserves_both_reasons(orchestrator):
    session = await orchestrator.skip_validation(
        PROJECT_ID, task_id="critical-v1", user_reason="没有第二块 GPU"
    )
    skipped = session.validation_queue.by_id("critical-v1")
    assert skipped.user_reason == "没有第二块 GPU"
    assert skipped.mentor_reason

@pytest.mark.parametrize("status", ["completed", "negative", "failed"])
async def test_validation_outcome_returns_to_complete(orchestrator, status):
    session = await orchestrator.record_validation_result(PROJECT_ID, validation_result(status))
    assert session.phase == "completing"
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/harness/test_orchestrator_completion_v1.py -q -p no:cacheprovider`

Expected: FAIL，completion modes 未完全接线。

- [ ] **Step 3: 实现结果影响和 loop**

`record_result` 是唯一进入 Complete 的入口。validation 先停在选择 gate，选择后逐项创建/执行/记录结果并可再次 Complete；plan_revision 生成 revision brief 后回到 Task 18；writing 保存 writing brief 并进入 finished。每次结果保留 `result_impact` 与 EvidenceRef。

- [ ] **Step 4: 运行 GREEN 与完整 harness suite**

Run: `uv run pytest tests/harness -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/harness tests/harness/test_orchestrator_completion_v1.py
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

- [ ] **Step 1: 写 idempotency 与非法 command 测试**

```python
async def test_same_idempotency_key_returns_same_result(command_bus):
    first = await command_bus.dispatch(SubmitIdea(project_id="p1", idea="x", idempotency_key="k1"))
    second = await command_bus.dispatch(SubmitIdea(project_id="p1", idea="x", idempotency_key="k1"))
    assert second.command_id == first.command_id
    assert second.run_id == first.run_id

def test_phase_exposes_explicit_allowed_commands():
    assert allowed_commands("awaiting_result_record") == ("record_result", "ask_working_question")
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/application/test_command_bus.py tests/application/test_allowed_commands.py -q -p no:cacheprovider`

Expected: FAIL，application layer 不存在。

- [ ] **Step 3: 实现 command union 与 dispatch**

```python
Command = Annotated[
    SubmitIdea | AnswerClarification | RevisePlan | OverridePlan | ConfirmPlan |
    AskWorkingQuestion | RecordResult | SelectValidations | SkipValidation |
    RestartResearch | CancelRun,
    Field(discriminator="type"),
]

class CommandBus:
    async def dispatch(self, command: Command) -> CommandReceipt:
        async with self._uow_factory() as uow:
            existing = await uow.commands.find(command.project_id, command.idempotency_key)
            if existing is not None:
                return existing.receipt
            assert_allowed(command.type, (await uow.sessions.for_project(command.project_id)).phase)
            return await self._handlers[type(command)](command, uow)
```

所有 mutation 必须带 `idempotency_key` 与可选 `expected_version`；phase guard 在调用 Agent 前执行。`RestartResearch` 封存当前 cycle 并创建同 project 下的新 session，旧 cycle 保持可查询和可导出；等待用户输入的 phase 没有自动超时 command。

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
    run_repo.seed(run(status="queued", attempt=0, max_attempts=3))
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
    session_repo.seed(session(phase="awaiting_plan_confirmation", updated_at=PAST))
    await recovery.requeue_expired()
    assert (await session_repo.get("s1")).phase == "awaiting_plan_confirmation"
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/application/test_run_worker.py tests/application/test_recovery.py -q -p no:cacheprovider`

Expected: FAIL，worker/recovery 不存在。

- [ ] **Step 3: 实现数据库 lease state machine**

```python
QUEUED -> RUNNING -> SUCCEEDED
QUEUED -> CANCELLED
RUNNING -> QUEUED      # transient error 且 attempt < max_attempts
RUNNING -> FAILED      # permanent error 或耗尽重试
RUNNING -> CANCELLED   # cooperative cancellation boundary
```

worker 用 compare-and-swap 获取 60 秒 lease；每次 provider 调用前后检查 cancellation。retry delay 为 `min(2 ** attempt, 30)` 秒并存储 `available_at`，不在请求线程 sleep。启动时 recovery 只重排过期 lease，不重复成功 run。

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
    response = await api_client.get("/api/health")
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
    container = await build_container(Settings())
    app.state.container = container
    await container.recovery.requeue_expired()
    await container.worker.start()
    yield
    await container.worker.stop()
    await container.engine.dispose()

def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Research Mentor API", version="1.0.0", lifespan=lifespan)
    app.include_router(api_router, prefix="/api")
    return app
```

`build_container` 根据 settings 选择 demo/真实 providers；routes 不直接 new repository/provider。

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
    created = await api_client.post("/api/projects", json={"name": "缓存研究"})
    assert created.status_code == 201
    view = await api_client.get(f"/api/projects/{created.json()['id']}")
    assert view.json()["allowed_commands"] == ["submit_idea"]

async def test_stale_command_returns_409(api_client, seeded_project):
    response = await api_client.post(
        f"/api/projects/{seeded_project}/commands",
        headers={"Idempotency-Key": "k1"},
        json={"type": "submit_idea", "idea": "x", "expected_version": 99},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/api/test_projects.py tests/api/test_commands.py -q -p no:cacheprovider`

Expected: FAIL，routes/views 不存在。

- [ ] **Step 3: 实现稳定 endpoint contracts**

Endpoints：

```text
POST /api/projects
GET  /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}/commands
GET  /api/projects/{project_id}/runs/{run_id}
POST /api/projects/{project_id}/runs/{run_id}/cancel
```

command 返回 `202 CommandReceipt`；重复 idempotency key 返回相同 receipt。错误统一 `{error:{code,message,details,request_id}}`：validation=422、not found=404、phase/version conflict=409、provider unavailable=503。

- [ ] **Step 4: 运行 GREEN 与 OpenAPI snapshot**

Run: `uv run pytest tests/api/test_projects.py tests/api/test_commands.py -q -p no:cacheprovider`

Expected: PASS，OpenAPI 包含 6 个 endpoints 与 discriminated command schema。

- [ ] **Step 5: Commit**

```powershell
git add src/research_mentor/api src/research_mentor/application/views.py tests/api
git commit -m "功能：提供项目与命令 API"
```

### Task 24: 实现文档上传、状态、下载与研究日志导出

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
        f"/api/projects/{project_id}/documents",
        files={"file": ("notes.md", b"# Experiment", "text/markdown")},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "uploaded"

def test_journal_markdown_contains_provenance(renderer):
    text = renderer.to_markdown(PROJECT_VIEW)
    assert "## 实验结果" in text
    assert "OpenAlex" in text
    assert "EvidenceRef" not in text
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/api/test_documents.py tests/application/test_journal.py -q -p no:cacheprovider`

Expected: FAIL，routes/service/renderer 不存在。

- [ ] **Step 3: 实现限制、异步 parse job 与 exports**

允许扩展名/MIME：`.txt`、`.md`、`.pdf`、`.docx`；单文件上限 20 MiB；stream 写入并计算 sha256，超限立即删除 incomplete blob。上传后创建 `document.parse` run；状态由 uploaded → parsing → ready/failed。Endpoints：

```text
POST /api/projects/{project_id}/documents
GET  /api/projects/{project_id}/documents
GET  /api/projects/{project_id}/documents/{document_id}
GET  /api/projects/{project_id}/export?format=json|markdown
```

JSON journal 使用 versioned schema；Markdown 按 idea、plan/check、tasks、results、evidence、writing brief 顺序，引用显示 title/author/year/URL 或文档名/chunk。

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
        "/api/projects/p1/events",
        headers={"Last-Event-ID": "2"},
    )
    body = response.text
    assert "id: 3" in body
    assert "id: 1" not in body

async def test_event_payload_never_contains_prompt_or_secret(api_client, seeded_events):
    body = (await api_client.get("/api/projects/p1/events")).text
    assert "system_prompt" not in body
    assert "api_key" not in body
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

先查询 `sequence > Last-Event-ID` 的持久事件，再每 1 秒轮询新事件；15 秒无事件发送 comment heartbeat。公开类型包括 `run.queued|started|succeeded|failed|cancelled`、`phase.changed`、`document.updated`、`message.created`。

- [ ] **Step 4: 运行 GREEN**

Run: `uv run pytest tests/api/test_events.py -q -p no:cacheprovider`

Expected: PASS，断线重连无漏项且允许重复消费。

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
    assert [p.demo_stage for p in projects] == ["idea", "working", "completion"]

async def test_demo_seed_is_idempotent(demo_service):
    first = await demo_service.ensure_seeded()
    second = await demo_service.ensure_seeded()
    assert [p.id for p in first] == [p.id for p in second]
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/application/test_demo.py -q -p no:cacheprovider`

Expected: FAIL，demo service/adapters 不存在。

- [ ] **Step 3: 实现固定 fixture 脚本**

三个项目分别停在 idea/review、working/result、completion/validation selection；demo model 按 command + phase 返回已通过 Pydantic 验证的固定输出；demo retrieval 返回明确标注 `demo://` provenance 的资料。所有 demo project view 都包含 `is_demo=true`，避免与真实结果混淆。

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

- [ ] **Step 1: 初始化依赖并写 client RED test**

Run:

```powershell
Set-Location frontend
npm init -y
npm install react@19 react-dom@19
npm install -D typescript vite @vitejs/plugin-react vitest jsdom @testing-library/react @testing-library/jest-dom @types/react @types/react-dom
```

Test：

```typescript
it("sends idempotency key for commands", async () => {
  const fetcher = vi.fn().mockResolvedValue(okJson({ command_id: "c1", run_id: "r1" }));
  await createClient(fetcher).dispatchCommand("p1", { type: "submit_idea", idea: "x" }, "k1");
  expect(fetcher.mock.calls[0][1].headers["Idempotency-Key"]).toBe("k1");
});
```

- [ ] **Step 2: 运行 RED**

Run: `npm test -- --run src/api/client.test.ts`

Expected: FAIL，client 不存在。

- [ ] **Step 3: 实现最小 shell、types 和 client**

```typescript
export type Phase =
  | "idea_review" | "awaiting_clarification" | "planning" | "checking"
  | "awaiting_plan_confirmation" | "working" | "completing"
  | "awaiting_validation_selection" | "awaiting_result_record" | "finished";

export interface ProjectView {
  id: string;
  name: string;
  version: number;
  phase: Phase;
  allowed_commands: CommandType[];
  is_demo: boolean;
}
```

API client 对非 2xx 解析统一 `ApiError`；SSE client 保存最后 event id，重连后调用一次 project view refresh。

- [ ] **Step 4: 运行 GREEN/build**

Run: `npm test -- --run && npm run build`

Expected: PASS，`frontend/dist` 生成。

- [ ] **Step 5: Commit**

```powershell
git add frontend
git commit -m "功能：建立 React 前端与类型化 API client"
```

### Task 28: 实现项目工作台、阶段视图与证据面板

**Files:**
- Create: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/components/ProjectSidebar.tsx`
- Create: `frontend/src/components/PhaseTimeline.tsx`
- Create: `frontend/src/components/RunStatus.tsx`
- Create: `frontend/src/components/EvidencePanel.tsx`
- Create: `frontend/src/components/DocumentPanel.tsx`
- Create: `frontend/src/features/idea/IdeaView.tsx`
- Create: `frontend/src/features/plan/PlanView.tsx`
- Create: `frontend/src/features/working/WorkingView.tsx`
- Create: `frontend/src/features/completion/CompletionView.tsx`
- Create: `frontend/src/features/project/ProjectWorkspace.tsx`
- Test: `frontend/src/features/project/ProjectWorkspace.test.tsx`

- [ ] **Step 1: 写 phase/command/a11y tests**

```typescript
it.each([
  ["idea_review", "提交研究想法"],
  ["awaiting_plan_confirmation", "确认方案"],
  ["awaiting_result_record", "记录实验结果"],
  ["awaiting_validation_selection", "选择验证任务"],
])("renders %s primary action", (phase, label) => {
  render(<ProjectWorkspace project={project({ phase })} />);
  expect(screen.getByRole("button", { name: label })).toBeEnabled();
});

it("marks demo content visibly", () => {
  render(<ProjectWorkspace project={project({ is_demo: true })} />);
  expect(screen.getByText("DEMO DATA")).toBeVisible();
});
```

- [ ] **Step 2: 运行 RED**

Run: `npm test -- --run src/features/project/ProjectWorkspace.test.tsx`

Expected: FAIL，workspace components 不存在。

- [ ] **Step 3: 实现 responsive research workspace**

Desktop 三栏：project/nav 240px、main minmax(0,1fr)、context 360px；窄屏用 tabs/drawer。主视图按 `phase` exhaustive switch 渲染；按钮只从 `allowed_commands` 产生。证据卡显示 source、support、provenance、外链；检查卡显示五维分数、Harness final score 和 threshold；run status 支持 retry/cancel 提示。全局使用中文 UI，技术标识保留英文。

视觉 token：

```css
:root {
  --ink: #16221d; --paper: #f4f1e8; --panel: #fffdf7;
  --mentor: #8d2f23; --accent: #1e6252; --line: #cfc8b8;
  --font-ui: "IBM Plex Sans", "Noto Sans SC", sans-serif;
  --font-reading: "Noto Serif SC", serif;
}
```

- [ ] **Step 4: 运行 GREEN/build 与 keyboard check**

Run: `npm test -- --run && npm run build`

Expected: PASS；所有 form 有 label，焦点可见，dialog 可 Esc 关闭，颜色不作为唯一状态提示。

- [ ] **Step 5: Commit**

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

it("disables command while receipt is pending", async () => {
  render(<IdeaView project={PROJECT} api={deferredApi()} />);
  await user.click(screen.getByRole("button", { name: "提交研究想法" }));
  expect(screen.getByRole("button", { name: "处理中" })).toBeDisabled();
});
```

- [ ] **Step 2: 运行 RED**

Run: `npm test -- --run src/hooks/useProjectEvents.test.tsx src/features/project/ProjectActions.test.tsx`

Expected: FAIL，hooks/connected actions 不存在。

- [ ] **Step 3: 实现 connected UI**

`useCommand` 每次用户动作生成 UUID idempotency key，同一 pending action 复用 key；receipt 后显示 run state。`useProjectEvents` 断线指数退避 1/2/4/8/15 秒，恢复后刷新 view。上传显示进度/parse status；validation selection 保持服务器顺序；错误 banner 显示 request id 与可重试性，不展示 stack trace。

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
- Create: `src/research_mentor/evals/runner.py`
- Create: `tests/evals/test_agent_evals.py`
- Modify: `evals/README.md`

- [ ] **Step 1: 写 dataset schema 与 threshold test**

```python
@pytest.mark.parametrize("dataset", sorted(Path("evals").glob("*_cases.json")))
def test_eval_dataset_is_versioned_and_nonempty(dataset):
    suite = EvalSuite.model_validate_json(dataset.read_text(encoding="utf-8"))
    assert suite.version == "1.0"
    assert len(suite.cases) >= 8

def test_demo_model_passes_required_eval_thresholds():
    report = run_all_evals(build_demo_agents())
    assert report.contract_pass_rate == 1.0
    assert report.behavior_pass_rate >= 0.90
```

- [ ] **Step 2: 运行 RED**

Run: `uv run pytest tests/evals/test_agent_evals.py -q -p no:cacheprovider`

Expected: FAIL，四个 datasets/runner 不存在。

- [ ] **Step 3: 写固定 cases 与 deterministic evaluator**

每个 Agent 至少覆盖正常、边界、证据不足、prompt injection、拒绝/clarify、中文输入；Idea Review 额外覆盖用户错误自称 type；Check 覆盖 5.9/6.0 threshold；Complete 覆盖三种 mode。runner 只评 schema、routing、required phrases/prohibited claims 和 deterministic score，不用另一个 LLM 作为 v1 发布 gate。

- [ ] **Step 4: 运行 GREEN 与全量 Python suite**

Run: `uv run pytest -q -p no:cacheprovider`

Expected: PASS，eval thresholds 达标。

- [ ] **Step 5: Commit**

```powershell
git add evals src/research_mentor/evals tests/evals
git commit -m "测试：扩充五 Agent 行为评估集"
```

### Task 31: 建立 Playwright E2E 与 30 项验收覆盖

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/demo-flow.spec.ts`
- Create: `frontend/tests/e2e/recovery.spec.ts`
- Create: `frontend/tests/e2e/documents.spec.ts`
- Create: `frontend/tests/e2e/accessibility.spec.ts`
- Create: `tests/integration/test_acceptance_matrix.py`

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
```

- [ ] **Step 2: 运行 RED**

Run: `npm run e2e -- --project=chromium`

Expected: FAIL，Playwright config/完整连接尚未验证。

- [ ] **Step 3: 实现四组 E2E**

`demo-flow` 覆盖 review 四路、plan/check、working/result、Complete 三路；`recovery` 覆盖刷新、SSE reconnect、重复 command、stale version、retry/cancel；`documents` 覆盖上传/解析/检索引用/导出；`accessibility` 对 project list 和四个 phase view 执行 axe 并测试 keyboard。`test_acceptance_matrix.py` 固定列出规格 1..30 的 test node id，缺一项即失败。

- [ ] **Step 4: 运行 GREEN**

Run:

```powershell
uv run pytest tests/integration/test_acceptance_matrix.py -q -p no:cacheprovider
Set-Location frontend
npm test -- --run
npm run build
npm run e2e -- --project=chromium
```

Expected: 全部 PASS，30 个 acceptance IDs 全覆盖。

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

README 必须包含：产品截图位置、五 Agent 架构、demo quickstart、真实 OpenAI/OpenAI-compatible 配置、OpenAlex mailto、Anydoc/FlagEmbedding 可选安装、SQLite/PostgreSQL、文件限制、API/SSE contract、测试矩阵、已知 v1 scope。`scripts/dev.ps1` 启动 API worker 和 Vite；`scripts/check.ps1` 顺序执行 migration smoke、Python tests、frontend tests/build、Playwright。

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
| 8 无关问题 decline | 16 | working relevance tests |
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
7. **G gate:** 30 项 acceptance mapping、eval、Playwright、accessibility 与 README quickstart 全部通过。

只有当前 gate 全绿才能进入下一 milestone；provider credential 缺失不应阻止 demo gate，但真实 provider smoke test 必须在有凭据的发布环境单独执行并记录 request id，不能写入仓库。
