"""Phase 5 Email テーブルの作成。

email_broadcasts / email_templates テーブルを作成する。

Revision ID: 006
Revises: 005
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """email_broadcasts / email_templates テーブルを作成する。"""
    op.create_table(
        "email_broadcasts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("from_address", sa.String(), nullable=False),
        sa.Column(
            "target_type",
            sa.String(),
            nullable=False,
            server_default="all",
        ),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column(
            "total_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "success_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "execution_plan_id",
            sa.String(),
            sa.ForeignKey("execution_plans.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_email_broadcasts_status", "email_broadcasts", ["status"])
    op.create_index(
        "ix_email_broadcasts_scheduled_at",
        "email_broadcasts",
        ["scheduled_at"],
    )

    op.create_table(
        "email_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """email_broadcasts / email_templates テーブルを削除する。"""
    op.drop_table("email_templates")
    op.drop_index("ix_email_broadcasts_scheduled_at", "email_broadcasts")
    op.drop_index("ix_email_broadcasts_status", "email_broadcasts")
    op.drop_table("email_broadcasts")
