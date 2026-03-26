"""Phase 4 テーブルの作成。

approval_requests / processed_idempotency_keys /
execution_audit_logs / worker_task_logs を作成する。

Revision ID: 003
Revises: 002
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Phase 4 テーブルを作成する。"""
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(),
            sa.ForeignKey("execution_plans.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
    )

    op.create_table(
        "processed_idempotency_keys",
        sa.Column("idempotency_key", sa.String(), primary_key=True),
        sa.Column("step_id", sa.String(), nullable=False),
        sa.Column("plan_id", sa.String(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "execution_audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("execution_id", sa.String(), nullable=True),
        sa.Column("plan_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_audit_logs_execution_id", "execution_audit_logs", ["execution_id"]
    )
    op.create_index("ix_audit_logs_plan_id", "execution_audit_logs", ["plan_id"])
    op.create_index("ix_audit_logs_action", "execution_audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "execution_audit_logs", ["created_at"])

    op.create_table(
        "worker_task_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_name", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
    )


def downgrade() -> None:
    """Phase 4 テーブルを削除する。"""
    op.drop_table("worker_task_logs")
    op.drop_table("execution_audit_logs")
    op.drop_table("processed_idempotency_keys")
    op.drop_table("approval_requests")
