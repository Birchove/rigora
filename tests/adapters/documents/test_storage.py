from collections.abc import AsyncIterator
import hashlib

import pytest

from research_mentor.adapters.filestore.local import LocalFileStore
from research_mentor.errors import InvalidStorageIdentifier


async def bytes_stream(content: bytes) -> AsyncIterator[bytes]:
    if content:
        yield content


@pytest.mark.asyncio
async def test_local_store_uses_only_project_and_document_ids(tmp_path) -> None:
    store = LocalFileStore(tmp_path)

    saved = await store.put("p1", "d1", bytes_stream(b"hello"))

    assert saved.path == tmp_path / "p1" / "d1" / "source.bin"
    assert saved.size_bytes == 5
    assert saved.sha256 == hashlib.sha256(b"hello").hexdigest()
    assert b"".join([part async for part in store.open(saved)]) == b"hello"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("project_id", "document_id"),
    [
        ("../escape", "d1"),
        ("p1", ".."),
        ("C:\\absolute", "d1"),
        ("p1", "/absolute"),
        ("", "d1"),
    ],
)
async def test_local_store_rejects_unsafe_ids(
    tmp_path,
    project_id: str,
    document_id: str,
) -> None:
    store = LocalFileStore(tmp_path)

    with pytest.raises(InvalidStorageIdentifier):
        await store.put(project_id, document_id, bytes_stream(b"unsafe"))


@pytest.mark.asyncio
async def test_local_store_supports_unicode_ids_and_empty_files(tmp_path) -> None:
    saved = await LocalFileStore(tmp_path).put(
        "项目一",
        "文档一",
        bytes_stream(b""),
    )

    assert saved.path == tmp_path / "项目一" / "文档一" / "source.bin"
    assert saved.size_bytes == 0
