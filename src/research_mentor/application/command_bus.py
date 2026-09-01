"""Transactional command dispatch with idempotency and guards."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import TypeAdapter

from research_mentor.application.allowed_commands import assert_allowed
from research_mentor.application.commands import (
    AgentCommandReceipt,
    Command,
    CommandResult,
)
from research_mentor.application.handlers import AGENT_COMMAND_TYPES, HandlerMap
from research_mentor.errors import (
    ConcurrencyConflict,
    IllegalTransitionError,
    InvariantViolationError,
    SessionNotFoundError,
)
from research_mentor.ports.repository import ProcessedCommand


_RESULT_ADAPTER = TypeAdapter(CommandResult)
_ACTIVE_RUN_STATUSES = frozenset({"queued", "running"})


class CommandBus:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        *,
        handlers: HandlerMap,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._handlers = handlers
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def dispatch(self, command: Command) -> CommandResult:
        async with self._uow_factory() as uow:
            existing = await uow.processed_commands.find(
                command.project_id, command.command_id
            )
            if existing is not None:
                return _RESULT_ADAPTER.validate_python(existing.receipt)

            project = await uow.projects.get(command.project_id)
            if project is None:
                raise SessionNotFoundError(
                    f"Project not found: {command.project_id}"
                )
            if project.version != command.expected_version:
                raise ConcurrencyConflict(command.project_id, command.expected_version)

            session = await uow.sessions.get(project.session_id)
            if session is None:
                raise SessionNotFoundError(
                    f"Session not found: {project.session_id}"
                )

            await self._assert_no_active_run(command.type, command.project_id, uow)
            assert_allowed(command.type, session)

            handler = self._handlers.get(command.type)
            if handler is None:
                raise InvariantViolationError(
                    f"No command handler registered for {command.type}"
                )
            result = await handler(command, uow, project, session)
            result = _RESULT_ADAPTER.validate_python(result)
            if command.type in AGENT_COMMAND_TYPES and not isinstance(
                result, AgentCommandReceipt
            ):
                raise InvariantViolationError(
                    f"Agent command {command.type} must return an agent receipt"
                )
            if command.type not in AGENT_COMMAND_TYPES and isinstance(
                result, AgentCommandReceipt
            ):
                raise InvariantViolationError(
                    f"Deterministic command {command.type} must return an updated view"
                )
            if isinstance(result, AgentCommandReceipt) and result.run_id == "":
                raise InvariantViolationError("Agent command receipt requires run_id")
            await uow.processed_commands.add(
                ProcessedCommand(
                    project_id=command.project_id,
                    command_id=command.command_id,
                    receipt=result.model_dump(mode="json"),
                    run_id=result.run_id
                    if isinstance(result, AgentCommandReceipt)
                    else None,
                    created_at=self._now(),
                )
            )
            return result

    @staticmethod
    async def _assert_no_active_run(
        command_type: str, project_id: str, uow: Any
    ) -> None:
        if command_type == "cancel_run":
            return
        active = await uow.runs.find_active_for_project(project_id)
        if active is not None and active.status in _ACTIVE_RUN_STATUSES:
            raise IllegalTransitionError("run in progress")
