"""Run async model I/O from the sync orchestrator without a second event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from contextvars import ContextVar, Token
from typing import Any, TypeVar


T = TypeVar("T")

_owner_loop: ContextVar[asyncio.AbstractEventLoop | None] = ContextVar(
    "research_mentor_owner_loop", default=None
)


def bind_owner_loop() -> Token[asyncio.AbstractEventLoop | None]:
    return _owner_loop.set(asyncio.get_running_loop())


def reset_owner_loop(token: Token[asyncio.AbstractEventLoop | None]) -> None:
    _owner_loop.reset(token)


def run_coro_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Block until *coro* finishes, using the bound owner loop when present.

    Production calls the sync orchestrator from ``asyncio.to_thread``. A nested
    ``asyncio.run()`` would create a second loop and break shared httpx/OpenAI
    clients bound to the uvicorn loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        owner = _owner_loop.get()
        if owner is not None and owner.is_running():
            return asyncio.run_coroutine_threadsafe(coro, owner).result()
        return asyncio.run(coro)
    raise RuntimeError("run_coro_sync cannot be used from a running event loop")
