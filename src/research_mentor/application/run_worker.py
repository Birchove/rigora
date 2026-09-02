"""Durable Agent run execution with leases, retries and cooperative cancellation."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, TypeAlias
from uuid import uuid4

from research_mentor.adapters.model.errors import (
    ModelProviderRejected,
    ModelTemporarilyUnavailable,
)
from research_mentor.domain.jobs import AgentRun
from research_mentor.errors import ModelOutputInvalid
from research_mentor.harness.state import SessionEvent, SessionEventType
from research_mentor.hyperparameters import (
    RETRY_BACKOFF_CAP_SECONDS,
    RUN_LEASE_RENEWAL_SECONDS,
    RUN_LEASE_SECONDS,
    RUN_RETRY_LIMIT,
    RUN_TIMEOUT_SECONDS,
    SCHEMA_REPAIR_RETRY_LIMIT,
    WORKER_POLL_INTERVAL_SECONDS,
)
from research_mentor.ports.events import OutboxEvent


logger = logging.getLogger("research_mentor.runs")


RunHandler: TypeAlias = Callable[
    [AgentRun, dict[str, Any], list[dict[str, Any]] | None], Awaitable[Any]
]


class _RunCancelled(Exception):
    pass


class RunService:
    """Run controls used by command handlers and API composition."""

    def __init__(
        self,
        uow_factory: Callable[[], Any],
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def request_cancel(self, run_id: str) -> bool:
        async with self._uow_factory() as uow:
            return await uow.runs.request_cancel(run_id)

    async def has_active_run(self, project_id: str) -> bool:
        async with self._uow_factory() as uow:
            return await uow.runs.find_active_for_project(project_id) is not None


class AgentRunWorker:
    """Claims one queued run and advances it through the durable state machine."""

    def __init__(
        self,
        uow_factory: Callable[[], Any],
        *,
        handlers: Mapping[str, RunHandler],
        worker_id: str,
        lease_seconds: float = RUN_LEASE_SECONDS,
        lease_renewal_seconds: float = RUN_LEASE_RENEWAL_SECONDS,
        run_timeout: float = RUN_TIMEOUT_SECONDS,
        retry_limit: int = RUN_RETRY_LIMIT,
        poll_interval: float = WORKER_POLL_INTERVAL_SECONDS,
        cancel_poll_seconds: float = 0.5,
        now: Callable[[], datetime] | None = None,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        if (
            lease_seconds <= 0
            or lease_renewal_seconds <= 0
            or run_timeout <= 0
            or poll_interval <= 0
            or cancel_poll_seconds <= 0
        ):
            raise ValueError("worker durations must be positive")
        if retry_limit < 1:
            raise ValueError("retry_limit must be positive")
        self._uow_factory = uow_factory
        self._handlers = handlers
        self.worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._renewal_seconds = lease_renewal_seconds
        self._run_timeout = run_timeout
        self._retry_limit = retry_limit
        self._poll_interval = poll_interval
        self._cancel_poll_seconds = cancel_poll_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._new_id = new_id or (lambda: str(uuid4()))
        self._polling_task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._polling_task is not None and not self._polling_task.done()

    async def start(self) -> None:
        if self.is_running:
            return
        self._polling_task = asyncio.create_task(self._poll())

    async def stop(self) -> None:
        task = self._polling_task
        self._polling_task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _poll(self) -> None:
        while True:
            run_id = await self.drain_once()
            if run_id is None:
                await asyncio.sleep(self._poll_interval)

    async def drain_once(self) -> str | None:
        run = await self._claim_next()
        if run is None:
            return None
        await self._execute_claimed(run)
        return run.run_id

    async def claim(self, run_id: str) -> bool:
        now = self._now()
        async with self._uow_factory() as uow:
            run = await uow.runs.claim(
                run_id,
                worker_id=self.worker_id,
                now=now,
                lease_expires_at=now + timedelta(seconds=self._lease_seconds),
            )
        return run is not None

    async def renew_lease(self, run_id: str) -> bool:
        now = self._now()
        async with self._uow_factory() as uow:
            run = await uow.runs.renew_lease(
                run_id,
                worker_id=self.worker_id,
                now=now,
                lease_expires_at=now + timedelta(seconds=self._lease_seconds),
            )
        return run is not None

    async def confirm_cancelled(self, run_id: str) -> bool:
        async with self._uow_factory() as uow:
            run = await uow.runs.get(run_id)
            if run is None or not run.cancel_requested:
                return False
            owner = self.worker_id if run.status == "running" else ""
            return await uow.runs.finish(
                run_id,
                worker_id=owner,
                expected_version=run.row_version,
                status="cancelled",
                now=self._now(),
                public_message="运行已取消。",
                error_code="run_cancelled",
            )

    async def _claim_next(self) -> AgentRun | None:
        now = self._now()
        async with self._uow_factory() as uow:
            return await uow.runs.claim_next(
                worker_id=self.worker_id,
                now=now,
                lease_expires_at=now + timedelta(seconds=self._lease_seconds),
            )

    async def _execute_claimed(self, run: AgentRun) -> None:
        if await self._cancel_requested(run.run_id):
            await self.confirm_cancelled(run.run_id)
            return
        handler = self._handlers.get(run.agent_name)
        if handler is None:
            await self._terminal(
                run.run_id,
                "failed",
                public_message="运行无法执行。",
                error_code="run_handler_missing",
            )
            return

        logger.info(
            "run start project=%s agent=%s run=%s attempt=%s",
            run.project_id,
            run.agent_name,
            run.run_id,
            run.attempt,
        )

        renewal = asyncio.create_task(self._renew_during_call(run.run_id))
        call_task = asyncio.create_task(self._call_with_schema_repair(handler, run))
        watch_task = asyncio.create_task(self._abort_on_cancel(run.run_id, call_task))
        outcome = "succeeded"
        public_message = "运行已完成。"
        error_code: str | None = None
        try:
            async with asyncio.timeout(self._run_timeout):
                await call_task
        except _RunCancelled:
            outcome = "cancelled"
        except asyncio.CancelledError:
            if await self._cancel_requested(run.run_id):
                outcome = "cancelled"
            else:
                raise
        except TimeoutError:
            outcome = "timed_out"
            public_message = "模型调用超时，请重试。"
            error_code = "run_timeout"
        except ModelTemporarilyUnavailable as exc:
            outcome = "retry"
            public_message = str(exc)
            logger.warning(
                "model temporarily unavailable project=%s agent=%s run=%s: %s",
                run.project_id,
                run.agent_name,
                run.run_id,
                exc,
                exc_info=True,
            )
        except ModelOutputInvalid:
            outcome = "failed"
            public_message = "模型输出格式校验失败。"
            error_code = "model_output_invalid"
        except ModelProviderRejected as exc:
            outcome = "failed"
            public_message = "模型拒绝了本次请求，请检查模型名与 JSON 输出兼容性后重试。"
            error_code = "model_provider_rejected"
            logger.exception(
                "model provider rejected project=%s agent=%s run=%s: %s",
                run.project_id,
                run.agent_name,
                run.run_id,
                exc,
            )
        except Exception:
            outcome = "failed"
            public_message = "运行失败，请重试。"
            error_code = "run_failed"
            logger.exception(
                "run failed project=%s agent=%s run=%s",
                run.project_id,
                run.agent_name,
                run.run_id,
            )
        finally:
            if not call_task.done():
                call_task.cancel()
                try:
                    await call_task
                except (asyncio.CancelledError, _RunCancelled, Exception):
                    pass
            watch_task.cancel()
            renewal.cancel()
            for background in (watch_task, renewal):
                try:
                    await background
                except asyncio.CancelledError:
                    pass

        logger.info(
            "run %s project=%s agent=%s run=%s%s",
            outcome,
            run.project_id,
            run.agent_name,
            run.run_id,
            f" error={error_code}" if error_code else "",
        )

        if outcome == "cancelled" or await self._cancel_requested(run.run_id):
            await self.confirm_cancelled(run.run_id)
        elif outcome == "retry":
            await self._retry_or_fail(run.run_id)
        else:
            await self._terminal(
                run.run_id,
                outcome,
                public_message=public_message,
                error_code=error_code,
            )

    async def _call_with_schema_repair(
        self, handler: RunHandler, run: AgentRun
    ) -> Any:
        repair_errors: list[dict[str, Any]] | None = None
        for repair_count in range(SCHEMA_REPAIR_RETRY_LIMIT + 1):
            if await self._cancel_requested(run.run_id):
                raise _RunCancelled
            try:
                return await handler(
                    run.model_copy(deep=True),
                    deepcopy(run.input_snapshot),
                    repair_errors,
                )
            except ModelOutputInvalid as exc:
                if repair_count == SCHEMA_REPAIR_RETRY_LIMIT:
                    raise
                repair_errors = self._minimal_schema_errors(exc.errors)
            if await self._cancel_requested(run.run_id):
                raise _RunCancelled
        raise AssertionError("unreachable")

    async def _abort_on_cancel(
        self, run_id: str, call_task: asyncio.Task[Any]
    ) -> None:
        while not call_task.done():
            await asyncio.sleep(self._cancel_poll_seconds)
            if call_task.done():
                return
            if await self._cancel_requested(run_id):
                call_task.cancel()
                return

    async def _renew_during_call(self, run_id: str) -> None:
        while True:
            await asyncio.sleep(self._renewal_seconds)
            if not await self.renew_lease(run_id):
                return

    async def _cancel_requested(self, run_id: str) -> bool:
        async with self._uow_factory() as uow:
            run = await uow.runs.get(run_id)
        return run is None or run.cancel_requested or run.status != "running"

    async def _terminal(
        self,
        run_id: str,
        status: str,
        *,
        public_message: str,
        error_code: str | None,
    ) -> bool:
        async with self._uow_factory() as uow:
            run = await uow.runs.get(run_id)
            if run is None or run.status != "running":
                return False
            finished = await uow.runs.finish(
                run_id,
                worker_id=self.worker_id,
                expected_version=run.row_version,
                status=status,
                now=self._now(),
                public_message=public_message,
                error_code=error_code,
            )
            if not finished or status not in {"failed", "timed_out"}:
                return finished
            project = await uow.projects.get(run.project_id)
            if project is None:
                return finished
            session = await uow.sessions.get(project.session_id)
            if session is None:
                return finished
            event_id = self._new_id()
            occurred_at = self._now()
            event = SessionEvent(
                event_id=event_id,
                session_id=session.session_id,
                event_type=SessionEventType.RUN_FAILED,
                phase_before=session.phase,
                phase_after=session.phase,
                payload={
                    "run_id": run_id,
                    "status": status,
                    "error_code": error_code,
                    "public_message": public_message,
                },
                occurred_at=occurred_at.isoformat(),
            )
            await uow.events.append(event)
            await uow.outbox.append(
                OutboxEvent(
                    outbox_id=self._new_id(),
                    session_event_id=event_id,
                    project_id=run.project_id,
                    topic="run.failed",
                    payload=event.payload,
                    created_at=occurred_at,
                )
            )
            return True

    async def _retry_or_fail(self, run_id: str) -> None:
        exhausted = False
        async with self._uow_factory() as uow:
            run = await uow.runs.get(run_id)
            if run is None or run.status != "running":
                return
            if run.attempt >= self._retry_limit:
                exhausted = True
            else:
                delay = min(2**run.attempt, RETRY_BACKOFF_CAP_SECONDS)
                await uow.runs.requeue_retry(
                    run_id,
                    worker_id=self.worker_id,
                    expected_version=run.row_version,
                    available_at=self._now() + timedelta(seconds=delay),
                    public_message="模型服务暂时不可用，已安排重试。",
                    error_code="model_temporarily_unavailable",
                )
        if exhausted:
            await self._terminal(
                run_id,
                "failed",
                public_message="模型服务暂时不可用，重试次数已用尽。",
                error_code="model_temporarily_unavailable",
            )

    @staticmethod
    def _minimal_schema_errors(
        errors: list[dict[str, object]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "loc": list(error.get("loc", ())),
                "msg": str(error.get("msg", "invalid output")),
            }
            for error in errors[:10]
        ]
