from research_mentor.harness.orchestration import (
    CompletionOrchestrator,
    IdeaReviewOrchestrator,
    PlanCheckOrchestrator,
    WorkingOrchestrator,
)
from research_mentor.harness.orchestrator import ResearchMentorOrchestrator
from research_mentor.harness.session_slices import (
    CompletionSlice,
    IdeaReviewSlice,
    PlanCheckSlice,
    WorkingSlice,
)
from research_mentor.harness.state import ResearchSession


SESSION_PAYLOAD_KEYS = {
    "session_id",
    "phase",
    "initial_input",
    "idea_review",
    "research_context",
    "refinement_code",
    "latest_plan_output",
    "active_plan",
    "latest_check",
    "check_round",
    "pending_plan_feedback",
    "pending_plan_revision_context",
    "plan_decision",
    "override_record",
    "plan_generation_mode",
    "plan_candidates",
    "candidate_override_records",
    "current_task",
    "main_experiment",
    "completed_validations",
    "latest_complete_output",
    "validation_queue",
    "writing_guidance",
    "plan_revision_records",
    "pending_plan_issue_reason",
    "pending_working_clarification",
}


def test_research_session_payload_keys_stay_flat() -> None:
    session = ResearchSession(session_id="s1")
    assert set(session.model_dump(mode="json")) == SESSION_PAYLOAD_KEYS
    assert issubclass(ResearchSession, IdeaReviewSlice)
    assert issubclass(ResearchSession, PlanCheckSlice)
    assert issubclass(ResearchSession, WorkingSlice)
    assert issubclass(ResearchSession, CompletionSlice)


def test_research_session_round_trips_slice_projections() -> None:
    session = ResearchSession(session_id="s1")
    idea = IdeaReviewSlice.model_validate(session.model_dump())
    plan = PlanCheckSlice.model_validate(session.model_dump())
    working = WorkingSlice.model_validate(session.model_dump())
    completion = CompletionSlice.model_validate(session.model_dump())
    restored = ResearchSession.model_validate(
        {
            "session_id": session.session_id,
            "phase": session.phase,
            **idea.model_dump(),
            **plan.model_dump(),
            **working.model_dump(),
            **completion.model_dump(),
        }
    )
    assert restored.model_dump(mode="json") == session.model_dump(mode="json")


def test_orchestrator_facade_composes_phase_classes() -> None:
    mro = ResearchMentorOrchestrator.__mro__
    assert IdeaReviewOrchestrator in mro
    assert PlanCheckOrchestrator in mro
    assert WorkingOrchestrator in mro
    assert CompletionOrchestrator in mro
    for name in (
        "create_session",
        "review_idea",
        "run_plan_loop",
        "run_plan",
        "run_check",
        "run_key_insight_check",
        "decide_plan",
        "continue_imperfect_plan",
        "start_working",
        "run_working_qa",
        "resume_working",
        "finish_working",
        "record_main_result",
        "record_validation_result",
        "run_complete",
        "select_validations",
        "decide_plan_revision",
    ):
        assert hasattr(ResearchMentorOrchestrator, name)
