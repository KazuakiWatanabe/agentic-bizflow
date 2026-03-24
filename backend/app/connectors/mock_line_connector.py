"""
LINE 向け Mock Connector を提供する。

本モジュールは 5 種類の workload kind に対応する mock 実装を提供する。
実際の LINE API は呼び出さず、成功レスポンスを返す。

入出力: execute / dry_run で action 名と inputs を受け取り、mock レスポンスを返す。
制約: 外部通信は一切行わない。

Note:
    - Phase 2.5 の検証用途に限定する
    - 将来の本番 LINE connector に置き換える想定
"""

from typing import Any, Dict

from app.connectors.base_connector import BaseConnector
from app.schemas.connector_capability import ConnectorCapability

# --- サポートするアクション一覧 ---
SUPPORTED_ACTIONS = [
    "tag.assign",
    "broadcast.schedule",
    "scenario.create",
    "scenario.start",
    "reminder.create",
]

# --- アクション別の mock プレビューメッセージ ---
PREVIEW_MESSAGES: Dict[str, str] = {
    "tag.assign": "対象ユーザーにタグを付与します",
    "broadcast.schedule": "一斉配信を予約します",
    "scenario.create": "ステップ配信シナリオを作成します",
    "scenario.start": "対象ユーザーへのシナリオ配信を開始します",
    "reminder.create": "リマインダーを作成します",
}

# --- アクション別の mock 成功メッセージ ---
SUCCESS_MESSAGES: Dict[str, str] = {
    "tag.assign": "タグを付与しました",
    "broadcast.schedule": "配信を予約しました",
    "scenario.create": "シナリオを作成しました",
    "scenario.start": "シナリオ配信を開始しました",
    "reminder.create": "リマインダーを作成しました",
}


class MockLineConnector(BaseConnector):
    """LINE API の Mock Connector。

    5 種類の workload kind（tag.assign / broadcast.schedule /
    scenario.create / scenario.start / reminder.create）に対応する。
    実際の LINE API は呼び出さず、mock レスポンスを返す。

    主要メソッド:
        execute: mock の成功レスポンスを返す
        dry_run: mock のプレビュー情報を返す
        capabilities: サポートするアクション一覧を返す

    Note:
        - 外部通信は一切行わない
        - サポート外のアクションは failed を返す
    """

    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """mock の本実行を行い、成功レスポンスを返す。

        Args:
            action: 実行するアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            status と message を含む dict

        Variables:
            message:
                アクションに対応する成功メッセージ。

        Note:
            - サポート外のアクションは status="failed" を返す
        """
        if action not in SUPPORTED_ACTIONS:
            return {
                "status": "failed",
                "error_code": "UNSUPPORTED_ACTION",
                "message": f"サポートされていないアクション: {action}",
            }

        # アクションに対応する成功メッセージを取得
        message = SUCCESS_MESSAGES.get(action, "実行しました")
        return {"status": "success", "message": message}

    def dry_run(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """mock の dry-run を行い、プレビュー情報を返す。

        Args:
            action: プレビュー対象のアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            preview と estimated_target_count を含む dict

        Variables:
            preview:
                アクションに対応するプレビューメッセージ。

        Note:
            - 外部通信は一切行わない
            - estimated_target_count は mock 値として 10 を返す
        """
        # アクションに対応するプレビューメッセージを取得
        preview = PREVIEW_MESSAGES.get(action, f"{action} を実行します")
        return {"preview": preview, "estimated_target_count": 10}

    def capabilities(self) -> ConnectorCapability:
        """LINE Mock Connector のサポートアクション一覧を返す。

        Returns:
            ConnectorCapability モデル
        """
        return ConnectorCapability(
            connector="line",
            supported_actions=SUPPORTED_ACTIONS,
            supports_dry_run=True,
            supports_rollback=False,
            supports_schedule=True,
        )
