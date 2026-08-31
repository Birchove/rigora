from datetime import datetime, tzinfo, timedelta
from zoneinfo import ZoneInfo

import pytest

from research_mentor.adapters.memory.clock import FixedClock
from research_mentor.adapters.memory.model import MemoryModelAdapter
from research_mentor.adapters.memory.retrieval import MemoryLiteratureSearchAdapter
from research_mentor.domain.evidence import LiteratureRecord
from research_mentor.domain.research import InitialInput
from research_mentor.errors import InvariantViolationError, ModelOutputInvalid, PortExecutionError
from research_mentor.ports.model import ModelRequest


def model_request(agent_name="idea_review") -> ModelRequest[InitialInput]:
    return ModelRequest(
        agent_name=agent_name,
        model_profile="test",
        instructions="instructions",
        user_input="data",
        output_model=InitialInput,
        timeout=10.0,
        trace_id="test",
    )


def test_fixed_clock_is_timezone_aware_and_stable() -> None:
    value = datetime(2026, 8, 29, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    clock = FixedClock(value)
    assert clock.now() == value
    assert clock.now() == value


def test_fixed_clock_rejects_naive_datetime() -> None:
    with pytest.raises(InvariantViolationError):
        FixedClock(datetime(2026, 8, 29, 10, 30))


class _NoOffset(tzinfo):
    def utcoffset(self, dt: datetime | None) -> timedelta | None:
        return None


def test_fixed_clock_rejects_datetime_with_missing_offset() -> None:
    with pytest.raises(InvariantViolationError):
        FixedClock(datetime(2026, 8, 29, 10, 30, tzinfo=_NoOffset()))


@pytest.mark.asyncio
async def test_memory_model_is_fifo_per_agent_and_validates_output() -> None:
    model = MemoryModelAdapter()
    model.enqueue("idea_review", {"original_idea": "first", "domain": "CS"})
    model.enqueue("idea_review", {"original_idea": "second", "domain": "CS"})
    first = await model.generate(model_request())
    second = await model.generate(model_request())
    assert first.original_idea == "first"
    assert second.original_idea == "second"
    assert isinstance(first, InitialInput)


@pytest.mark.asyncio
async def test_memory_model_rejects_empty_queue() -> None:
    with pytest.raises(PortExecutionError):
        await MemoryModelAdapter().generate(model_request("complete"))


@pytest.mark.asyncio
async def test_memory_model_queues_are_isolated_by_agent() -> None:
    model = MemoryModelAdapter()
    model.enqueue("idea_review", {"original_idea": "idea", "domain": "CS"})
    with pytest.raises(PortExecutionError):
        await model.generate(model_request("complete"))


@pytest.mark.asyncio
async def test_memory_model_wraps_output_validation_error() -> None:
    model = MemoryModelAdapter()
    model.enqueue("idea_review", {"domain": "CS"})
    with pytest.raises(ModelOutputInvalid):
        await model.generate(model_request())


def test_memory_retrieval_returns_copy_and_unknown_query_is_empty() -> None:
    adapter = MemoryLiteratureSearchAdapter()
    record = LiteratureRecord(title="Paper", source_type="paper", summary="Summary", relevance="Relevant")
    adapter.set_results("memory", [record])
    result = adapter.search("memory", limit=5)
    result.clear()
    assert len(adapter.search("memory", limit=5)) == 1
    assert adapter.search("unknown", limit=5) == []


def test_memory_retrieval_applies_limit_and_deep_copies_models() -> None:
    adapter = MemoryLiteratureSearchAdapter()
    records = [
        LiteratureRecord(title="Paper 1", source_type="paper", summary="Summary", relevance="Relevant", key_findings=["one"]),
        LiteratureRecord(title="Paper 2", source_type="paper", summary="Summary", relevance="Relevant"),
    ]
    adapter.set_results("memory", records)
    result = adapter.search("memory", limit=1)
    result[0].key_findings.append("mutated")
    records[0].key_findings.append("source-mutated")
    fresh = adapter.search("memory", limit=5)
    assert len(fresh) == 2
    assert fresh[0].key_findings == ["one"]


def test_memory_retrieval_nonpositive_limit_is_empty() -> None:
    adapter = MemoryLiteratureSearchAdapter()
    record = LiteratureRecord(title="Paper", source_type="paper", summary="Summary", relevance="Relevant")
    adapter.set_results("memory", [record])
    assert adapter.search("memory", limit=0) == []
    assert adapter.search("memory", limit=-1) == []
