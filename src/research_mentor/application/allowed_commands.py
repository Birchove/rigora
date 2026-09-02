"""Server-authoritative phase to command mapping."""

from research_mentor.errors import IllegalTransitionError
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import ResearchSession


_CONTROLS = ("cancel_run", "restart_research", "archive_project")
_PHASE_COMMANDS: dict[SessionPhase, tuple[str, ...]] = {
    SessionPhase.AWAITING_IDEA: ("submit_idea", *_CONTROLS),
    SessionPhase.AWAITING_IDEA_REFINEMENT: ("submit_refinement", *_CONTROLS),
    SessionPhase.PLANNING: ("run_plan", *_CONTROLS),
    SessionPhase.CHECKING_KEY_INSIGHT: ("run_check", *_CONTROLS),
    SessionPhase.AWAITING_PLAN_DECISION: ("decide_plan", *_CONTROLS),
    SessionPhase.AWAITING_WORKING_CONTEXT: _CONTROLS,
    SessionPhase.WORKING: ("send_working_message", "finish_working", *_CONTROLS),
    SessionPhase.COMPLETING: ("run_complete", *_CONTROLS),
    SessionPhase.AWAITING_VALIDATION_SELECTION: (
        "select_validations",
        *_CONTROLS,
    ),
    SessionPhase.AWAITING_PLAN_REVISION_DECISION: (
        "decide_plan_revision",
        *_CONTROLS,
    ),
    SessionPhase.CHECK_LOOP_EXHAUSTED: ("decide_plan", *_CONTROLS),
    SessionPhase.COMPLETED: ("restart_research", "archive_project"),
    SessionPhase.REJECTED: ("restart_research", "archive_project"),
}


def allowed_commands(session: ResearchSession) -> tuple[str, ...]:
    if session.phase is SessionPhase.AWAITING_RESULT_RECORD:
        record_command = None
        if session.current_task is not None:
            record_command = (
                "record_main_result"
                if session.current_task.task_kind == "main"
                else "record_validation_result"
            )
        primary = (record_command,) if record_command is not None else ()
        return (*primary, "resume_working", *_CONTROLS)
    return _PHASE_COMMANDS[session.phase]


def assert_allowed(command_type: str, session: ResearchSession) -> None:
    if command_type not in allowed_commands(session):
        raise IllegalTransitionError(
            f"phase {session.phase} does not allow command {command_type}"
        )
