"""
Connector のテスト。

本モジュールは mock connector の全 action が正常応答することと、
capabilities() の返り値が正しいことを検証する。

入出力: action + inputs → レスポンス dict。
制約: 外部通信は一切行わない。

Note:
    - MockLineConnector の 5 action を検証する
    - MockInternalJobConnector の 2 action を検証する
"""

from app.connectors.mock_internal_job_connector import MockInternalJobConnector
from app.connectors.mock_line_connector import MockLineConnector


class TestMockLineConnector:
    """MockLineConnector のテスト。"""

    def setup_method(self):
        """各テストの前に MockLineConnector を初期化する。

        Variables:
            connector:
                テスト対象の MockLineConnector インスタンス。
        """
        self.connector = MockLineConnector()

    def test_tag_assignが正常応答する(self) -> None:
        """tag.assign アクションが success を返すことを確認する。

        Variables:
            result:
                execute の返り値。
        """
        result = self.connector.execute("tag.assign", {"tag_name": "VIP"})
        assert result["status"] == "success"

    def test_broadcast_scheduleが正常応答する(self) -> None:
        """broadcast.schedule アクションが success を返すことを確認する。

        Variables:
            result:
                execute の返り値。
        """
        result = self.connector.execute("broadcast.schedule", {})
        assert result["status"] == "success"

    def test_scenario_createが正常応答する(self) -> None:
        """scenario.create アクションが success を返すことを確認する。

        Variables:
            result:
                execute の返り値。
        """
        result = self.connector.execute("scenario.create", {})
        assert result["status"] == "success"

    def test_scenario_startが正常応答する(self) -> None:
        """scenario.start アクションが success を返すことを確認する。

        Variables:
            result:
                execute の返り値。
        """
        result = self.connector.execute("scenario.start", {})
        assert result["status"] == "success"

    def test_reminder_createが正常応答する(self) -> None:
        """reminder.create アクションが success を返すことを確認する。

        Variables:
            result:
                execute の返り値。
        """
        result = self.connector.execute("reminder.create", {})
        assert result["status"] == "success"

    def test_未サポートアクションがfailedを返す(self) -> None:
        """未サポートのアクションが failed を返すことを確認する。

        Variables:
            result:
                execute の返り値。
        """
        result = self.connector.execute("unknown.action", {})
        assert result["status"] == "failed"
        assert result["error_code"] == "UNSUPPORTED_ACTION"

    def test_capabilitiesが正しいアクション一覧を返す(self) -> None:
        """capabilities() が 5 種類のアクションを含むことを確認する。

        Variables:
            cap:
                capabilities の返り値。
        """
        cap = self.connector.capabilities()
        assert cap.connector == "line"
        assert len(cap.supported_actions) == 5
        assert "tag.assign" in cap.supported_actions
        assert "broadcast.schedule" in cap.supported_actions
        assert cap.supports_dry_run is True

    def test_dryrunがpreviewを返す(self) -> None:
        """dry_run() が preview テキストを返すことを確認する。

        Variables:
            result:
                dry_run の返り値。
        """
        result = self.connector.dry_run("tag.assign", {})
        assert "preview" in result
        assert "estimated_target_count" in result


class TestMockInternalJobConnector:
    """MockInternalJobConnector のテスト。"""

    def setup_method(self):
        """各テストの前に MockInternalJobConnector を初期化する。

        Variables:
            connector:
                テスト対象の MockInternalJobConnector インスタンス。
        """
        self.connector = MockInternalJobConnector()

    def test_job_enqueueが正常応答する(self) -> None:
        """job.enqueue アクションが success を返すことを確認する。

        Variables:
            result:
                execute の返り値。
        """
        result = self.connector.execute("job.enqueue", {})
        assert result["status"] == "success"

    def test_capabilitiesが正しい(self) -> None:
        """capabilities() が internal_job の情報を返すことを確認する。

        Variables:
            cap:
                capabilities の返り値。
        """
        cap = self.connector.capabilities()
        assert cap.connector == "internal_job"
        assert "job.enqueue" in cap.supported_actions
