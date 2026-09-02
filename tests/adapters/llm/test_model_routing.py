from unittest.mock import AsyncMock

import pytest

from research_mentor.adapters.model.routing import RoutingModelAdapter
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.ports.model import ModelRequest


REVIEW_OUTPUT = IdeaReviewOutput(
    idea_type="opinion",
    action="reject",
    normalized_idea="无法验证的主张",
    reason="缺少可检验研究问题",
    next_action="重新定义问题",
)


def request(agent_name: str) -> ModelRequest[IdeaReviewOutput]:
    return ModelRequest(
        agent_name=agent_name,  # type: ignore[arg-type]
        model_profile="route-test",
        instructions="mentor instructions",
        user_input="<idea_review_data>{}</idea_review_data>",
        output_model=IdeaReviewOutput,
        timeout=9.0,
        trace_id="trace-routing",
    )


@pytest.mark.asyncio
async def test_routing_adapter_dispatches_by_agent() -> None:
    qwen = AsyncMock()
    qwen.generate = AsyncMock(return_value=REVIEW_OUTPUT)
    deepseek = AsyncMock()
    deepseek.generate = AsyncMock(return_value=REVIEW_OUTPUT)
    demo = AsyncMock()
    demo.generate = AsyncMock(return_value=REVIEW_OUTPUT)
    adapter = RoutingModelAdapter(
        {"idea_review": qwen, "plan_loop": deepseek},
        fallback=demo,
    )

    result = await adapter.generate(request("idea_review"))

    assert result == REVIEW_OUTPUT
    qwen.generate.assert_awaited_once()
    deepseek.generate.assert_not_called()
    demo.generate.assert_not_called()


@pytest.mark.asyncio
async def test_routing_adapter_falls_back_for_unassigned_agent() -> None:
    qwen = AsyncMock()
    qwen.generate = AsyncMock(return_value=REVIEW_OUTPUT)
    demo = AsyncMock()
    demo.generate = AsyncMock(return_value=REVIEW_OUTPUT)
    adapter = RoutingModelAdapter({"idea_review": qwen}, fallback=demo)

    await adapter.generate(request("working_qa"))

    demo.generate.assert_awaited_once()
    qwen.generate.assert_not_called()


@pytest.mark.asyncio
async def test_routing_adapter_prefers_model_profile() -> None:
    by_model = AsyncMock()
    by_model.generate = AsyncMock(return_value=REVIEW_OUTPUT)
    by_agent = AsyncMock()
    by_agent.generate = AsyncMock(return_value=REVIEW_OUTPUT)
    demo = AsyncMock()
    adapter = RoutingModelAdapter(
        {"gpt-5.6-sol": by_model, "plan_loop": by_agent},
        fallback=demo,
    )

    await adapter.generate(
        ModelRequest(
            agent_name="plan_loop",
            model_profile="gpt-5.6-sol",
            instructions="mentor instructions",
            user_input="<idea_review_data>{}</idea_review_data>",
            output_model=IdeaReviewOutput,
            timeout=9.0,
            trace_id="trace-routing",
        )
    )

    by_model.generate.assert_awaited_once()
    by_agent.generate.assert_not_called()
