from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from research_mentor.adapters.memory.repository import (
    MemoryProcessedCommandRepository,
    MemoryRepositoryPort,
)
from research_mentor.ports.documents import DocumentParserPort
from research_mentor.ports.events import PublicEventPublisherPort
from research_mentor.ports.files import FileStorePort
from research_mentor.ports.repository import (
    ExpectedVersion,
    ProcessedCommand,
    RepositoryPort,
)


PROCESSED_COMMAND = ProcessedCommand(
    project_id="p1",
    command_id="c1",
    receipt={"project_id": "p1", "version": 2},
    run_id="r1",
    created_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
)


@pytest.fixture
def repository_uow():
    commands: dict[tuple[str, str], ProcessedCommand] = {}

    def factory() -> MemoryRepositoryPort:
        return MemoryRepositoryPort(
            processed_commands=MemoryProcessedCommandRepository(commands)
        )

    return factory


@pytest.mark.asyncio
async def test_uow_finds_processed_command_by_command_id(repository_uow) -> None:
    async with repository_uow() as uow:
        await uow.processed_commands.add(PROCESSED_COMMAND)
    async with repository_uow() as uow:
        found = await uow.processed_commands.find("p1", "c1")

    assert found is not None
    assert found.receipt == PROCESSED_COMMAND.receipt
    assert found.run_id == "r1"


@pytest.mark.asyncio
async def test_uow_rolls_back_processed_command_on_error(repository_uow) -> None:
    with pytest.raises(RuntimeError):
        async with repository_uow() as uow:
            await uow.processed_commands.add(PROCESSED_COMMAND)
            raise RuntimeError("abort")

    async with repository_uow() as uow:
        assert await uow.processed_commands.find("p1", "c1") is None


def test_expected_version_rejects_zero() -> None:
    with pytest.raises(ValidationError):
        ExpectedVersion(expected_version=0)


def test_ports_use_v1_boundary_names() -> None:
    assert all(
        value is not None
        for value in (
            RepositoryPort,
            FileStorePort,
            DocumentParserPort,
            PublicEventPublisherPort,
        )
    )
