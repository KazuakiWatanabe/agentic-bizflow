"""
DB ORM モデルの CRUD テスト。

本モジュールは全テーブルの CRUD 操作、外部キー制約、UNIQUE 制約の動作を検証する。

入出力: db_session フィクスチャで in-memory SQLite に対して操作する。
制約: 外部 LLM は使わない。

Note:
    - conftest.py の db_session フィクスチャを使用する
    - 各テスト後に rollback でデータを初期化する
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    BroadcastModel,
    ExecutionPlanModel,
    ExecutionResultModel,
    ReminderDeliveryModel,
    ReminderEnrollmentModel,
    ReminderModel,
    ReminderStepModel,
    ScenarioEnrollmentModel,
    ScenarioModel,
    ScenarioStepModel,
    StepResultModel,
    TagAssignmentModel,
    TagModel,
)


def _now() -> datetime:
    """テスト用の現在時刻を返す。"""
    return datetime.now(timezone.utc)


def _uid() -> str:
    """テスト用の UUID を返す。"""
    return str(uuid.uuid4())


class TestExecutionPlanModel:
    """execution_plans テーブルの CRUD テスト。"""

    def test_INSERT_とSELECT(self, db_session) -> None:
        """execution_plans にレコードを INSERT し SELECT できることを確認する。"""
        plan = ExecutionPlanModel(
            id=_uid(),
            source_definition_id="def_001",
            source_definition_json='{"title": "test"}',
            plan_json='{"plan_id": "plan_001"}',
            status="created",
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(plan)
        db_session.flush()

        result = db_session.query(ExecutionPlanModel).filter_by(id=plan.id).first()
        assert result is not None
        assert result.status == "created"
        assert result.risk_level == "low"

    def test_statusのデフォルト値(self, db_session) -> None:
        """status のデフォルトが 'created' であることを確認する。"""
        plan = ExecutionPlanModel(
            id=_uid(),
            source_definition_id="def_002",
            source_definition_json="{}",
            plan_json="{}",
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(plan)
        db_session.flush()

        result = db_session.query(ExecutionPlanModel).filter_by(id=plan.id).first()
        assert result.status == "created"


class TestExecutionResultModel:
    """execution_results テーブルの CRUD テスト。"""

    def test_FK制約_planが存在する場合(self, db_session) -> None:
        """execution_results の plan_id FK が正しく機能することを確認する。"""
        plan_id = _uid()
        plan = ExecutionPlanModel(
            id=plan_id,
            source_definition_id="def_001",
            source_definition_json="{}",
            plan_json="{}",
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(plan)
        db_session.flush()

        result = ExecutionResultModel(
            id=_uid(),
            plan_id=plan_id,
            status="success",
            started_at=_now(),
        )
        db_session.add(result)
        db_session.flush()

        fetched = db_session.query(ExecutionResultModel).filter_by(id=result.id).first()
        assert fetched is not None
        assert fetched.plan_id == plan_id


class TestStepResultModel:
    """step_results テーブルの CRUD テスト。"""

    def test_INSERT(self, db_session) -> None:
        """step_results にレコードを INSERT できることを確認する。"""
        plan_id = _uid()
        exec_id = _uid()
        plan = ExecutionPlanModel(
            id=plan_id,
            source_definition_id="def",
            source_definition_json="{}",
            plan_json="{}",
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(plan)
        db_session.flush()

        exec_result = ExecutionResultModel(
            id=exec_id,
            plan_id=plan_id,
            status="success",
            started_at=_now(),
        )
        db_session.add(exec_result)
        db_session.flush()

        step = StepResultModel(
            id=_uid(),
            execution_id=exec_id,
            step_id="step_001",
            sequence=1,
            kind="tag.assign",
            connector="line",
            status="success",
            created_at=_now(),
        )
        db_session.add(step)
        db_session.flush()

        fetched = db_session.query(StepResultModel).filter_by(id=step.id).first()
        assert fetched is not None
        assert fetched.kind == "tag.assign"


class TestTagModel:
    """tags テーブルの CRUD テスト。"""

    def test_UNIQUE制約_同名タグ(self, db_session) -> None:
        """同名タグの INSERT で IntegrityError が発生することを確認する。"""
        tag1 = TagModel(id=_uid(), name="VIP", created_at=_now())
        db_session.add(tag1)
        db_session.flush()

        tag2 = TagModel(id=_uid(), name="VIP", created_at=_now())
        db_session.add(tag2)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestTagAssignmentModel:
    """tag_assignments テーブルのテスト。"""

    def test_タグ付与(self, db_session) -> None:
        """タグ付与レコードが作成できることを確認する。"""
        tag = TagModel(id=_uid(), name="test_tag", created_at=_now())
        db_session.add(tag)
        db_session.flush()

        assignment = TagAssignmentModel(
            target_id="user_001",
            tag_id=tag.id,
            assigned_at=_now(),
        )
        db_session.add(assignment)
        db_session.flush()

        fetched = (
            db_session.query(TagAssignmentModel)
            .filter_by(target_id="user_001", tag_id=tag.id)
            .first()
        )
        assert fetched is not None


class TestScenarioModel:
    """scenarios 関連テーブルのテスト。"""

    def test_scenario_と_stepsの作成(self, db_session) -> None:
        """シナリオとステップが作成できることを確認する。"""
        scenario = ScenarioModel(
            id=_uid(),
            name="テストシナリオ",
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(scenario)
        db_session.flush()

        step = ScenarioStepModel(
            id=_uid(),
            scenario_id=scenario.id,
            step_order=1,
            message_content="ステップ1",
            created_at=_now(),
        )
        db_session.add(step)
        db_session.flush()

        fetched = db_session.query(ScenarioStepModel).filter_by(id=step.id).first()
        assert fetched is not None
        assert fetched.message_content == "ステップ1"

    def test_scenario_steps_UNIQUE制約(self, db_session) -> None:
        """scenario_steps の (scenario_id, step_order) UNIQUE 制約を確認する。"""
        sid = _uid()
        scenario = ScenarioModel(
            id=sid, name="dup_test", created_at=_now(), updated_at=_now()
        )
        db_session.add(scenario)
        db_session.flush()

        s1 = ScenarioStepModel(
            id=_uid(),
            scenario_id=sid,
            step_order=1,
            message_content="ステップ1",
            created_at=_now(),
        )
        db_session.add(s1)
        db_session.flush()

        s2 = ScenarioStepModel(
            id=_uid(),
            scenario_id=sid,
            step_order=1,
            message_content="重複",
            created_at=_now(),
        )
        db_session.add(s2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_enrollment_がactive_で作成される(self, db_session) -> None:
        """enrollment が status=active で作成されることを確認する。"""
        scenario = ScenarioModel(
            id=_uid(), name="enroll_test", created_at=_now(), updated_at=_now()
        )
        db_session.add(scenario)
        db_session.flush()

        enrollment = ScenarioEnrollmentModel(
            id=_uid(),
            scenario_id=scenario.id,
            target_id="user_001",
            started_at=_now(),
            updated_at=_now(),
        )
        db_session.add(enrollment)
        db_session.flush()

        fetched = (
            db_session.query(ScenarioEnrollmentModel)
            .filter_by(id=enrollment.id)
            .first()
        )
        assert fetched.status == "active"


class TestBroadcastModel:
    """broadcasts テーブルのテスト。"""

    def test_statusのデフォルトはdraft(self, db_session) -> None:
        """broadcasts の status デフォルトが 'draft' であることを確認する。"""
        broadcast = BroadcastModel(
            id=_uid(),
            title="テスト配信",
            message_content="テストメッセージ",
            created_at=_now(),
        )
        db_session.add(broadcast)
        db_session.flush()

        fetched = db_session.query(BroadcastModel).filter_by(id=broadcast.id).first()
        assert fetched.status == "draft"


class TestReminderModel:
    """reminders 関連テーブルのテスト。"""

    def test_reminder_と_stepsの作成(self, db_session) -> None:
        """リマインダーとステップが作成できることを確認する。"""
        reminder = ReminderModel(
            id=_uid(), name="テストリマインダー", created_at=_now(), updated_at=_now()
        )
        db_session.add(reminder)
        db_session.flush()

        step = ReminderStepModel(
            id=_uid(),
            reminder_id=reminder.id,
            offset_minutes=-60,
            message_content="1時間前通知",
            created_at=_now(),
        )
        db_session.add(step)
        db_session.flush()

        fetched = db_session.query(ReminderStepModel).filter_by(id=step.id).first()
        assert fetched.offset_minutes == -60

    def test_reminder_delivery_UNIQUE制約(self, db_session) -> None:
        """reminder_deliveries の UNIQUE 制約を確認する。"""
        reminder = ReminderModel(
            id=_uid(), name="uniq_test", created_at=_now(), updated_at=_now()
        )
        db_session.add(reminder)
        db_session.flush()

        step = ReminderStepModel(
            id=_uid(),
            reminder_id=reminder.id,
            offset_minutes=0,
            message_content="msg",
            created_at=_now(),
        )
        db_session.add(step)
        db_session.flush()

        enrollment = ReminderEnrollmentModel(
            id=_uid(),
            reminder_id=reminder.id,
            target_id="user_001",
            target_date=_now(),
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(enrollment)
        db_session.flush()

        d1 = ReminderDeliveryModel(
            id=_uid(),
            enrollment_id=enrollment.id,
            reminder_step_id=step.id,
            delivered_at=_now(),
        )
        db_session.add(d1)
        db_session.flush()

        d2 = ReminderDeliveryModel(
            id=_uid(),
            enrollment_id=enrollment.id,
            reminder_step_id=step.id,
            delivered_at=_now(),
        )
        db_session.add(d2)
        with pytest.raises(IntegrityError):
            db_session.flush()
