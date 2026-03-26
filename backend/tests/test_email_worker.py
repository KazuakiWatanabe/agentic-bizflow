"""
Email Worker のユニットテスト。

本モジュールは process_scheduled_email_broadcasts ワーカー関数の
正常系・未到来スキップ・失敗時ステータス更新を検証する。

入出力: DB セッション + mock connector → 処理結果 dict。
制約: 外部 LLM は使わない。SMTP は使わない。

Note:
    - テストデータは EmailBroadcastModel を直接 DB に INSERT して準備する
    - connector はモッククラスを使用する
    - 冪等性チェック（IdempotencyRepository）が動作するため DB セッションが必要
"""

import uuid
from datetime import datetime, timedelta, timezone

from app.db.models import EmailBroadcastModel
from app.domains.email.worker import process_scheduled_email_broadcasts
from app.schemas.connector_capability import ConnectorCapability


class _MockEmailConnector:
    """テスト用の Email mock connector。

    execute / dry_run / capabilities を提供する。
    execute は常に成功を返す。

    Note:
        - 実際の SMTP 送信は行わない
    """

    def execute(self, action, inputs):
        """mock 実行。常に成功を返す。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            成功ステータスの dict
        """
        return {"status": "success", "message": "sent", "success_count": 1}

    def dry_run(self, action, inputs):
        """mock dry-run。プレビューを返す。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        return {"preview": "preview", "estimated_target_count": 0}

    def capabilities(self):
        """mock capabilities。サポートアクション一覧を返す。

        Returns:
            ConnectorCapability モデル
        """
        return ConnectorCapability(
            connector="email",
            supported_actions=[
                "email.broadcast.schedule",
                "email.broadcast.send",
                "email.template.create",
            ],
        )


class _FailingEmailConnector:
    """テスト用の Email mock connector（失敗版）。

    execute が常に失敗を返す。

    Note:
        - 失敗時のステータス更新を検証するために使用する
    """

    def execute(self, action, inputs):
        """mock 実行。常に失敗を返す。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            失敗ステータスの dict
        """
        return {"status": "failed", "message": "送信エラー"}

    def dry_run(self, action, inputs):
        """mock dry-run。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        return {"preview": "preview", "estimated_target_count": 0}

    def capabilities(self):
        """mock capabilities。

        Returns:
            ConnectorCapability モデル
        """
        return ConnectorCapability(
            connector="email",
            supported_actions=["email.broadcast.send"],
        )


def _create_broadcast(
    db_session,
    status="scheduled",
    scheduled_at=None,
    broadcast_id=None,
) -> EmailBroadcastModel:
    """テスト用の EmailBroadcastModel を DB に作成するヘルパー。

    Args:
        db_session: テスト用 DB セッション
        status: レコードのステータス
        scheduled_at: 配信予約日時
        broadcast_id: レコード ID（省略時は UUID 自動生成）

    Returns:
        作成した EmailBroadcastModel インスタンス
    """
    # デフォルトは過去日時（処理対象になる）
    if scheduled_at is None:
        scheduled_at = datetime.now(timezone.utc) - timedelta(hours=1)

    record = EmailBroadcastModel(
        id=broadcast_id or str(uuid.uuid4()),
        subject="テスト配信",
        body_html="<p>テスト</p>",
        from_address="test@example.com",
        target_type="all",
        status=status,
        scheduled_at=scheduled_at,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(record)
    db_session.commit()
    return record


def test_scheduled_past_broadcast_becomes_sent(db_session) -> None:
    """過去の scheduled_at を持つレコードが sent に更新されることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        broadcast: テスト用の配信レコード
        result: ワーカー関数の戻り値
        updated: 更新後の配信レコード

    Note:
        - status が scheduled → sent に遷移する
        - processed_count が 1 であること
    """
    broadcast = _create_broadcast(
        db_session,
        status="scheduled",
        scheduled_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    connector = _MockEmailConnector()
    result = process_scheduled_email_broadcasts(db_session, connector)

    assert result["processed_count"] == 1
    assert result["error_count"] == 0

    # DB のステータスを確認
    db_session.refresh(broadcast)
    assert broadcast.status == "sent"


def test_future_scheduled_broadcast_not_processed(db_session) -> None:
    """未来の scheduled_at を持つレコードが処理されないことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        broadcast: テスト用の配信レコード（未来日時）
        result: ワーカー関数の戻り値

    Note:
        - scheduled_at が未来の場合は処理対象にならない
        - processed_count が 0 であること
    """
    # 未来の日時で配信を作成
    future_time = datetime.now(timezone.utc) + timedelta(hours=24)
    broadcast = _create_broadcast(
        db_session,
        status="scheduled",
        scheduled_at=future_time,
    )

    connector = _MockEmailConnector()
    result = process_scheduled_email_broadcasts(db_session, connector)

    assert result["processed_count"] == 0
    assert result["error_count"] == 0

    # ステータスが変わっていないことを確認
    db_session.refresh(broadcast)
    assert broadcast.status == "scheduled"


def test_failure_sets_status_failed(db_session) -> None:
    """connector が失敗を返した場合に status が failed になることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        broadcast: テスト用の配信レコード
        result: ワーカー関数の戻り値

    Note:
        - connector.execute が failed を返した場合
        - status が scheduled → failed に遷移する
    """
    broadcast = _create_broadcast(
        db_session,
        status="scheduled",
        scheduled_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    connector = _FailingEmailConnector()
    result = process_scheduled_email_broadcasts(db_session, connector)

    # 処理はされた（processed_count=1）がエラーあり
    assert result["processed_count"] == 1
    assert result["error_count"] == 1

    # DB のステータスを確認
    db_session.refresh(broadcast)
    assert broadcast.status == "failed"
