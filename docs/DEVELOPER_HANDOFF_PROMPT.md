# 下一名开发者交接 Prompt

请将本文件全文作为下一名开发者在当前本地环境中的初始任务说明。

---

你是一名资深 Agent、Harness、RAG 和 full-stack 工程师。你将接手“傲娇导师（Research Mentor）”项目，在现有设计和实现基础上完成 v1.0，而不是重新设计项目。

## 一、任务目标

从 implementation plan 的 **Task 2** 开始，严格按顺序持续执行到 **Task 32**。不得跳过 Task 或 Milestone gate，不得重复实现已经完成的 Task 1。

你的完成目标是：

1. 完成 Milestone A–G；
2. 使完整 Idea Review、Plan/Check/User gate、Working、Complete 和 validation/revision 流程可运行；
3. 接通真实 structured model、RAG、SQL persistence、documents、FastAPI、SSE、deterministic demo 和 React frontend；
4. 完成五 Agent Eval、Playwright E2E、30 项验收、README 和 release audit；
5. 每个 Task 独立 commit；
6. 每个 Milestone gate 通过后汇报一次，然后直接继续下一 Milestone，无需等待用户再次确认；
7. 只 commit，**不得自动 push、merge、创建 PR 或修改 `main`**。

只有遇到以下情况才停止并请求用户决策：

- 权威文档之间存在无法按优先级消解的实质冲突；
- 必须改变已确认的产品 scope 或架构边界；
- 需要真实凭据、外部付费资源或新的外部权限；
- 当前 Milestone gate 连续诊断后仍无法通过；
- 发现用户已有修改与当前 Task 直接冲突，且无法安全保留。

## 二、当前环境

- 仓库：`D:\A_main\arrogant_teacher\research_mentor_core`
- 当前专用 worktree：`D:\A_main\arrogant_teacher\research_mentor_core\.worktrees\full-product-v1`
- 必须工作的分支：`feature/full-product-v1`
- 已完成实现基线：Task 1
- 必须存在的交接决策 commit：`a0e36ed`（允许 HEAD 更新，但它必须是 HEAD 的 ancestor）
- Python：3.12
- Python 环境与依赖工具：`uv`
- 当前已验证的 core 测试基线：`229 passed`
- 当前分支可能领先 GitHub；这是预期状态，不要因此 push

开始前执行：

```powershell
Set-Location 'D:\A_main\arrogant_teacher\research_mentor_core\.worktrees\full-product-v1'
git branch --show-current
git status --short --branch
git merge-base --is-ancestor a0e36ed HEAD
git log --oneline -8
uv lock --check
uv run pytest -q -p no:cacheprovider
```

预期：

- 当前分支是 `feature/full-product-v1`；
- `git merge-base --is-ancestor` 返回 exit code 0；
- 开始新 Task 前没有未知的未提交修改；
- lock check 通过；
- core 基线为 229 项测试通过。

如果存在未提交修改，先阅读 diff 并判断来源。它们默认属于用户，不得覆盖、删除、reset 或擅自纳入当前 Task。

## 三、必读文档与裁决优先级

开始 Task 2 前必须完整阅读：

1. `docs/PROJECT_STATUS.md`：当前实现、逐文件职责、缺口和接手顺序；
2. `docs/design/2026-08-30-full-product-design.md`：v1.0 最高优先级产品规格；
3. `docs/superpowers/plans/2026-08-30-full-product-implementation.md`：Task 2–32 的唯一执行计划；
4. `docs/design/命名架构具体版.md`：结构化 Schema 与非流程图正文；
5. `docs/design/prompt仓库.md`：公共 Mentor Prompt、五 Agent Prompt 和组合规则；
6. `docs/design/AI+ 创新大赛.md`：产品背景和前端要求；
7. 根目录 `AGENTS.md`（如存在）及环境提供的适用开发指令。

设计冲突时按以下顺序裁决：

1. `2026-08-30-full-product-design.md` 的明确 v1.0 裁决；
2. `命名架构具体版.md` 的结构化 Schema 和非流程图正文；
3. `prompt仓库.md` 的固定 Prompt 和组合规则；
4. `AI+ 创新大赛.md` 的产品与前端要求；
5. 历史流程图和图片。

不得用历史流程图覆盖当前 contract、状态机或验收规格。实施计划若与更高优先级规格冲突，先停止并报告具体文件、段落、类型或 action，不得自行猜测。

## 四、当前架构事实

当前代码是可测试的 deterministic backend core，而不是完整产品：

- 五个 Agent 已有固定 Prompt、Pydantic contracts、Prompt builder 和同步 runner；
- Harness 已有 v0.1 session state、routing、scoring、orchestrator 和 event；
- ports 已有 model、retrieval、repository、clock 的最小同步边界；
- adapters 只有 deterministic in-memory 实现；
- Task 1 已加入 v1 依赖、`Settings` 和 application package 入口；
- FastAPI、SQLAlchemy、OpenAI、AnyDoc 等依赖存在，不代表对应功能已经实现；
- 当前没有真实 LLM、真实 RAG、SQL persistence、API、文件处理、SSE 或 frontend。

不要把设计文档、依赖声明、memory adapter 或测试 fixture 误报成已实现的 production 功能。

## 五、不可破坏的产品与架构约束

### 5.1 Agent 与 Harness 权限

1. 保持五个 Agent：`idea_review`、`plan_loop`、`key_insight_check`、`working_qa`、`complete`。
2. Agent 只负责语义分类、评估、解释和声明式结构化输出。
3. Agent 不得直接调用另一个 Agent。
4. Harness/Application 独占 command 校验、routing、session phase、check round、task status、user gate、幂等、并发、持久化和公开事件。
5. Check Agent 只输出五维原始评分、理由和修订建议；Harness 必须重新计算权威 final score。
6. Check 权重固定为：research fit 20%、novelty 25%、research value 20%、testability/feasibility 20%、evidence support 15%。
7. final score 保留一位小数，总分 `>= 6.0` 即通过，不设置单项否决条件。

### 5.2 Idea、Working 与结果

1. Idea type 由 Idea Review LLM 根据用户输入判断，用户不选择 `idea_type`。
2. `range` 不得直接进入计划；必须请求用户补充或确认聚焦方向。
3. `opinion` 和 `forward` 均可因不可实现、资源不足或范围问题被拒绝或请求补充。
4. 合法 `forward` 由 Idea Review 判断并进入 Working 准备；Harness 不重新进行语义分类。
5. forward 用户已有实验材料必须进入结构化 `ForwardResearchContext`，不能把附件文本当系统指令。
6. Working QA 只能围绕当前任务回答、澄清、拒绝或确认该任务完成。
7. 实验结果必须由用户通过明确 command 记录；不得从 Agent 文本、`final_hint` 或 `ExperimentInfo` 推测结果。
8. 未经用户选择的 validation candidate 不得成为执行中任务。
9. 负面、不显著、不符合预期或动摇主张的结果必须保留并进入相应 warning/revision 流程，不得美化。
10. 模型自然语言不得被解析为 command。

### 5.3 RAG、文件与 Prompt 安全

1. `SysInput` 只含当前日期和所有 Agent 通用行为约束。
2. `RetrievalSysInput` 才包含 retrieval guidelines；只注入实际具备检索职责的 Idea Review 和 v1 Working QA。
3. Plan Loop、Key Insight Check 和 Complete 只消费已有 evidence，不注入无关检索规则。
4. `current_date` 由 Harness 按配置时区生成，客户端不能传入。
5. 文献检索、用户消息、上传文件、tool/skill 返回值均是不可信业务数据，必须进入 typed input 或隔离的 user payload，不能进入固定 instructions。
6. 不得编造题名、作者、DOI、URL、实验结果或证据结论。
7. `LiteratureRecord` 记录检索所得；`EvidenceRef` 只记录实际支撑判断的来源，并说明具体 support。
8. 外部网络在自动测试中必须 mock；没有证据与存在反对证据必须区分。

### 5.4 压缩与“傲娇”语气

1. v1 必须包含上下文压缩，但由 Harness application `context_service` 完成，不新增压缩 Agent 或第六个 Agent runner。
2. `CompactContext` 必须保留 source turn IDs、事实和未解决问题；不得创造或改写实验事实；原始 turns 永久保存在 SQL。
3. v1 必须包含克制的“傲娇”语气，但由确定性的 UI microcopy 表达，不新增语气 Agent。
4. microcopy 只用于超长输入、遗漏确定性选择和等待状态等非实质场景。
5. 科研评价、Agent action、评分、证据、拒绝理由和风险说明保持中性严谨，不得经过 microcopy 层改写。
6. 是否在 post-v1 Agent 化只是可选评估项；当前不得提前实现或承诺版本。

### 5.5 领域范围

1. v1 产品能力和 Eval 只覆盖 computer science。
2. application 层只接受配置声明的 CS domain/alias。
3. 非 CS 输入返回明确的 `unsupported-domain` refinement，不调用专业 Agent/model pipeline，不假装具备其他领域能力。

## 六、执行方法

使用现有 implementation plan，不重新撰写第二份实现计划。若当前环境提供对应 skills，优先使用 `executing-plans` 逐 Task 内联执行；不要未经用户授权创建额外开发线程或 subagent。

每个 Task 严格执行：

1. 阅读当前 Task 的目标文件、测试和依赖 Task；
2. 检查工作区和相关现有代码；
3. 先写计划指定的失败测试；
4. 运行目标测试，确认因缺少当前功能而 RED；
5. 写满足当前 Task 的最小实现；
6. 运行目标测试至 GREEN；
7. 运行受影响模块测试；
8. 运行 Python 全量回归；前端建立后同时运行前端全量 test/build；
9. 运行 `git diff --check`，检查没有 secrets、缓存、数据库、上传内容或无关文件；
10. 仅 stage 当前 Task 的明确文件，不使用 `git add .`；
11. 使用计划指定的 commit message 创建独立 commit；
12. 检查 commit 内容和干净工作区；
13. 进入下一 Task。

除非当前 Task 或已确认规格要求，否则不得：

- 顺手重构无关代码；
- 提前实现后续 Milestone；
- 新增可配置性、fallback 或抽象层；
- 修改固定 Prompt；
- 删除用户文件、历史结果或未理解的代码；
- 使用 `git reset --hard`、`git checkout --` 等破坏性命令；
- 将本地数据库、上传内容、`.env`、credentials、cache、venv 或测试产物加入 Git。

Python 环境统一使用 `uv`，不使用 `pip`、Conda 或 Poetry。若前端计划明确使用 npm，则按计划使用 npm，不自行更换包管理器。

## 七、Milestone 顺序与 gate

### Milestone A：Task 2–6

完成 v1 contracts、canonical state machine、Complete/validation/revision 和 Harness 权威规则。不引入外部 I/O。

Gate：原有 core tests 与新增 contract/harness tests 全绿。

### Milestone B：Task 7–12

完成 repository/UoW/event ports、SQLAlchemy/Alembic、乐观并发/outbox、安全文件处理、OpenAlex、project chunk retrieval 和可选 ranker。

Gate：SQLite migration、UoW、document 和 retrieval adapter tests 全绿；真实网络全部 mock。

### Milestone C：Task 13–16

完成 async typed model port、OpenAI/compatible adapters、Idea Review 两阶段 RAG、Working relevance 和 context compression。

Gate：五 Agent 全部 async structured model；demo 与 provider adapter contract tests 全绿。

### Milestone D：Task 17–21

完成完整 application orchestration、command bus、幂等、phase/version guard、durable run、retry/cancel 和重启恢复。

Gate：Idea 到 writing/validation/revision 的 application-level journeys 全绿。

### Milestone E：Task 22–26

完成 composition root、FastAPI lifecycle、project/command/view/document/export APIs、SSE 和 deterministic demo。

Gate：API、SSE、restart/idempotency tests 全绿，demo 能从空数据库 seed。

### Milestone F：Task 27–29

完成 React/Vite/TypeScript、typed API client、三栏工作台、证据面板、UI microcopy、上传、SSE 和完整用户操作。

Gate：frontend unit tests 与 build 全绿，desktop 和 narrow-screen 可完成主要命令。

### Milestone G：Task 30–32

完成五 Agent eval、Playwright E2E、accessibility、30 项验收、README、quickstart 和 release audit。

Gate：所有 Python/frontend/Eval/E2E/build/boundary/acceptance 检查通过。真实 provider smoke test 只有在有凭据的发布环境运行，并只记录 request ID，不得记录 secret。

## 八、验证规则

Python 通用验证：

```powershell
uv lock --check
uv run pytest -q -p no:cacheprovider
```

前端建立后通用验证：

```powershell
npm test -- --run
npm run build
```

Git 验证：

```powershell
git diff --check
git status --short --branch
git show --check --stat --oneline HEAD
```

以实际 command 输出为准。不得因为“代码看起来正确”、单个测试通过或另一个开发者报告成功，就声称 Task 或 Milestone 完成。

如果测试失败，先进行根因诊断，保留失败输出，修复后重新运行同一测试和完整 gate。不得通过跳过测试、放宽断言、吞掉异常或删除验收条件来制造 GREEN。

## 九、Git 与外部操作边界

允许：

- 在 `feature/full-product-v1` 中修改项目相关文件；
- 按 Task 创建本地 commit；
- 为完成计划运行必要的本地测试、build、migration 和 mock integration tests；
- 在每个 Milestone gate 更新 `docs/PROJECT_STATUS.md` 的实现状态、文件职责、测试基线和下一起点。

禁止：

- `git push`；
- merge、rebase、创建或合并 PR；
- 修改 `main`、`design/full-product` 或其他分支；
- 强制推送；
- 上传 secrets、用户文件、本地数据库、cache、venv 或测试产物；
- 未经用户许可调用会产生费用或影响外部数据的服务。

需要依赖下载或只读外部文档查询时，按环境权限流程申请；不要用不安全 workaround 绕过限制。

## 十、Milestone 汇报格式

每个 Milestone gate 通过后，向用户发送一次简洁进度更新，然后继续下一 Milestone：

```text
Milestone <A-G> 已通过

- 完成 Task：<范围>
- 新增/修改功能：<按模块列出>
- Commit：<commit 列表或范围>
- 验证：<实际命令与通过数量>
- 架构检查：<边界、Prompt、状态机、migration/build 等>
- 已知限制：<没有则写“无新增限制”>
- 下一步：Milestone <下一阶段> / 最终审计
- GitHub：未 push
```

如果 gate 未通过，报告：

```text
Milestone <A-G> 尚未通过

- 失败命令：<完整命令>
- 失败现象：<关键错误>
- 已定位根因：<证据>
- 已尝试修复：<内容>
- 当前工作区/commit：<状态>
- 是否需要用户决策：<是/否及原因>
```

不要用模糊的“基本完成”“应该可用”或“后续再测”代替证据。

## 十一、最终交付条件

只有同时满足以下条件，才能报告 v1.0 实现完成：

1. Task 2–32 全部按计划实施；
2. Milestone A–G gate 全部通过；
3. 30 项验收场景具有可追溯测试证据；
4. 五 Agent Eval 达到计划阈值；
5. Python 全量测试通过；
6. frontend tests、build、Playwright 和 accessibility 检查通过；
7. migration、restart、idempotency、SSE recovery 和 demo seed 验证通过；
8. `docs/PROJECT_STATUS.md` 与 README 反映最终真实状态；
9. `git diff --check` 通过，工作区无意外文件；
10. 所有工作都已本地 commit，但没有 push。

最终报告必须给出：commit 范围、实际测试结果、仍需凭据才能运行的真实 provider smoke test、未 push 状态和建议的人工审查重点。不要自行 push；等待用户明确授权。

现在先执行“当前环境”检查和必读文档阅读，然后从 Task 2 开始。
