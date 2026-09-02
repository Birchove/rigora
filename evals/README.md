# Agent Eval Suites

每个 `*_cases.json` 都是 versioned `EvalSuite`：`version=1.0`、`prompt_version`、`domain=computer_science`。runner 只评 schema、routing、rubric 和稳定性，不用另一个 LLM 当发布 gate。没有真实 model provider 时，`provider_mode` 固定为 `demo`，不伪造真实模型质量。

| Suite | 覆盖 |
| --- | --- |
| `idea_review_cases.json` | ≥20 条 CS 标注，覆盖 opinion/range/forward、reject/refinement、四种 forward stage、证据不足、prompt injection、用户错误自称 type |
| `plan_loop_cases.json` | low/mid/high 的 1/2/3 路径、candidate ID 唯一性、跨路径隔离、差异 profile、单选 gate、exhausted override、专家 rubric、prompt isolation |
| `key_insight_check_cases.json` | 明确通过/退回、单项低于下界不通过、6.0 通过边界、5.9 失败边界；重复采样评五维稳定性 |
| `working_qa_cases.json` | success 未确认不推进、主实验 plan issue、validation `completed+contradicts` / `failed+neutral`、低分不得硬拒 |
| `complete_cases.json` | validation relevance、duplicate candidate ID、plan revision、WritingGuidance |
| `retrieval_relevance_cases.json` | ≥20 条人工 relevance 标注，校准 lexical ranker 阈值 0.3；低分不得改回硬拒 |
| `citation_cases.json` | 可解析率与 DOI/URL/provider-ID duplicate rate |
| `demo_workflow_cases.json` | demo fixture 完整流程 success rate |

必要条件 gate 不进入 dataset，也不是通过条件。

运行：

```powershell
uv run pytest -q -p no:cacheprovider tests/evals
```
