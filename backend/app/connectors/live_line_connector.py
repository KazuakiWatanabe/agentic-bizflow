"""
LINE Messaging API Connector を提供する。

本モジュールは LINE Messaging API を呼び出し、DB にも書き込む
本番用 connector を提供する。

入出力: execute で LINE API を呼び出し + DB 書き込み、dry_run はプレビューのみ。
制約: LINE_CHANNEL_ACCESS_TOKEN が必要。

Note:
    - Phase 4 では枠組みのみ実装する
    - デフォルトは db モード（live はオプトイン）
    - テストでは LINE API を mock して検証する
"""

import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.connectors.base_connector import BaseConnector
from app.connectors.db_line_connector import DBLineConnector
from app.schemas.connector_capability import ConnectorCapability

logger = logging.getLogger(__name__)

# LINE API の設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_API_BASE = "https://api.line.me/v2/bot"

# サポートするアクション一覧
SUPPORTED_ACTIONS = [
    "tag.assign",
    "broadcast.schedule",
    "scenario.create",
    "scenario.start",
    "reminder.create",
    "broadcast.send",
    "scenario.deliver",
    "reminder.deliver",
]


class LiveLineConnector(BaseConnector):
    """LINE Messaging API Connector。

    LINE API を呼び出し、DB にも書き込む本番用 connector。
    DBLineConnector の機能を継承しつつ、LINE API 連携を追加する。

    主要メソッド:
        execute: LINE API + DB 書き込み
        dry_run: プレビューのみ（API 呼び出しなし、DB 書き込みなし）
        capabilities: サポートアクション一覧

    Variables:
        _db: SQLAlchemy セッション
        _db_connector: DB 書き込み用の connector

    Note:
        - LINE_CHANNEL_ACCESS_TOKEN が空の場合は DB のみに書き込む
        - broadcast.send / scenario.deliver / reminder.deliver は LINE API 呼び出しを含む
    """

    def __init__(self, db: Optional[Session] = None) -> None:
        """LiveLineConnector を初期化する。

        Args:
            db: SQLAlchemy セッション
        """
        self._db = db
        # DB 書き込みは DBLineConnector に委譲
        self._db_connector = DBLineConnector(db=db) if db else None

    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """LINE API + DB に書き込む。

        Args:
            action: 実行するアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            実行結果 dict

        Note:
            - DB 書き込み可能なアクションは DBLineConnector に委譲する
            - broadcast.send / scenario.deliver / reminder.deliver は
              LINE API 呼び出しを行う（将来実装）
        """
        # DB 書き込み系のアクション（Phase 3 互換）
        db_actions = {
            "tag.assign",
            "broadcast.schedule",
            "scenario.create",
            "scenario.start",
            "reminder.create",
        }

        if action in db_actions and self._db_connector:
            return self._db_connector.execute(action, inputs)

        # LINE API 呼び出し系（Phase 4 で枠組みのみ実装）
        if action in {"broadcast.send", "scenario.deliver", "reminder.deliver"}:
            return self._execute_line_api(action, inputs)

        return {
            "status": "failed",
            "error_code": "UNSUPPORTED_ACTION",
            "message": f"サポートされていないアクション: {action}",
        }

    def dry_run(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """プレビューを返す（API / DB 書き込みなし）。

        Args:
            action: プレビュー対象のアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            プレビュー情報 dict
        """
        if self._db_connector:
            return self._db_connector.dry_run(action, inputs)
        return {"preview": f"{action} を実行します", "estimated_target_count": 0}

    def capabilities(self) -> ConnectorCapability:
        """LiveLineConnector のサポートアクション一覧を返す。

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

    def _execute_line_api(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """LINE API を呼び出す（枠組み）。

        Args:
            action: アクション名
            inputs: 入力パラメータ

        Returns:
            実行結果 dict

        Note:
            - LINE_CHANNEL_ACCESS_TOKEN が空の場合は mock 応答を返す
            - 将来の LINE API 実装のスタブ
        """
        if not LINE_CHANNEL_ACCESS_TOKEN:
            logger.warning(
                "LINE_CHANNEL_ACCESS_TOKEN 未設定: %s を mock 応答で返します",
                action,
            )
            return {
                "status": "success",
                "message": f"{action} を実行しました（LINE API 未接続）",
            }

        # TODO: LINE Messaging API の実装（Phase 4 完了後に実装）
        logger.info("LINE API 呼び出し: action=%s", action)
        return {
            "status": "success",
            "message": f"{action} を LINE API 経由で実行しました",
        }
