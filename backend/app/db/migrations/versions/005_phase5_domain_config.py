"""Phase 5 ドメイン設定テーブルの作成。

domain_configs テーブルを作成する。

Revision ID: 005
Revises: 004
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """domain_configs テーブルを作成する。"""
    op.create_table(
        "domain_configs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("domain", sa.String(), unique=True, nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "config_json",
            sa.Text(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """domain_configs テーブルを削除する。"""
    op.drop_table("domain_configs")
