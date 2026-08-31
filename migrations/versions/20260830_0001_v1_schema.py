"""Create the v1 persistence schema."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260830_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("project_id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("domain", sa.String(200), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "research_sessions",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(100), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "version >= 1", name="research_session_version_positive"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "session_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("phase_before", sa.String(100)),
        sa.Column("phase_after", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["research_sessions.session_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "project_id", "sequence", name="uq_session_event_sequence"
        ),
    )
    op.create_table(
        "outbox_events",
        sa.Column("outbox_id", sa.String(36), primary_key=True),
        sa.Column("session_event_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("publish_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.ForeignKeyConstraint(
            ["session_event_id"],
            ["session_events.event_id"],
            name="fk_outbox_session_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "agent_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("command_id", sa.String(100), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("public_message", sa.Text()),
        sa.Column("error_code", sa.String(100)),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "processed_commands",
        sa.Column("processed_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("command_id", sa.String(100), nullable=False),
        sa.Column("receipt", sa.JSON(), nullable=False),
        sa.Column("run_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"]),
        sa.UniqueConstraint(
            "project_id", "command_id", name="uq_processed_command"
        ),
    )
    op.create_table(
        "conversation_turns",
        sa.Column("turn_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent_name", sa.String(100)),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["research_sessions.session_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("original_name", sa.String(1000), nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.JSON(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.document_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "literature_records",
        sa.Column("record_id", sa.String(100), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("provider_id", sa.String(500), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "project_literature",
        sa.Column("project_id", sa.String(36), primary_key=True),
        sa.Column("record_id", sa.String(100), primary_key=True),
        sa.Column("query_id", sa.String(100)),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["record_id"],
            ["literature_records.record_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "validation_types",
        sa.Column("validation_type", sa.String(100), primary_key=True),
        sa.Column("paradigm", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "agent_outputs",
        sa.Column("output_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("structured_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.run_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "research_exports",
        sa.Column("export_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("export_format", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("storage_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    for table_name in (
        "research_exports",
        "agent_outputs",
        "validation_types",
        "project_literature",
        "literature_records",
        "document_chunks",
        "documents",
        "conversation_turns",
        "processed_commands",
        "agent_runs",
        "outbox_events",
        "session_events",
        "research_sessions",
        "projects",
    ):
        op.drop_table(table_name)
