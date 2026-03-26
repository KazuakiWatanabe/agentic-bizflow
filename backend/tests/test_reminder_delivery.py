"""
reminder 配信 Worker のテスト。

本モジュールは app.workers.reminder_delivery.process_reminder_deliveries の
配信処理・配信記録作成・二重配信防止・全ステップ完了を検証する。

入出力: db_session にテストデータを投入し、mock connector で配信を検証する。
制約: 外部 LLM は使わない。配信ウィンドウは mock で常に True にする。

Note:
    - target_date + offset_minutes が現在より前のステップが配信対象
    - reminder_deliveries に配信記録を作成する
    - UNIQUE 制約で二重配信を防止する
    - 全ステップ配信済みなら enrollment を completed にする
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from app.connectors.base_connector import BaseConnector
from app.db.models import (
    ReminderDeliveryModel,
    ReminderEnrollmentModel,
    ReminderModel,
    ReminderStepModel,
)
from app.schemas.connector_capability import ConnectorCapability
from app.workers.reminder_delivery import process_reminder_deliveries


class _MockDeliveryConnector(BaseConnector):
    """テスト用の mock connector。

    reminder 配信に対して常に成功を返す。

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
        return {"status": "success", "message": "delivered"}

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
            supported_actions=["reminder.deliver"],
        )


def _create_reminder_data(db_session, num_steps: int = 2):
    """テスト用の Reminder + Step + Enrollment データを作成するヘルパー。

    Args:
        db_session: テスト用 DB セッション
        num_steps: 作成するステップ数

    Returns:
        tuple: (reminder, steps リスト, enrollment)

    Variables:
        reminder_id: テスト用リマインダーの UUID
        reminder: ReminderModel インスタンス
        steps: ReminderStepModel のリスト
        enrollment: ReminderEnrollmentModel インスタンス

    Note:
        - target_date は過去に設定し、offset_minutes=0 で即 due にする
    """
    reminder_id = str(uuid.uuid4())
    reminder = ReminderModel(
        id=reminder_id,
        name="テストリマインダー",
        is_active=True,
    )
    db_session.add(reminder)
    db_session.flush()

    steps = []
    for i in range(num_steps):
        step = ReminderStepModel(
            id=str(uuid.uuid4()),
            reminder_id=reminder_id,
            offset_minutes=-(i * 60),  # 基準日以前のオフセット
            message_type="text",
            message_content=f"リマインダーステップ {i + 1}",
        )
        db_session.add(step)
        steps.append(step)
    db_session.flush()

    # target_date を十分過去に設定し、全ステップが due になるようにする
    past_target = datetime.now(timezone.utc) - timedelta(days=1)
    enrollment = ReminderEnrollmentModel(
        id=str(uuid.uuid4()),
        reminder_id=reminder_id,
        target_id="user_001",
        target_date=past_target,
        status="active",
    )
    db_session.add(enrollment)
    db_session.flush()

    return reminder, steps, enrollment


def test_due_reminder_step_is_delivered(db_session) -> None:
    """due な reminder ステップが配信されることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト用 mock connector
        result: process_reminder_deliveries の実行結果

    Note:
        - is_within_delivery_window を mock して常に True にする
    """
    connector = _MockDeliveryConnector()
    _reminder, _steps, _enrollment = _create_reminder_data(db_session, num_steps=2)

    with patch(
        "app.workers.reminder_delivery.is_within_delivery_window",
        return_value=True,
    ):
        result = process_reminder_deliveries(db_session, connector)

    assert result["processed_count"] >= 1
    assert result["error_count"] == 0
    assert connector.call_count >= 1


def test_reminder_delivery_record_is_created(db_session) -> None:
    """配信後に reminder_deliveries レコードが作成されることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト用 mock connector
        enrollment: 対象の enrollment
        deliveries: 配信記録のリスト
    """
    connector = _MockDeliveryConnector()
    _reminder, _steps, enrollment = _create_reminder_data(db_session, num_steps=1)

    with patch(
        "app.workers.reminder_delivery.is_within_delivery_window",
        return_value=True,
    ):
        process_reminder_deliveries(db_session, connector)

    # reminder_deliveries にレコードが作成されている
    deliveries = (
        db_session.query(ReminderDeliveryModel)
        .filter_by(enrollment_id=enrollment.id)
        .all()
    )
    assert len(deliveries) >= 1
    assert deliveries[0].enrollment_id == enrollment.id
    assert deliveries[0].delivered_at is not None


def test_unique_constraint_prevents_double_delivery(db_session) -> None:
    """UNIQUE 制約が二重配信を防止することを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        enrollment_id: テスト用 enrollment の UUID
        step_id: テスト用 step の UUID
        delivery1: 1 回目の配信記録
        delivery2: 2 回目の配信記録（UNIQUE 制約違反）

    Note:
        - (enrollment_id, reminder_step_id) の UNIQUE 制約で
          同じ組み合わせの INSERT が IntegrityError を発生させる
    """
    _reminder, steps, enrollment = _create_reminder_data(db_session, num_steps=1)
    step_id = steps[0].id

    # 1 回目の配信記録を INSERT
    delivery1 = ReminderDeliveryModel(
        id=str(uuid.uuid4()),
        enrollment_id=enrollment.id,
        reminder_step_id=step_id,
        delivered_at=datetime.now(timezone.utc),
    )
    db_session.add(delivery1)
    db_session.flush()

    # 2 回目の同じ組み合わせで INSERT → IntegrityError
    delivery2 = ReminderDeliveryModel(
        id=str(uuid.uuid4()),
        enrollment_id=enrollment.id,
        reminder_step_id=step_id,
        delivered_at=datetime.now(timezone.utc),
    )
    db_session.add(delivery2)
    try:
        db_session.flush()
        assert False, "IntegrityError が発生するべき"
    except IntegrityError:
        db_session.rollback()
        # UNIQUE 制約で二重配信が防止された
        assert True


def test_all_steps_delivered_completes_enrollment(db_session) -> None:
    """全ステップ配信済みで enrollment が completed になることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト用 mock connector
        enrollment: 対象の enrollment

    Note:
        - ステップ数 1 のリマインダーで 1 回配信すると completed になる
    """
    connector = _MockDeliveryConnector()
    _reminder, _steps, enrollment = _create_reminder_data(db_session, num_steps=1)

    with patch(
        "app.workers.reminder_delivery.is_within_delivery_window",
        return_value=True,
    ):
        process_reminder_deliveries(db_session, connector)

    db_session.refresh(enrollment)
    assert enrollment.status == "completed"
