# Working RAG 与用户控制增量设计

- 状态：用户于 2026-09-01 确认。
- 来源：仓库外 `用户新建议.md`；本文只记录经确认并与 v1 contract 对齐后的裁决。

## 1. Working RAG

Working 检索 query 必须由 `normalized_idea + research_question/current stage + current task/current experiment + question` 确定性组成，不能只检索本轮短问题。语料只来自当前项目已落库且获选的 document chunks、literature、evidence 与可追溯会话上下文。

v1 取消任何基于 rank score 的模型前硬拒。低分、empty 和 unavailable 都作为 `RetrievalDiagnostics` 传给 Working Agent；Agent 结合结构化研究上下文决定 `answer/clarify/decline`。`rag_relevance_threshold` 在 v1 中只用于评估与校准，不驱动状态转换。Task 30 使用人工相关性标注集记录 ranker 类型、score distribution 和候选阈值；在有校准证据前不增加双阈值或额外便宜模型。

## 2. 完成确认与 plan issue

Working `success` 只是完成建议：进入结果 panel 对应的 `AWAITING_RESULT_RECORD`，但 current task 仍为 `in_progress`。用户提交 `record_main_result` 或 `record_validation_result` 后，Harness 才在同一事务中确认 task completed 并进入 `COMPLETING`。用户选择“尚未完成”时使用确定性的 `resume_working` 返回 `WORKING`，不调用模型。

主实验中足以推翻或重设当前结论的问题使用 `report_plan_issue`，进入 `AWAITING_PLAN_REVISION_DECISION`。validation 的负面结论、反对预期或执行失败仍通过结构化 `ValidationResult(execution_status, impact, failure_reason)` 记录并回 Complete；不增加含义混乱的 `validationResult: bool`。

## 3. Forward、validation 与用户控制

Forward 使用 `ResearchContext.forward_context`，允许 `plan=None`，不得从已有实验反推虚假 ResearchPlan。Working 与 Complete 必须接受这一模式，并依赖 research question、task 和已记录结果工作。

Validation candidates 按 rank 排队，前端保持相同顺序；每项 panel 显示 purpose、method、expected result、priority、mentor rationale 和 addresses claims。

等待用户输入的 phase 永不由服务端超时。用户在等待阶段提交新 idea 时必须显式 `restart_research(confirm_restart=True)`，封存旧 cycle 后重新进入 Idea Review；Agent run 期间的新输入不进入冻结 request，用户需等待或 cancel 后 restart。

## 4. 已有裁决保持不变

`low/mid/high` 仍是现有 Plan/Check runner 的 1/2/3 条隔离候选路径，不增加 Agent 类型。必要条件 gate 仍因规则未定义而不实现。Context Assembler 的字段投影与 prompt isolation 规则保持不变。

## 5. 验收重点

- 短问题“那第二个方案呢”使用完整研究上下文构造 query；
- 任意有限低分均不在模型前 decline；
- success 未经结果 panel 确认不完成 task；
- forward `plan=None` 可完成 Working → result → Complete；
- validation 的 `completed+contradicts` 与 `failed+neutral` 路由不同但都保留事实；
- restart 与等待 phase 不丢失旧事件、结果或 draft。
