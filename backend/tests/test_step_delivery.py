"""
scenario step 配信 Worker のテスト。

本モジュールは app.workers.step_delivery.process_step_deliveries の
配信処理・ステップ進行・完了遷移・失敗リトライを検証する。

入出力: db_session にテストデータを投入し、mock connector で配信を検証する。
制約: 外部 LLM は使わない。配信ウィンドウは mock で常に True にする。

Note:
    - next_delivery_at を過去に設定して due 状態にする
    - mock connector は {"status": "success", "message": "ok"} を返す
    - is_within_delivery_window を mock して時間帯に依存しないテストにする
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import patch

from app.connectors.base_connector import BaseConnector
from app.db.models import (
    ScenarioEnrollmentModel,
    ScenarioModel,
    ScenarioStepModel,
)
from app.schemas.connector_capability import ConnectorCapability
from app.workers.step_delivery import process_step_deliveries


class _MockDeliveryConnector(BaseConnector):
    """テスト用の mock connector。

    配信アクションに対して常に成功を返す。

    Variables:
        call_count: execute が呼び出された回数
        last_action: 最後に呼び出された action 名
    """

    def __init__(self) -> None:
        """_MockDeliveryConnector を初期化する。"""
        self.call_count = 0
        self.last_action = ""

    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """成功レスポンスを返す。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            成功ステータスの dict
        """
        self.call_count += 1
        self.last_action = action
        return {"status": "success", "message": "ok"}

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
            supported_actions=["scenario.deliver"],
        )


class _MockFailConnector(BaseConnector):
    """テスト用の失敗 mock connector。

    配信アクションに対して常に失敗を返す。
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
            supported_actions=["scenario.deliver"],
        )


def _create_scenario_data(db_session, num_steps: int = 2):
    """テスト用の Scenario + Step + Enrollment データを作成するヘルパー。

    Args:
        db_session: テスト用 DB セッション
        num_steps: 作成するステップ数

    Returns:
        tuple: (scenario, steps リスト, enrollment)

    Variables:
        scenario_id: テスト用シナリオの UUID
        scenario: ScenarioModel インスタンス
        steps: ScenarioStepModel のリスト
        enrollment: ScenarioEnrollmentModel インスタンス

    Note:
        - next_delivery_at は過去の日時を設定して due 状態にする
    """
    scenario_id = str(uuid.uuid4())
    scenario = ScenarioModel(
        id=scenario_id,
        name="テストシナリオ",
        trigger_type="manual",
        is_active=True,
    )
    db_session.add(scenario)
    db_session.flush()

    steps = []
    for i in range(1, num_steps + 1):
        step = ScenarioStepModel(
            id=str(uuid.uuid4()),
            scenario_id=scenario_id,
            step_order=i,
            delay_minutes=0,
            message_type="text",
            message_content=f"ステップ {i} のメッセージ",
        )
        db_session.add(step)
        steps.append(step)
    db_session.flush()

    # next_delivery_at を過去に設定して due 状態にする
    past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    enrollment = ScenarioEnrollmentModel(
        id=str(uuid.uuid4()),
        scenario_id=scenario_id,
        target_id="user_001",
        current_step_order=0,
        status="active",
        next_delivery_at=past_time,
    )
    db_session.add(enrollment)
    db_session.flush()

    return scenario, steps, enrollment


def test_due_enrollment_step_is_delivered(db_session) -> None:
    """due な enrollment のステップが配信されることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト用 mock connector
        scenario, steps, enrollment: テストデータ
        result: process_step_deliveries の実行結果

    Note:
        - is_within_delivery_window を mock して常に True にする
    """
    connector = _MockDeliveryConnector()
    _scenario, _steps, _enrollment = _create_scenario_data(db_session, num_steps=2)

    with patch(
        "app.workers.step_delivery.is_within_delivery_window",
        return_value=True,
    ):
        result = process_step_deliveries(db_session, connector)

    assert result["processed_count"] >= 1
    assert result["error_count"] == 0
    assert connector.call_count >= 1
    assert connector.last_action == "scenario.deliver"


def test_step_progression_updates_enrollment(db_session) -> None:
    """ステップ進行で current_step_order と next_delivery_at が更新されることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト用 mock connector
        enrollment: 対象の enrollment

    Note:
        - current_step_order が 0 → 1 に進む
        - next_delivery_at が再計算される
    """
    connector = _MockDeliveryConnector()
    _scenario, _steps, enrollment = _create_scenario_data(db_session, num_steps=3)

    with patch(
        "app.workers.step_delivery.is_within_delivery_window",
        return_value=True,
    ):
        process_step_deliveries(db_session, connector)

    db_session.refresh(enrollment)
    # ステップが進行している
    assert enrollment.current_step_order == 1
    # 次のステップがあるため next_delivery_at が設定される
    assert enrollment.next_delivery_at is not None


def test_final_step_completes_enrollment(db_session) -> None:
    """最終ステップ配信後に status が completed になることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト用 mock connector
        enrollment: 対象の enrollment

    Note:
        - ステップ数 1 のシナリオで 1 回配信すると completed になる
    """
    connector = _MockDeliveryConnector()
    _scenario, _steps, enrollment = _create_scenario_data(db_session, num_steps=1)

    with patch(
        "app.workers.step_delivery.is_within_delivery_window",
        return_value=True,
    ):
        process_step_deliveries(db_session, connector)

    db_session.refresh(enrollment)
    assert enrollment.status == "completed"


def test_failure_increments_retry_count(db_session) -> None:
    """配信失敗時に retry_count がインクリメントされることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト用失敗 mock connector
        enrollment: 対象の enrollment

    Note:
        - 失敗レスポンスで retry_count が 0 → 1 に増える
    """
    connector = _MockFailConnector()
    _scenario, _steps, enrollment = _create_scenario_data(db_session, num_steps=2)

    with patch(
        "app.workers.step_delivery.is_within_delivery_window",
        return_value=True,
    ):
        process_step_deliveries(db_session, connector)

    db_session.refresh(enrollment)
    assert enrollment.retry_count >= 1
    assert enrollment.status == "active"


def test_max_retries_exceeded_fails_enrollment(db_session) -> None:
    """max_retries 超過で status が failed になることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト用失敗 mock connector
        enrollment: 対象の enrollment

    Note:
        - retry_count を max_retries に設定してから失敗させると failed に遷移する
    """
    connector = _MockFailConnector()
    _scenario, _steps, enrollment = _create_scenario_data(db_session, num_steps=2)

    # retry_count を max_retries に設定（次の失敗で超過する）
    enrollment.retry_count = enrollment.max_retries
    db_session.flush()

    with patch(
        "app.workers.step_delivery.is_within_delivery_window",
        return_value=True,
    ):
        process_step_deliveries(db_session, connector)

    db_session.refresh(enrollment)
    assert enrollment.status == "failed"
