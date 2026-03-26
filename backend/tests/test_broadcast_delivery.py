"""
broadcast 配信 Worker のテスト。

本モジュールは app.workers.broadcast_delivery.process_scheduled_broadcasts の
配信処理を検証する。

入出力: db_session にテストデータを投入し、mock connector で配信を検証する。
制約: 外部 LLM は使わない。

Note:
    - scheduled_at が過去の broadcast → 送信される
    - scheduled_at が未来の broadcast → 処理されない
    - 配信失敗 → status=failed に遷移する
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.connectors.base_connector import BaseConnector
from app.db.models import BroadcastModel
from app.schemas.connector_capability import ConnectorCapability
from app.workers.broadcast_delivery import process_scheduled_broadcasts


class _MockDeliveryConnector(BaseConnector):
    """テスト用の mock connector。

    broadcast 配信に対して常に成功を返す。

    Variables:
        call_count: execute が呼び出された回数
    """

    def __init__(self) -> None:
        """_MockDeliveryConnector を初期化する。"""
        self.call_count = 0

    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """成功レスポンスを返す。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            成功ステータスの dict
        """
        self.call_count += 1
        return {"status": "success", "message": "delivered", "success_count": 100}

    def dry_run(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """プレビューを返す。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        return {"preview": "preview", "estimated_target_count": 0}

    def capabilities(self) -> ConnectorCapability:
        """サポートアクション一覧を返す。

        Returns:
            ConnectorCapability モデル
        """
        return ConnectorCapability(
            connector="mock",
            supported_actions=["broadcast.send"],
        )


class _MockFailConnector(BaseConnector):
    """テスト用の失敗 mock connector。

    broadcast 配信に対して常に失敗を返す。
    """

    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """失敗レスポンスを返す。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            失敗ステータスの dict
        """
        return {"status": "failed", "message": "delivery error"}

    def dry_run(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """プレビューを返す。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        return {"preview": "preview", "estimated_target_count": 0}

    def capabilities(self) -> ConnectorCapability:
        """サポートアクション一覧を返す。

        Returns:
            ConnectorCapability モデル
        """
        return ConnectorCapability(
            connector="mock_fail",
            supported_actions=["broadcast.send"],
        )


def _create_broadcast(db_session, scheduled_at: datetime) -> BroadcastModel:
    """テスト用の BroadcastModel を作成するヘルパー。

    Args:
        db_session: テスト用 DB セッション
        scheduled_at: 予約配信日時

    Returns:
        BroadcastModel インスタンス

    Variables:
        broadcast: 作成された BroadcastModel
    """
    broadcast = BroadcastModel(
        id=str(uuid.uuid4()),
        title="テスト配信",
        message_type="text",
        message_content="テストメッセージ",
        target_type="all",
        status="scheduled",
        scheduled_at=scheduled_at,
    )
    db_session.add(broadcast)
    db_session.flush()
    return broadcast


def test_past_scheduled_broadcast_sent(db_session) -> None:
    """scheduled_at が過去の broadcast が送信されることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        past_time: 過去の日時
        broadcast: テスト用 broadcast
        connector: テスト用 mock connector
        result: process_scheduled_broadcasts の結果

    Note:
        - scheduled_at が現在より前なら配信対象となる
    """
    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    broadcast = _create_broadcast(db_session, scheduled_at=past_time)
    connector = _MockDeliveryConnector()

    result = process_scheduled_broadcasts(db_session, connector)

    assert result["processed_count"] >= 1
    assert result["error_count"] == 0
    assert connector.call_count >= 1

    db_session.refresh(broadcast)
    assert broadcast.status == "sent"
    assert broadcast.sent_at is not None


def test_future_scheduled_broadcast_not_processed(db_session) -> None:
    """scheduled_at が未来の broadcast が処理されないことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        future_time: 未来の日時
        broadcast: テスト用 broadcast
        connector: テスト用 mock connector
        result: process_scheduled_broadcasts の結果

    Note:
        - scheduled_at が現在より後なら配信対象にならない
    """
    future_time = datetime.now(timezone.utc) + timedelta(hours=24)
    broadcast = _create_broadcast(db_session, scheduled_at=future_time)
    connector = _MockDeliveryConnector()

    result = process_scheduled_broadcasts(db_session, connector)

    assert result["processed_count"] == 0
    assert connector.call_count == 0

    db_session.refresh(broadcast)
    assert broadcast.status == "scheduled"


def test_failed_broadcast_status_is_failed(db_session) -> None:
    """配信失敗時に status が failed になることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        past_time: 過去の日時
        broadcast: テスト用 broadcast
        connector: テスト用失敗 mock connector
        result: process_scheduled_broadcasts の結果
    """
    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    broadcast = _create_broadcast(db_session, scheduled_at=past_time)
    connector = _MockFailConnector()

    result = process_scheduled_broadcasts(db_session, connector)

    assert result["processed_count"] >= 1

    db_session.refresh(broadcast)
    assert broadcast.status == "failed"
