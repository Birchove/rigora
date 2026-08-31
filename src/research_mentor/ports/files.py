"""Binary file storage boundary."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field


class StoredFile(BaseModel):
    project_id: str
    document_id: str
    path: Path
    size_bytes: int = Field(ge=0)
    sha256: str


class FileStorePort(Protocol):
    async def put(
        self,
        project_id: str,
        document_id: str,
        content: AsyncIterator[bytes],
    ) -> StoredFile: ...

    async def open(self, stored_file: StoredFile) -> AsyncIterator[bytes]: ...

    async def remove(self, stored_file: StoredFile) -> None: ...
