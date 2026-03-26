"""
テンプレートコネクタ。

本モジュールは新しいドメイン用の connector テンプレートを提供する。
BaseConnector を継承し、execute / dry_run / capabilities のプレースホルダを定義する。

入出力: execute / dry_run で action 名と inputs を受け取り、結果 dict を返す。
制約: Agent 層には依存しない。

Note:
    - 新しいドメインを作成する際はこのファイルをコピーして実装する
    - execute() / dry_run() に独自のアクション処理を追加する
"""

import logging
from typing import Any, Dict

from app.connectors.base_connector import BaseConnector
from app.schemas.connector_capability import ConnectorCapability

logger = logging.getLogger(__name__)

# サポートするアクション一覧（テンプレートでは空）
SUPPORTED_ACTIONS: list[str] = []


class TemplateConnector(BaseConnector):
    """テンプレートコネクタ。

    BaseConnector を継承した connector のテンプレート。
    新しいドメインではこのクラスをコピーしてアクション処理を実装する。

    主要メソッド:
        execute: workload ステップを本実行する
        dry_run: 副作用なしでプレビューを返す
        capabilities: サポートアクション一覧を返す

    Note:
        - テンプレートのため、全アクションに対して未サポートエラーを返す
    """

    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """workload ステップを本実行する（プレースホルダ）。

        Args:
            action: 実行するアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            実行結果を含む dict

        Note:
            - テンプレートでは全アクションに対して未サポートエラーを返す
        """
        return {
            "status": "failed",
            "error_code": "UNSUPPORTED_ACTION",
            "message": f"テンプレート: サポートされていないアクション: {action}",
        }

    def dry_run(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """副作用なしでプレビューを返す（プレースホルダ）。

        Args:
            action: プレビュー対象のアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            プレビュー情報を含む dict

        Note:
            - テンプレートでは汎用プレビューを返す
        """
        return {
            "preview": f"テンプレート: {action} を実行します",
            "estimated_target_count": 0,
        }

    def capabilities(self) -> ConnectorCapability:
        """テンプレートコネクタのサポートアクション一覧を返す。

        Returns:
            ConnectorCapability モデル
        """
        return ConnectorCapability(
            connector="template",
            supported_actions=SUPPORTED_ACTIONS,
            supports_dry_run=True,
            supports_rollback=False,
            supports_schedule=False,
        )
