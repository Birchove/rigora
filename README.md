# 傲娇导师（Research Mentor Core）

一个面向科研想法审查、方案迭代和实验过程辅导的 multi-agent 核心。

当前版本为 **v0.1**：采用 Agent-oriented modular monolith，以结构化 Pydantic contracts 连接五个 Agent，并由 deterministic Harness 独占状态流转和最终裁决。它是可安装、可测试的 Python backend core，尚不是包含 UI 和真实模型接入的完整产品。

## 核心架构

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

Agent 只完成一次结构化推理调用，不直接调用其他 Agent，也不能修改 session phase、循环次数或任务状态。

| Agent | 职责 |
|---|---|
| `idea_review` | 检索并审查用户想法，识别 `idea_type`，给出 plan、forward、clarify 或 reject 建议。 |
| `plan_loop` | 生成研究方案，或根据用户反馈和检查意见修订 `ResearchPlan`。 |
| `key_insight_check` | 评估“点睛之笔”的研究匹配度、新颖性、研究价值、可行性与证据支撑。 |
| `working_qa` | 围绕正在进行的实验提供问答与状态整理。 |
| `complete` | 基于已经记录的实验结果给出下一项验证或写作方向。 |

Harness 独占以下权限：

- routing 和状态转移；
- Check loop 次数管理；
- 确定性评分与通过判定；
- 用户确认 gate；
- task lifecycle、session 保存和状态事件记录。

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

加权结果先保留一位小数，`final_score >= 6.0` 即通过。不设置单项分数否决条件。

## 项目目录

```text
.
├── src/research_mentor/
│   ├── agents/       # 五个 Agent 的 contracts、Prompt、builder 和 runner
│   ├── domain/       # 跨 Agent 共享的领域模型
│   ├── harness/      # 状态机、routing、scoring 与 orchestrator
│   ├── ports/        # model、retrieval、repository、clock 边界
│   └── adapters/     # v0.1 的 in-memory adapters
├── tests/            # domain、Agent、Harness 与 adapter 测试
├── evals/            # Check scoring 回归样例
├── docs/design/      # Prompt、命名架构与产品设计文档
├── pyproject.toml
└── uv.lock
```

## 环境与测试

要求 Python `3.12` 和 [uv](https://docs.astral.sh/uv/)。

```powershell
uv sync --dev
uv run pytest -q -p no:cacheprovider
```

只运行 Check Agent scoring Eval：

```powershell
uv run pytest -q -p no:cacheprovider tests/evals/test_key_insight_check_eval.py
```

## 显式停点

- `AWAITING_WORKING_CONTEXT`：Harness 无法从现有输出自动构造完整的 `ExperimentTaskContext`。
- `AWAITING_RESULT_RECORD`：必须由用户记录实验结果；不能从 `ExperimentInfo` 猜测结果。
- `AWAITING_VALIDATION_SELECTION`：必须等待用户选择验证任务，不会解析 `final_hint` 自动创建任务。

## v0.1 边界

当前不包含：

- 真实 LLM provider；
- 真实 RAG/retrieval 实现；
- SQL/database adapter；
- 文件上传、解析和多模态输入；
- Web、桌面或移动端 UI。

`memory` adapters 仅用于 deterministic tests，不表示外部 provider 已经接入。

## 设计文档

- [`docs/design/prompt仓库.md`](docs/design/prompt仓库.md)：公共 Mentor Prompt 与五个 Agent Prompt。
- [`docs/design/命名架构具体版.md`](docs/design/命名架构具体版.md)：Input/Output Schema、状态和 Harness 设计。
- [`docs/design/AI+ 创新大赛.md`](docs/design/AI+%20创新大赛.md)：产品背景与早期流程设计。

若历史流程图与当前代码或结构化 Schema 存在冲突，以当前 contracts、Harness 实现和测试为准。
