"""Startup recovery for abandoned durable runs."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any


class RunRecovery:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def requeue_expired(self) -> tuple[str, ...]:
        async with self._uow_factory() as uow:
            return await uow.runs.requeue_expired(now=self._now())
