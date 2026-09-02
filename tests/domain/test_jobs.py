from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from research_mentor.domain.jobs import AgentRun


NOW = datetime(2026, 8, 31, tzinfo=UTC)


def test_agent_run_supports_timeout_as_public_status() -> None:
    run = AgentRun(
        run_id="r1",
        project_id="p1",
        command_id="c1",
        agent_name="idea_review",
        status="timed_out",
        attempt=1,
        started_at=NOW,
        finished_at=NOW,
        public_message="模型调用超时",
        error_code="model_timeout",
    )

    assert run.status == "timed_out"
    assert run.config_snapshot["check_pass_score"] == 6.0
    assert run.config_snapshot["check_dimension_floors"]["evidence_support"] == 2.5


def test_agent_run_rejects_negative_attempt() -> None:
    with pytest.raises(ValidationError):
        AgentRun(
            run_id="r1",
            project_id="p1",
            command_id="c1",
            agent_name="idea_review",
            status="queued",
            attempt=-1,
        )
