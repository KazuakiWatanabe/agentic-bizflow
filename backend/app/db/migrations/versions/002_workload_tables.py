"""workload ドメインテーブルの作成。

scenarios / scenario_steps / scenario_enrollments /
broadcasts / reminders / reminder_steps / reminder_enrollments /
reminder_deliveries / tags / tag_assignments を作成する。

Revision ID: 002
Revises: 001
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """workload ドメインテーブルを作成する。"""
    # tags（他テーブルから FK 参照されるため先に作成）
    op.create_table(
        "tags",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # tag_assignments
    op.create_table(
        "tag_assignments",
        sa.Column("target_id", sa.String(), primary_key=True),
        sa.Column(
            "tag_id",
            sa.String(),
            sa.ForeignKey("tags.id"),
            primary_key=True,
        ),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
    )

    # scenarios
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "trigger_type",
            sa.String(),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "trigger_tag_id",
            sa.String(),
            sa.ForeignKey("tags.id"),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "execution_plan_id",
            sa.String(),
            sa.ForeignKey("execution_plans.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # scenario_steps
    op.create_table(
        "scenario_steps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String(),
            sa.ForeignKey("scenarios.id"),
            nullable=False,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column(
            "delay_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "message_type",
            sa.String(),
            nullable=False,
            server_default="text",
        ),
        sa.Column("message_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("scenario_id", "step_order", name="uq_scenario_step_order"),
    )

    # scenario_enrollments
    op.create_table(
        "scenario_enrollments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "scenario_id",
            sa.String(),
            sa.ForeignKey("scenarios.id"),
            nullable=False,
        ),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column(
            "current_step_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="active",
        ),
        sa.Column("next_delivery_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_scenario_enrollments_next_delivery_at",
        "scenario_enrollments",
        ["next_delivery_at"],
    )
    op.create_index(
        "ix_scenario_enrollments_status",
        "scenario_enrollments",
        ["status"],
    )

    # broadcasts
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "message_type",
            sa.String(),
            nullable=False,
            server_default="text",
        ),
        sa.Column("message_content", sa.Text(), nullable=False),
        sa.Column(
            "target_type",
            sa.String(),
            nullable=False,
            server_default="all",
        ),
        sa.Column(
            "target_tag_id",
            sa.String(),
            sa.ForeignKey("tags.id"),
            nullable=True,
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
    op.create_index("ix_broadcasts_status", "broadcasts", ["status"])
    op.create_index("ix_broadcasts_scheduled_at", "broadcasts", ["scheduled_at"])

    # reminders
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "execution_plan_id",
            sa.String(),
            sa.ForeignKey("execution_plans.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # reminder_steps
    op.create_table(
        "reminder_steps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "reminder_id",
            sa.String(),
            sa.ForeignKey("reminders.id"),
            nullable=False,
        ),
        sa.Column("offset_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "message_type",
            sa.String(),
            nullable=False,
            server_default="text",
        ),
        sa.Column("message_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_reminder_steps_reminder_id", "reminder_steps", ["reminder_id"])

    # reminder_enrollments
    op.create_table(
        "reminder_enrollments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "reminder_id",
            sa.String(),
            sa.ForeignKey("reminders.id"),
            nullable=False,
        ),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("target_date", sa.DateTime(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_reminder_enrollments_status",
        "reminder_enrollments",
        ["status"],
    )
    op.create_index(
        "ix_reminder_enrollments_target_date",
        "reminder_enrollments",
        ["target_date"],
    )

    # reminder_deliveries
    op.create_table(
        "reminder_deliveries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "enrollment_id",
            sa.String(),
            sa.ForeignKey("reminder_enrollments.id"),
            nullable=False,
        ),
        sa.Column(
            "reminder_step_id",
            sa.String(),
            sa.ForeignKey("reminder_steps.id"),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "enrollment_id",
            "reminder_step_id",
            name="uq_reminder_delivery",
        ),
    )


def downgrade() -> None:
    """workload ドメインテーブルを削除する。"""
    op.drop_table("reminder_deliveries")
    op.drop_table("reminder_enrollments")
    op.drop_table("reminder_steps")
    op.drop_table("reminders")
    op.drop_table("broadcasts")
    op.drop_table("scenario_enrollments")
    op.drop_table("scenario_steps")
    op.drop_table("scenarios")
    op.drop_table("tag_assignments")
    op.drop_table("tags")
