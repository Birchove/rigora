"""Mappings between domain records and SQLAlchemy rows."""

from datetime import datetime

from research_mentor.adapters.sql.models import (
    AgentOutputRow,
    OutboxEventRow,
    SessionEventRow,
)
from research_mentor.harness.state import ResearchSession, SessionEvent
from research_mentor.ports.events import OutboxEvent
from research_mentor.ports.repository import AgentOutputRecord


def session_payload(session: ResearchSession) -> dict[str, object]:
    return session.model_dump(mode="json")


def session_from_payload(payload: dict[str, object]) -> ResearchSession:
    return ResearchSession.model_validate(payload)


def event_to_row(
    event: SessionEvent,
    *,
    project_id: str,
    sequence: int,
) -> SessionEventRow:
    return SessionEventRow(
        event_id=event.event_id,
        project_id=project_id,
        session_id=event.session_id,
        sequence=sequence,
        event_type=event.event_type.value,
        phase_before=event.phase_before.value if event.phase_before else None,
        phase_after=event.phase_after.value,
        payload=event.payload,
        occurred_at=datetime.fromisoformat(event.occurred_at),
    )


def outbox_to_row(event: OutboxEvent) -> OutboxEventRow:
    return OutboxEventRow(
        outbox_id=event.outbox_id,
        session_event_id=event.session_event_id,
        project_id=event.project_id,
        topic=event.topic,
        payload=event.payload,
        created_at=event.created_at,
        published_at=event.published_at,
        publish_attempts=0,
    )


def agent_output_to_row(output: AgentOutputRecord) -> AgentOutputRow:
    return AgentOutputRow(
        output_id=output.output_id,
        run_id=output.run_id,
        project_id=output.project_id,
        agent_name=output.agent_name,
        prompt_version=output.prompt_version,
        session_version=output.session_version,
        structured_payload=output.structured_payload,
        created_at=output.created_at,
    )
