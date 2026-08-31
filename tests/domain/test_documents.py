from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from research_mentor.domain.documents import UploadedDocument


NOW = datetime(2026, 8, 31, tzinfo=UTC)


def test_uploaded_document_requires_digest_and_size() -> None:
    document = UploadedDocument(
        document_id="d1",
        project_id="p1",
        original_name="notes.md",
        media_type="text/markdown",
        size_bytes=7,
        sha256="a" * 64,
        status="uploaded",
        created_at=NOW,
    )

    assert document.error_message is None


def test_uploaded_document_rejects_negative_size() -> None:
    with pytest.raises(ValidationError):
        UploadedDocument(
            document_id="d1",
            project_id="p1",
            original_name="notes.md",
            media_type="text/markdown",
            size_bytes=-1,
            sha256="a" * 64,
            status="uploaded",
            created_at=NOW,
        )
