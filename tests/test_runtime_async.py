import asyncio

import httpx
import pytest

from research_mentor.runtime_async import bind_owner_loop, reset_owner_loop, run_coro_sync


def test_run_coro_sync_without_owner_loop() -> None:
    async def work() -> int:
        return 3

    assert run_coro_sync(work()) == 3


@pytest.mark.asyncio
async def test_run_coro_sync_reuses_owner_loop_from_worker_thread() -> None:
    owner = asyncio.get_running_loop()
    seen: list[int] = []

    async def work() -> str:
        seen.append(id(asyncio.get_running_loop()))
        return "ok"

    token = bind_owner_loop()
    try:
        result = await asyncio.to_thread(lambda: run_coro_sync(work()))
    finally:
        reset_owner_loop(token)

    assert result == "ok"
    assert seen == [id(owner)]


@pytest.mark.asyncio
async def test_shared_httpx_client_survives_threaded_orchestrator_call(respx_mock) -> None:
    respx_mock.post("https://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    client = httpx.AsyncClient()

    async def call() -> dict[str, bool]:
        response = await client.post("https://provider.test/v1/chat/completions")
        return response.json()

    token = bind_owner_loop()
    try:
        payload = await asyncio.to_thread(lambda: run_coro_sync(call()))
    finally:
        reset_owner_loop(token)
        await client.aclose()

    assert payload == {"ok": True}
