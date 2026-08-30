# Key Insight Check Eval

`key_insight_check_cases.json` 是 Check Agent 评分链路的最小回归集，覆盖明确通过、明确退回、单项低分不否决和四舍五入边界四种情况。

当前 Eval 验证 Harness 的确定性聚合与决策，不评价 LLM 是否能从自然语言稳定地产生合理的五维分数。接入真实 model provider 后，应另建 model-based Eval，并固定模型版本、Prompt 版本和重复采样次数。

运行：

```powershell
uv run --offline --no-sync pytest -q -p no:cacheprovider tests/evals/test_key_insight_check_eval.py
```
