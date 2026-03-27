"""Phase 7 contacts テーブルの作成。

contacts / contact_channels テーブルを作成する。
チャネル非依存の連絡先管理を実現する。

Revision ID: 007
Revises: 006
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """contacts / contact_channels テーブルを作成する。"""
    op.create_table(
        "contacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            sa.Text(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "contact_channels",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "contact_id",
            sa.String(),
            sa.ForeignKey("contacts.id"),
            nullable=False,
        ),
        sa.Column("channel_type", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "channel_type",
            "external_id",
            name="uq_contact_channel_type_external_id",
        ),
    )
    op.create_index(
        "ix_contact_channels_contact_id",
        "contact_channels",
        ["contact_id"],
    )


def downgrade() -> None:
    """contacts / contact_channels テーブルを削除する。"""
    op.drop_index("ix_contact_channels_contact_id", "contact_channels")
    op.drop_table("contact_channels")
    op.drop_table("contacts")
