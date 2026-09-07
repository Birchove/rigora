"""Drop the unused validation_types lookup table.

补充实验已改为通用 name/purpose/method 结构，固定 paradigm/validation_type
分类被移除，该 lookup table 不再被任何代码读写。

Revision ID: 20260908_0007
Revises: 20260902_0006
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260908_0007"
down_revision: str | None = "20260902_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("validation_types")


def downgrade() -> None:
    op.create_table(
        "validation_types",
        sa.Column("validation_type", sa.String(100), primary_key=True),
        sa.Column("paradigm", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
