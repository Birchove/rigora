"""Local binary store with fixed, traversal-safe paths."""

from collections.abc import AsyncIterator
import hashlib
from pathlib import Path

from research_mentor.errors import InvalidStorageIdentifier
from research_mentor.ports.files import StoredFile


def _validate_identifier(value: str) -> None:
    if (
        not value
        or value in {".", ".."}
        or any(not (character.isalnum() or character in {"-", "_"}) for character in value)
    ):
        raise InvalidStorageIdentifier(f"Unsafe storage identifier: {value!r}")


class LocalFileStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, project_id: str, document_id: str) -> Path:
        _validate_identifier(project_id)
        _validate_identifier(document_id)
        path = (self._root / project_id / document_id / "source.bin").resolve()
        if self._root not in path.parents:
            raise InvalidStorageIdentifier("Storage path escaped configured root")
        return path

    async def put(
        self,
        project_id: str,
        document_id: str,
        content: AsyncIterator[bytes],
    ) -> StoredFile:
        path = self._path(project_id, document_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with path.open("wb") as stream:
                async for chunk in content:
                    stream.write(chunk)
                    digest.update(chunk)
                    size_bytes += len(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return StoredFile(
            project_id=project_id,
            document_id=document_id,
            path=path,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
        )

    async def open(self, stored_file: StoredFile) -> AsyncIterator[bytes]:
        path = self._verified_path(stored_file)
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                yield chunk

    async def remove(self, stored_file: StoredFile) -> None:
        self._verified_path(stored_file).unlink(missing_ok=True)

    def _verified_path(self, stored_file: StoredFile) -> Path:
        expected = self._path(stored_file.project_id, stored_file.document_id)
        if stored_file.path.resolve() != expected:
            raise InvalidStorageIdentifier("Stored file path does not match its IDs")
        return expected
