"""Deterministic literature retrieval for demo mode."""

from datetime import datetime, timezone

from research_mentor.domain.evidence import LiteratureRecord


class DemoRetrievalAdapter:
    async def search(self, query: str, *, limit: int = 10) -> list[LiteratureRecord]:
        if limit <= 0:
            return []
        records = [
            LiteratureRecord(
                record_id="demo-literature-state-compression",
                provider="demo",
                provider_id="demo-state-compression",
                title="State Compression for Reliable Long-Context Recovery",
                authors=["Demo Research Group"],
                year=2026,
                source_type="paper",
                url="demo://literature/state-compression",
                summary="用于演示的固定文献记录，不代表真实检索结果。",
                relevance=f"演示查询：{query}",
                key_findings=["分层状态摘要可作为恢复稳定性的受控变量。"],
                retrieved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            ),
            LiteratureRecord(
                record_id="demo-literature-evaluation",
                provider="demo",
                provider_id="demo-evaluation",
                title="A Reproducible Evaluation Protocol for Agent Memory",
                authors=["Demo Evaluation Lab"],
                year=2026,
                source_type="paper",
                url="demo://literature/evaluation-protocol",
                summary="用于展示 evidence panel 的确定性 fixture。",
                relevance="支持重复运行、消融和错误分析设计。",
                key_findings=["固定任务集和多次运行有助于区分随机波动。"],
                retrieved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            ),
        ]
        return [item.model_copy(deep=True) for item in records[:limit]]
