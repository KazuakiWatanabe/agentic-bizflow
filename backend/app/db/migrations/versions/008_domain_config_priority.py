"""Phase 7 domain_configs に priority カラムを追加。

domain_configs テーブルに priority カラムを追加する。
ドメインの優先順位管理を実現する。

Revision ID: 008
Revises: 007
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """domain_configs に priority カラムを追加する。

    Note:
        - SQLite は ALTER TABLE ADD COLUMN に制約があるため
          batch_alter_table を使用する
    """
    with op.batch_alter_table("domain_configs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "priority",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    """domain_configs から priority カラムを削除する。"""
    with op.batch_alter_table("domain_configs") as batch_op:
        batch_op.drop_column("priority")
