"""実行管理テーブルの作成。

execution_plans / execution_results / step_results を作成する。

Revision ID: 001
Revises: None
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """実行管理テーブルを作成する。"""
    op.create_table(
        "execution_plans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_definition_id", sa.String(), nullable=False),
        sa.Column("source_definition_json", sa.Text(), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False),
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "risk_level",
            sa.String(),
            nullable=False,
            server_default="low",
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="created",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "execution_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(),
            sa.ForeignKey("execution_plans.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "errors_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "warnings_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
    )

    op.create_table(
        "step_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.String(),
            sa.ForeignKey("execution_results.id"),
            nullable=False,
        ),
        sa.Column("step_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("connector", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """実行管理テーブルを削除する。"""
    op.drop_table("step_results")
    op.drop_table("execution_results")
    op.drop_table("execution_plans")
