from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


EXPECTED_TABLES = {
    "alembic_version",
    "projects",
    "research_sessions",
    "session_events",
    "outbox_events",
    "agent_runs",
    "processed_commands",
    "conversation_turns",
    "documents",
    "document_chunks",
    "literature_records",
    "project_literature",
    "validation_types",
    "agent_outputs",
    "research_exports",
}


def run_migrations(url: str, revision: str) -> None:
    root = Path(__file__).parents[3]
    config = Config(root / "alembic.ini")
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    if revision == "base":
        command.downgrade(config, revision)
    else:
        command.upgrade(config, revision)


def table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_head_creates_v1_tables(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'test.db'}"

    run_migrations(url, "head")

    assert table_names(url) == EXPECTED_TABLES


def test_migration_downgrades_and_upgrades_again(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'cycle.db'}"

    run_migrations(url, "head")
    run_migrations(url, "base")
    assert table_names(url) == {"alembic_version"}

    run_migrations(url, "head")
    assert table_names(url) == EXPECTED_TABLES


def test_v1_named_constraints_exist(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'constraints.db'}"
    run_migrations(url, "head")
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        processed_unique = inspector.get_unique_constraints("processed_commands")
        event_unique = inspector.get_unique_constraints("session_events")
        session_checks = inspector.get_check_constraints("research_sessions")
        outbox_fks = inspector.get_foreign_keys("outbox_events")
    finally:
        engine.dispose()

    assert {item["name"] for item in processed_unique} >= {"uq_processed_command"}
    assert {item["name"] for item in event_unique} >= {"uq_session_event_sequence"}
    assert {item["name"] for item in session_checks} >= {
        "ck_research_session_version_positive"
    }
    assert {item["name"] for item in outbox_fks} >= {"fk_outbox_session_event"}
