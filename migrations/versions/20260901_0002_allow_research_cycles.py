"""Allow a project to retain more than one research session.

Revision ID: 20260901_0002
Revises: 20260830_0001
"""

from alembic import op


revision = "20260901_0002"
down_revision = "20260830_0001"
branch_labels = None
depends_on = None

_NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    with op.batch_alter_table(
        "research_sessions", naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_research_sessions_project_id", type_="unique"
        )


def downgrade() -> None:
    with op.batch_alter_table("research_sessions") as batch_op:
        batch_op.create_unique_constraint(
            "uq_research_sessions_project_id", ["project_id"]
        )
