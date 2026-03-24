"""
内部ジョブキュー用 Mock Connector を提供する。

本モジュールは内部バッチジョブ系のアクションに対応する mock 実装を提供する。
実際のジョブキューは使用せず、成功レスポンスを返す。

入出力: execute / dry_run で action 名と inputs を受け取り、mock レスポンスを返す。
制約: 外部通信は一切行わない。

Note:
    - Phase 2.5 の検証用途に限定する
    - 将来の Cloud Tasks / Pub/Sub connector に置き換える想定
"""

from typing import Any, Dict

from app.connectors.base_connector import BaseConnector
from app.schemas.connector_capability import ConnectorCapability

# --- サポートするアクション一覧 ---
SUPPORTED_ACTIONS = [
    "job.enqueue",
    "job.status",
]


class MockInternalJobConnector(BaseConnector):
    """内部ジョブキューの Mock Connector。

    ジョブの投入と状態確認に対応する mock 実装を提供する。
    実際のジョブキューは使用しない。

    主要メソッド:
        execute: mock のジョブ投入レスポンスを返す
        dry_run: mock のプレビュー情報を返す
        capabilities: サポートするアクション一覧を返す

    Note:
        - 外部通信は一切行わない
    """

    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """mock のジョブ実行を行い、成功レスポンスを返す。

        Args:
            action: 実行するアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            status と message を含む dict

        Note:
            - サポート外のアクションは status="failed" を返す
        """
        if action not in SUPPORTED_ACTIONS:
            return {
                "status": "failed",
                "error_code": "UNSUPPORTED_ACTION",
                "message": f"サポートされていないアクション: {action}",
            }
        return {"status": "success", "message": f"ジョブを実行しました: {action}"}

    def dry_run(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """mock の dry-run を行い、プレビュー情報を返す。

        Args:
            action: プレビュー対象のアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            preview を含む dict

        Note:
            - 外部通信は一切行わない
        """
        return {"preview": f"ジョブ {action} を実行します", "estimated_target_count": 0}

    def capabilities(self) -> ConnectorCapability:
        """内部ジョブ Mock Connector のサポートアクション一覧を返す。

        Returns:
            ConnectorCapability モデル
        """
        return ConnectorCapability(
            connector="internal_job",
            supported_actions=SUPPORTED_ACTIONS,
            supports_dry_run=True,
            supports_rollback=False,
            supports_schedule=False,
        )
