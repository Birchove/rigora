import pytest

from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.errors import ConcurrencyConflict
from research_mentor.harness.state import SessionPhase


@pytest.mark.asyncio
async def test_stale_session_update_raises_conflict(
    sql_context,
    updated_session,
) -> None:
    async with SqlUnitOfWork(sql_context) as first:
        await first.sessions.save(updated_session, expected_version=1)

    stale = updated_session.model_copy(update={"phase": SessionPhase.COMPLETED})
    with pytest.raises(ConcurrencyConflict) as error:
        async with SqlUnitOfWork(sql_context) as second:
            await second.sessions.save(stale, expected_version=1)

    assert error.value.resource_id == "s1"
    assert error.value.expected_version == 1
