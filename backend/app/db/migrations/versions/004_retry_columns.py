"""scenario_enrollments に retry カラムを追加。

retry_count / max_retries を追加する。

Revision ID: 004
Revises: 003
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """retry カラムを追加する。"""
    with op.batch_alter_table("scenario_enrollments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "retry_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "max_retries",
                sa.Integer(),
                nullable=False,
                server_default="3",
            )
        )


def downgrade() -> None:
    """retry カラムを削除する。"""
    with op.batch_alter_table("scenario_enrollments") as batch_op:
        batch_op.drop_column("max_retries")
        batch_op.drop_column("retry_count")
