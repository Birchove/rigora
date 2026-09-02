"""Idea review phase orchestration."""

from research_mentor.agents.idea_review.contracts import IdeaReviewInput, IdeaReviewOutput, IdeaReviewSysInput
from research_mentor.domain.research import InitialInput, ResearchContext
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.orchestration.base import OrchestratorBase
from research_mentor.harness.routing import route_idea_review
from research_mentor.harness.state import SessionEventType, SessionPhase
from research_mentor.harness.task_factory import TaskFactory


class IdeaReviewOrchestrator(OrchestratorBase):
    def review_idea(
        self,
        session_id: str,
        idea: InitialInput,
        prepared: IdeaReviewOutput | None = None,
    ) -> IdeaReviewOutput:
        session = self._load_for_phase(
            session_id,
            {SessionPhase.AWAITING_IDEA, SessionPhase.AWAITING_IDEA_REFINEMENT},
        )
        phase_before = session.phase
        supported_domains = {
            item.casefold()
            for item in (
                *self._config.supported_domains,
                *self._config.supported_domain_aliases,
            )
        }
        if idea.domain.strip().casefold() not in supported_domains:
            output = IdeaReviewOutput(
                idea_type="range",
                action="request_refinement",
                normalized_idea=idea.original_idea,
                reason="当前版本仅支持 computer science 领域。",
                next_action="请将问题限定为 computer science 研究，或使用通用 Agent。",
            )
            refinement_code = "unsupported_domain"
        elif prepared is not None:
            output = prepared.model_copy(deep=True)
            refinement_code = (
                "idea_refinement" if output.action == "request_refinement" else None
            )
        else:
            output = self._idea_review_runner.run_sync(
                IdeaReviewInput(
                    idea=idea.model_copy(deep=True),
                    sys_input=IdeaReviewSysInput(current_date=self._current_date()),
                ),
                model_profile=self._agent_model("idea_review"),
            )
            refinement_code = (
                "idea_refinement" if output.action == "request_refinement" else None
            )
        phase_after = route_idea_review(output)
        session.initial_input = idea.model_copy(deep=True)
        session.idea_review = output.model_copy(deep=True)
        session.refinement_code = refinement_code
        if output.action == "proceed_to_working":
            if output.forward_context is None:
                raise InvariantViolationError("forward working requires forward_context")
            session.research_context = ResearchContext(
                normalized_idea=output.normalized_idea,
                research_question=output.forward_context.research_question,
                forward_context=output.forward_context.model_copy(deep=True),
            )
            session.current_task = TaskFactory.from_forward_context(
                output.forward_context
            )
            session.main_experiment = (
                output.forward_context.main_result.model_copy(deep=True)
                if output.forward_context.main_result is not None
                else None
            )
            session.completed_validations = [
                item.model_copy(deep=True)
                for item in output.forward_context.completed_validations
            ]
        session.phase = phase_after
        event = self._event(
            session_id,
            SessionEventType.IDEA_REVIEWED,
            phase_before,
            phase_after,
            output.model_dump(mode="json"),
        )
        self._commit(session, event)
        return output.model_copy(deep=True)
