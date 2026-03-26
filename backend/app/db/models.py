"""
SQLAlchemy ORM モデル定義。

本モジュールは Phase 3 で使用する全テーブルの ORM モデルを定義する。
実行管理テーブル（execution_plans / execution_results / step_results）と
workload ドメインテーブル（scenarios / broadcasts / reminders / tags 等）を含む。

入出力: Base を継承した ORM モデルクラスを公開する。
制約: Agent 層（app/agent/）には依存しない。

Note:
    - ID は UUID v4 の文字列型（TEXT）
    - タイムスタンプは UTC の datetime 型
    - Alembic の env.py から import されて Base.metadata に登録される
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ============================================================
# ヘルパー: 現在の UTC 日時を返す
# ============================================================
def _utcnow() -> datetime:
    """現在の UTC 日時を返すヘルパー。

    Returns:
        タイムゾーン付きの UTC 現在日時
    """
    return datetime.now(timezone.utc)


# ============================================================
# 実行管理テーブル（Task 2）
# ============================================================


class ExecutionPlanModel(Base):
    """実行計画の永続化モデル。

    ExecutionPlanner が生成した ExecutionPlan を DB に保存する。
    status は created → approved → executing → completed / failed と遷移する。

    Variables:
        id: plan_id（UUID 文字列）
        source_definition_id: 元の BusinessDefinition の識別子
        source_definition_json: BusinessDefinition の JSON スナップショット
        plan_json: ExecutionPlan 全体の JSON
        requires_approval: 承認要否
        risk_level: low / medium / high
        summary: 実行計画の要約
        status: created / approved / executing / completed / failed
        created_at: 作成日時
        updated_at: 更新日時

    Note:
        - status のデフォルトは 'created'
        - risk_level のデフォルトは 'low'
    """

    __tablename__ = "execution_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_definition_id: Mapped[str] = mapped_column(String, nullable=False)
    source_definition_json: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    risk_level: Mapped[str] = mapped_column(String, nullable=False, default="low")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # リレーション
    execution_results: Mapped[list["ExecutionResultModel"]] = relationship(
        back_populates="plan"
    )


class ExecutionResultModel(Base):
    """実行結果の永続化モデル。

    WorkloadRunner の実行結果を DB に保存する。

    Variables:
        id: execution_id（UUID 文字列）
        plan_id: 実行した ExecutionPlan の ID（FK）
        status: success / partial_success / failed / blocked
        started_at: 実行開始日時
        finished_at: 実行完了日時
        errors_json: エラー一覧の JSON 文字列
        warnings_json: 警告一覧の JSON 文字列

    Note:
        - finished_at は実行中は NULL、完了後に設定される
    """

    __tablename__ = "execution_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        String, ForeignKey("execution_plans.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    errors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # リレーション
    plan: Mapped["ExecutionPlanModel"] = relationship(
        back_populates="execution_results"
    )
    step_results: Mapped[list["StepResultModel"]] = relationship(
        back_populates="execution"
    )


class StepResultModel(Base):
    """ステップ実行結果の永続化モデル。

    各 ExecutionStep の実行結果を個別に保存する。

    Variables:
        id: UUID 文字列
        execution_id: 所属する ExecutionResult の ID（FK）
        step_id: ExecutionStep の step_id
        sequence: ステップ順序
        kind: workload kind
        connector: connector 名
        status: success / failed / blocked / skipped
        error_code: エラーコード（成功時は NULL）
        message: 結果メッセージ
        created_at: 記録日時

    Note:
        - error_code は成功時に NULL となる
    """

    __tablename__ = "step_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String, ForeignKey("execution_results.id"), nullable=False
    )
    step_id: Mapped[str] = mapped_column(String, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    connector: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    # リレーション
    execution: Mapped["ExecutionResultModel"] = relationship(
        back_populates="step_results"
    )


# ============================================================
# workload ドメインテーブル（Task 3）
# ============================================================


class TagModel(Base):
    """タグの永続化モデル。

    タグ名を一意に管理する。tag.assign で UPSERT される。

    Variables:
        id: UUID 文字列
        name: タグ名（UNIQUE）
        created_at: 作成日時

    Note:
        - name に UNIQUE 制約を設定する
    """

    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    # リレーション
    assignments: Mapped[list["TagAssignmentModel"]] = relationship(back_populates="tag")


class TagAssignmentModel(Base):
    """タグ付与の永続化モデル。

    対象者にタグを付与する。複合主キー（target_id, tag_id）。

    Variables:
        target_id: 対象者の外部 ID
        tag_id: タグ ID（FK → tags）
        assigned_at: 付与日時

    Note:
        - line-harness の friend_tags に相当
        - target_id は LINE に限定しない汎用的な識別子
    """

    __tablename__ = "tag_assignments"

    target_id: Mapped[str] = mapped_column(String, primary_key=True)
    tag_id: Mapped[str] = mapped_column(String, ForeignKey("tags.id"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    # リレーション
    tag: Mapped["TagModel"] = relationship(back_populates="assignments")


class ScenarioModel(Base):
    """シナリオの永続化モデル。

    ステップ配信シナリオを管理する。

    Variables:
        id: UUID 文字列
        name: シナリオ名
        description: 説明
        trigger_type: manual / tag_added
        trigger_tag_id: タグトリガー時のタグ ID（FK → tags）
        is_active: 有効/無効
        execution_plan_id: 生成元の plan ID（FK → execution_plans）
        created_at: 作成日時
        updated_at: 更新日時

    Note:
        - trigger_type のデフォルトは 'manual'
    """

    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    trigger_tag_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("tags.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    execution_plan_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("execution_plans.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # リレーション
    steps: Mapped[list["ScenarioStepModel"]] = relationship(back_populates="scenario")
    enrollments: Mapped[list["ScenarioEnrollmentModel"]] = relationship(
        back_populates="scenario"
    )


class ScenarioStepModel(Base):
    """シナリオステップの永続化モデル。

    シナリオ内の個別配信ステップを管理する。

    Variables:
        id: UUID 文字列
        scenario_id: 所属シナリオ ID（FK → scenarios）
        step_order: ステップ順序
        delay_minutes: 前ステップからの遅延（分）
        message_type: text / image / flex
        message_content: メッセージ本文
        created_at: 作成日時

    Note:
        - (scenario_id, step_order) に UNIQUE 制約を設定する
    """

    __tablename__ = "scenario_steps"
    __table_args__ = (
        UniqueConstraint("scenario_id", "step_order", name="uq_scenario_step_order"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        String, ForeignKey("scenarios.id"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_type: Mapped[str] = mapped_column(String, nullable=False, default="text")
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    # リレーション
    scenario: Mapped["ScenarioModel"] = relationship(back_populates="steps")


class ScenarioEnrollmentModel(Base):
    """シナリオ登録の永続化モデル。

    対象者をシナリオに登録する。line-harness の friend_scenarios に相当。

    Variables:
        id: UUID 文字列
        scenario_id: シナリオ ID（FK → scenarios）
        target_id: 対象者の外部 ID
        current_step_order: 現在のステップ位置
        status: active / paused / completed
        next_delivery_at: 次回配信予定日時
        started_at: 開始日時
        updated_at: 更新日時

    Note:
        - Phase 3 では enroll（active 状態で登録）までを行う
        - step 進行は Phase 4 の責務
    """

    __tablename__ = "scenario_enrollments"
    __table_args__ = (
        Index("ix_scenario_enrollments_next_delivery_at", "next_delivery_at"),
        Index("ix_scenario_enrollments_status", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        String, ForeignKey("scenarios.id"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    current_step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    next_delivery_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # リレーション
    scenario: Mapped["ScenarioModel"] = relationship(back_populates="enrollments")


class BroadcastModel(Base):
    """一斉配信の永続化モデル。

    一斉配信メッセージを管理する。

    Variables:
        id: UUID 文字列
        title: 配信タイトル
        message_type: text / image / flex
        message_content: メッセージ本文
        target_type: all / tag / segment
        target_tag_id: タグ絞り込み時のタグ ID（FK → tags）
        status: draft / scheduled / sending / sent
        scheduled_at: 予約配信日時
        sent_at: 送信完了日時
        total_count: 対象者数
        success_count: 送信成功数
        execution_plan_id: 生成元の plan ID（FK → execution_plans）
        created_at: 作成日時

    Note:
        - Phase 3 では draft → scheduled までを担当する
        - sending → sent への遷移は Phase 4（Cron）の責務
    """

    __tablename__ = "broadcasts"
    __table_args__ = (
        Index("ix_broadcasts_status", "status"),
        Index("ix_broadcasts_scheduled_at", "scheduled_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message_type: Mapped[str] = mapped_column(String, nullable=False, default="text")
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False, default="all")
    target_tag_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("tags.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_plan_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("execution_plans.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )


class ReminderModel(Base):
    """リマインダーの永続化モデル。

    リマインダーを管理する。

    Variables:
        id: UUID 文字列
        name: リマインダ名
        description: 説明
        is_active: 有効/無効
        execution_plan_id: 生成元の plan ID（FK → execution_plans）
        created_at: 作成日時
        updated_at: 更新日時
    """

    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    execution_plan_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("execution_plans.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # リレーション
    steps: Mapped[list["ReminderStepModel"]] = relationship(back_populates="reminder")
    enrollments: Mapped[list["ReminderEnrollmentModel"]] = relationship(
        back_populates="reminder"
    )


class ReminderStepModel(Base):
    """リマインダーステップの永続化モデル。

    リマインダーの個別配信ステップを管理する。

    Variables:
        id: UUID 文字列
        reminder_id: 所属リマインダ ID（FK → reminders）
        offset_minutes: 基準日からのオフセット（負=前、正=後）
        message_type: text / image / flex
        message_content: メッセージ本文
        created_at: 作成日時

    Note:
        - offset_minutes が負の場合は基準日より前に配信する
    """

    __tablename__ = "reminder_steps"
    __table_args__ = (Index("ix_reminder_steps_reminder_id", "reminder_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    reminder_id: Mapped[str] = mapped_column(
        String, ForeignKey("reminders.id"), nullable=False
    )
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    message_type: Mapped[str] = mapped_column(String, nullable=False, default="text")
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    # リレーション
    reminder: Mapped["ReminderModel"] = relationship(back_populates="steps")


class ReminderEnrollmentModel(Base):
    """リマインダー登録の永続化モデル。

    対象者をリマインダーに登録する。line-harness の friend_reminders に相当。

    Variables:
        id: UUID 文字列
        reminder_id: リマインダ ID（FK → reminders）
        target_id: 対象者の外部 ID
        target_date: 基準日（例: セミナー日）
        status: active / completed / cancelled
        created_at: 作成日時
        updated_at: 更新日時
    """

    __tablename__ = "reminder_enrollments"
    __table_args__ = (
        Index("ix_reminder_enrollments_status", "status"),
        Index("ix_reminder_enrollments_target_date", "target_date"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    reminder_id: Mapped[str] = mapped_column(
        String, ForeignKey("reminders.id"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    target_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # リレーション
    reminder: Mapped["ReminderModel"] = relationship(back_populates="enrollments")
    deliveries: Mapped[list["ReminderDeliveryModel"]] = relationship(
        back_populates="enrollment"
    )


class ReminderDeliveryModel(Base):
    """リマインダー配信記録の永続化モデル。

    配信済み記録を管理する。冪等性の担保に使用する。

    Variables:
        id: UUID 文字列
        enrollment_id: 登録 ID（FK → reminder_enrollments）
        reminder_step_id: ステップ ID（FK → reminder_steps）
        delivered_at: 配信日時

    Note:
        - (enrollment_id, reminder_step_id) に UNIQUE 制約を設定する
        - 冪等性の担保に使用する（同じ組み合わせで 2 回配信しない）
    """

    __tablename__ = "reminder_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "enrollment_id",
            "reminder_step_id",
            name="uq_reminder_delivery",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    enrollment_id: Mapped[str] = mapped_column(
        String, ForeignKey("reminder_enrollments.id"), nullable=False
    )
    reminder_step_id: Mapped[str] = mapped_column(
        String, ForeignKey("reminder_steps.id"), nullable=False
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    # リレーション
    enrollment: Mapped["ReminderEnrollmentModel"] = relationship(
        back_populates="deliveries"
    )
