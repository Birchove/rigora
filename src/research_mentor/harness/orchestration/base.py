"""Shared load/commit/event helpers for phase orchestrators."""

from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import JsonValue

from research_mentor.agents.complete.runner import CompleteRunner
from research_mentor.agents.idea_review.runner import IdeaReviewRunner
from research_mentor.agents.key_insight_check.runner import KeyInsightCheckRunner
from research_mentor.agents.plan_loop.runner import PlanLoopRunner
from research_mentor.agents.working_qa.runner import WorkingQARunner
from research_mentor.config import HarnessConfig
from research_mentor.errors import IllegalTransitionError, InvariantViolationError
from research_mentor.harness.state import ResearchSession, SessionEvent, SessionEventType, SessionPhase
from research_mentor.ports.clock import ClockPort
from research_mentor.ports.repository import ResearchSessionRepository


class OrchestratorBase:
    def __init__(
        self,
        *,
        repository: ResearchSessionRepository,
        clock: ClockPort,
        idea_review_runner: IdeaReviewRunner,
        plan_loop_runner: PlanLoopRunner,
        key_insight_check_runner: KeyInsightCheckRunner,
        working_qa_runner: WorkingQARunner,
        complete_runner: CompleteRunner,
        config: HarnessConfig,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._idea_review_runner = idea_review_runner
        self._plan_loop_runner = plan_loop_runner
        self._key_insight_check_runner = key_insight_check_runner
        self._working_qa_runner = working_qa_runner
        self._complete_runner = complete_runner
        self._config = config

    def _agent_model(self, agent_name: str) -> str:
        return self._config.model_for_agent(agent_name)

    def _load_for_phase(
        self,
        session_id: str,
        allowed: set[SessionPhase],
    ) -> ResearchSession:
        session = self._repository.get(session_id).model_copy(deep=True)
        if session.phase not in allowed:
            raise IllegalTransitionError(
                f"phase {session.phase} does not allow this command"
            )
        return session

    def _now(self) -> datetime:
        now = self._clock.now()
        if now.utcoffset() is None:
            raise InvariantViolationError("ClockPort must return a timezone-aware datetime")
        return now

    def _current_date(self) -> date:
        return self._now().astimezone(ZoneInfo("Asia/Shanghai")).date()

    def _event(
        self,
        session_id: str,
        event_type: SessionEventType,
        phase_before: SessionPhase | None,
        phase_after: SessionPhase,
        payload: dict[str, JsonValue],
    ) -> SessionEvent:
        return SessionEvent(
            event_id=str(uuid4()),
            session_id=session_id,
            event_type=event_type,
            phase_before=phase_before,
            phase_after=phase_after,
            payload=payload,
            occurred_at=self._now().isoformat(),
        )

    def _commit(self, session: ResearchSession, event: SessionEvent) -> None:
        self._repository.commit(session, event)

    def create_session(self, session_id: str) -> ResearchSession:
        session = ResearchSession(session_id=session_id)
        event = self._event(
            session_id,
            SessionEventType.SESSION_CREATED,
            None,
            session.phase,
            {},
        )
        self._repository.add(session, event)
        return session.model_copy(deep=True)
