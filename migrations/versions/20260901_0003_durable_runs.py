"""Add durable worker metadata to agent runs.

Revision ID: 20260901_0003
Revises: 20260901_0002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260901_0003"
down_revision: str | None = "20260901_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch:
        batch.add_column(sa.Column("available_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("lease_owner", sa.String(100)))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
        batch.add_column(
            sa.Column("row_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(
            sa.Column(
                "cancel_requested",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(
            sa.Column("input_snapshot", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch:
        for name in (
            "input_snapshot",
            "cancel_requested",
            "row_version",
            "lease_expires_at",
            "lease_owner",
            "available_at",
        ):
            batch.drop_column(name)
