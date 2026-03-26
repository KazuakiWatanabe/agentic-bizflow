"""
DB Connector のテスト。

本モジュールは DBLineConnector が各 workload kind で
正しく DB にレコードを書き込むことを検証する。

入出力: DBLineConnector を db_session で初期化し、execute / dry_run を呼ぶ。
制約: in-memory SQLite を使用する。外部 LLM は使わない。

Note:
    - execute で DB にレコードが作成されることを確認する
    - dry_run で DB にレコードが作成されないことを確認する
"""

from app.connectors.db_line_connector import DBLineConnector
from app.db.models import (
    BroadcastModel,
    ReminderModel,
    ReminderStepModel,
    ScenarioEnrollmentModel,
    ScenarioModel,
    ScenarioStepModel,
    TagAssignmentModel,
    TagModel,
)


class TestDBLineConnectorExecute:
    """DBLineConnector の execute テスト。"""

    def test_tag_assignでtags_と_tag_assignmentsにレコードが作成される(
        self, db_session
    ) -> None:
        """tag.assign で tags + tag_assignments にレコードが作成される。

        Variables:
            connector: DBLineConnector インスタンス
            result: execute の結果 dict
        """
        connector = DBLineConnector(db=db_session)
        result = connector.execute(
            "tag.assign",
            {"tag_name": "VIP", "target": "user_001"},
        )
        db_session.flush()

        assert result["status"] == "success"
        assert db_session.query(TagModel).filter_by(name="VIP").first() is not None
        assert (
            db_session.query(TagAssignmentModel)
            .filter_by(target_id="user_001")
            .first()
            is not None
        )

    def test_broadcast_scheduleでbroadcastsがscheduledで作成される(
        self, db_session
    ) -> None:
        """broadcast.schedule で broadcasts が status=scheduled で作成される。

        Variables:
            connector: DBLineConnector インスタンス
            result: execute の結果 dict
        """
        connector = DBLineConnector(db=db_session)
        result = connector.execute(
            "broadcast.schedule",
            {"message": "テスト配信"},
        )
        db_session.flush()

        assert result["status"] == "success"
        broadcast = db_session.query(BroadcastModel).first()
        assert broadcast is not None
        assert broadcast.status == "scheduled"

    def test_scenario_createでscenarios_と_stepsが作成される(
        self, db_session
    ) -> None:
        """scenario.create で scenarios + scenario_steps が作成される。

        Variables:
            connector: DBLineConnector インスタンス
            result: execute の結果 dict
        """
        connector = DBLineConnector(db=db_session)
        result = connector.execute(
            "scenario.create",
            {"scenario_name": "テストシナリオ", "steps": ["ステップ1", "ステップ2"]},
        )
        db_session.flush()

        assert result["status"] == "success"
        assert db_session.query(ScenarioModel).first() is not None
        assert db_session.query(ScenarioStepModel).count() == 2

    def test_scenario_startでenrollmentsがactiveで作成される(
        self, db_session
    ) -> None:
        """scenario.start で scenario_enrollments が active で作成される。

        Variables:
            connector: DBLineConnector インスタンス
        """
        connector = DBLineConnector(db=db_session)
        # まずシナリオを作成
        connector.execute(
            "scenario.create",
            {"scenario_name": "開始テスト", "steps": ["ステップ1"]},
        )
        db_session.flush()

        # シナリオ開始
        result = connector.execute(
            "scenario.start",
            {"scenario_name": "開始テスト", "target": "user_001"},
        )
        db_session.flush()

        assert result["status"] == "success"
        enrollment = db_session.query(ScenarioEnrollmentModel).first()
        assert enrollment is not None
        assert enrollment.status == "active"

    def test_reminder_createでreminders_と_stepsが作成される(
        self, db_session
    ) -> None:
        """reminder.create で reminders + reminder_steps が作成される。

        Variables:
            connector: DBLineConnector インスタンス
            result: execute の結果 dict
        """
        connector = DBLineConnector(db=db_session)
        result = connector.execute(
            "reminder.create",
            {"reminder_name": "テストリマインダー", "steps": ["通知1", "通知2"]},
        )
        db_session.flush()

        assert result["status"] == "success"
        assert db_session.query(ReminderModel).first() is not None
        assert db_session.query(ReminderStepModel).count() == 2

    def test_scenario_start_存在しないシナリオでfailed(
        self, db_session
    ) -> None:
        """存在しないシナリオで scenario.start が failed を返すことを確認する。"""
        connector = DBLineConnector(db=db_session)
        result = connector.execute(
            "scenario.start",
            {"scenario_name": "存在しない", "target": "user_001"},
        )
        assert result["status"] == "failed"
        assert result["error_code"] == "SCENARIO_NOT_FOUND"


class TestDBLineConnectorDryRun:
    """DBLineConnector の dry_run テスト。"""

    def test_dryrunでDBにレコードが作成されない(self, db_session) -> None:
        """dry_run で DB にレコードが作成されないことを確認する。

        Variables:
            connector: DBLineConnector インスタンス
        """
        connector = DBLineConnector(db=db_session)

        # 全アクションの dry_run を実行
        for action in [
            "tag.assign",
            "broadcast.schedule",
            "scenario.create",
            "scenario.start",
            "reminder.create",
        ]:
            result = connector.dry_run(action, {"tag_name": "t", "message": "m"})
            assert "preview" in result

        # DB にレコードが作成されていないことを確認
        assert db_session.query(TagModel).count() == 0
        assert db_session.query(BroadcastModel).count() == 0
        assert db_session.query(ScenarioModel).count() == 0
        assert db_session.query(ReminderModel).count() == 0

    def test_capabilitiesが正しいactionリストを返す(self, db_session) -> None:
        """capabilities() が正しいアクションリストを返すことを確認する。"""
        connector = DBLineConnector(db=db_session)
        caps = connector.capabilities()
        assert caps.connector == "line"
        assert "tag.assign" in caps.supported_actions
        assert "broadcast.schedule" in caps.supported_actions
        assert "scenario.create" in caps.supported_actions
        assert "scenario.start" in caps.supported_actions
        assert "reminder.create" in caps.supported_actions
