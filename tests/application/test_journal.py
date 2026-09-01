from datetime import datetime, timezone

from research_mentor.application.journal import JournalRenderer, ResearchJournal
from research_mentor.domain.evidence import LiteratureRecord
from research_mentor.domain.projects import ResearchProject
from research_mentor.domain.research import InitialInput


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_journal_json_is_authoritative_and_markdown_is_deterministic():
    journal = ResearchJournal(
        project=ResearchProject(project_id="p1", title="缓存研究", domain="computer_science",
                                session_id="s1", version=1, created_at=NOW, updated_at=NOW),
        initial_input=InitialInput(original_idea="比较缓存恢复", domain="computer science"),
        literature=[LiteratureRecord(title="Reliable Cache Recovery", source_type="paper",
                    summary="OpenAlex 收录的恢复研究。", relevance="直接相关", provider="OpenAlex")],
        generated_at=NOW,
    )
    restored = ResearchJournal.model_validate_json(journal.model_dump_json())
    markdown = JournalRenderer().to_markdown(restored)
    assert markdown == JournalRenderer().to_markdown(restored)
    assert "## 研究想法" in markdown
    assert "## 证据" in markdown and "OpenAlex" in markdown
    assert "## Plan / Check 争论" in markdown
    assert "## 实验结果" in markdown
    assert "## Validation" in markdown
    assert "## WritingGuidance" in markdown
    assert "EvidenceRef" not in markdown
