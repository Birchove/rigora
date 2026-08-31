from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from research_mentor.domain.projects import ResearchProject


NOW = datetime(2026, 8, 31, tzinfo=UTC)


def test_research_project_requires_positive_version() -> None:
    with pytest.raises(ValidationError):
        ResearchProject(
            project_id="p1",
            title="缓存研究",
            domain="computer_science",
            session_id="s1",
            version=0,
            created_at=NOW,
            updated_at=NOW,
        )


def test_research_project_accepts_public_fields() -> None:
    project = ResearchProject(
        project_id="p1",
        title="缓存研究",
        domain="computer_science",
        session_id="s1",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )

    assert project.version == 1
