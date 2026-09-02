"""Run Harness orchestration against a session snapshot and persist the result."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from research_mentor.adapters.memory.clock import FixedClock
from research_mentor.agents.complete.runner import CompleteRunner
from research_mentor.agents.idea_review.runner import IdeaReviewRunner
from research_mentor.agents.key_insight_check.runner import KeyInsightCheckRunner
from research_mentor.agents.plan_loop.runner import PlanLoopRunner
from research_mentor.agents.working_qa.runner import WorkingQARunner
from research_mentor.application.event_stream import _INTERNAL_TYPE_MAP
from research_mentor.config import HarnessConfig, Settings
from research_mentor.errors import SessionNotFoundError
from research_mentor.harness.orchestrator import ResearchMentorOrchestrator
from research_mentor.harness.state import ResearchSession, SessionEvent
from research_mentor.ports.events import OutboxEvent
from research_mentor.ports.model import StructuredModelPort


class SnapshotSessionRepository:
    def __init__(self, session: ResearchSession) -> None:
        self.session = session.model_copy(deep=True)
        self.events: list[SessionEvent] = []

    def get(self, session_id: str) -> ResearchSession:
        if session_id != self.session.session_id:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return self.session.model_copy(deep=True)

    def commit(self, session: ResearchSession, event: SessionEvent) -> None:
        if event.session_id != session.session_id:
            raise SessionNotFoundError(session.session_id)
        self.session = session.model_copy(deep=True)
        self.events.append(event.model_copy(deep=True))


def harness_config(settings: Settings) -> HarnessConfig:
    return HarnessConfig(
        max_check_rounds=settings.max_check_rounds,
        pass_score=settings.check_pass_score,
        rag_relevance_threshold=settings.rag_relevance_threshold,
        supported_domains=settings.supported_domains,
        supported_domain_aliases=settings.supported_domain_aliases,
    )


def build_orchestrator(
    repository: SnapshotSessionRepository,
    *,
    model: StructuredModelPort,
    settings: Settings,
    now: datetime | None = None,
) -> ResearchMentorOrchestrator:
    clock_now = now or datetime.now(timezone.utc)
    return ResearchMentorOrchestrator(
        repository=repository,
        clock=FixedClock(clock_now),
        idea_review_runner=IdeaReviewRunner(model),
        plan_loop_runner=PlanLoopRunner(model),
        key_insight_check_runner=KeyInsightCheckRunner(model),
        working_qa_runner=WorkingQARunner(model),
        complete_runner=CompleteRunner(model),
        config=harness_config(settings),
    )


async def persist_events(
    uow: Any,
    *,
    project_id: str,
    events: list[SessionEvent],
    now: datetime,
    new_id: Callable[[], str],
) -> None:
    for event in events:
        await uow.events.append(event)
        topic = _INTERNAL_TYPE_MAP.get(event.event_type.value, event.event_type.value)
        await uow.outbox.append(
            OutboxEvent(
                outbox_id=new_id(),
                session_event_id=event.event_id,
                project_id=project_id,
                topic=topic,
                payload=event.payload,
                created_at=now,
            )
        )


async def apply_orchestrator(
    uow: Any,
    *,
    project_id: str,
    session: ResearchSession,
    model: StructuredModelPort,
    settings: Settings,
    mutate: Callable[[ResearchMentorOrchestrator, str], None],
    now: datetime | None = None,
    new_id: Callable[[], str] | None = None,
) -> ResearchSession:
    occurred_at = now or datetime.now(timezone.utc)
    make_id = new_id or (lambda: str(uuid4()))
    expected_version = await uow.sessions.row_version(session.session_id)
    repository = SnapshotSessionRepository(session)
    orchestrator = build_orchestrator(
        repository, model=model, settings=settings, now=occurred_at
    )

    def run() -> tuple[ResearchSession, list[SessionEvent]]:
        mutate(orchestrator, session.session_id)
        return repository.session, list(repository.events)

    updated, events = await asyncio.to_thread(run)
    await uow.sessions.save(updated, expected_version=expected_version)
    await persist_events(
        uow,
        project_id=project_id,
        events=events,
        now=occurred_at,
        new_id=make_id,
    )
    return updated
