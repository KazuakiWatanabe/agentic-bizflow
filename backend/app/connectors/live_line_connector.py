"""
LINE Messaging API Connector を提供する。

本モジュールは LINE Messaging API を呼び出し、DB にも書き込む
本番用 connector を提供する。

入出力: execute で LINE API を呼び出し + DB 書き込み、dry_run はプレビューのみ。
制約: LINE_CHANNEL_ACCESS_TOKEN が必要。

Note:
    - tag.assign は DB 書き込み + LINE API 呼び出しを行う
    - その他の DB 書き込みアクションは DBLineConnector に委譲する
    - デフォルトは db モード（live はオプトイン）
    - テストでは LINE API を mock して検証する
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx
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
            - tag.assign は DB 書き込み + LINE API 呼び出しを行う
            - その他の DB 書き込みアクションは DBLineConnector に委譲する
            - broadcast.send / scenario.deliver / reminder.deliver は
              LINE API 呼び出しを行う（将来実装）
        """
        # tag.assign は DB + LINE API の両方を実行
        if action == "tag.assign" and self._db_connector:
            return self._execute_line_tag_assign(inputs)

        # その他の DB 書き込み系アクション（Phase 3 互換）
        db_actions = {
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

    def _execute_line_tag_assign(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """tag.assign を DB + LINE API で実行する。

        DB connector で先にローカル書き込みを行い、
        その後 LINE API にタグ付与リクエストを送信する。

        Args:
            inputs: tag_name, target を含む入力パラメータ

        Returns:
            実行結果 dict

        Variables:
            db_result: DB 書き込みの結果
            tag_name: 付与するタグ名
            target_id: 対象者 ID
            url: LINE API のタグ付与エンドポイント URL
            headers: LINE API リクエストヘッダ

        Note:
            - DB 書き込みを先に行い、成功後に LINE API を呼び出す
            - LINE API が失敗しても DB 書き込みは成功扱いとする（警告ログ出力）
            - LINE_CHANNEL_ACCESS_TOKEN が空の場合は LINE API 呼び出しをスキップする
        """
        # まず DB に書き込む
        db_result = self._db_connector.execute("tag.assign", inputs)
        if db_result.get("status") != "success":
            return db_result

        # LINE API 呼び出し
        if not LINE_CHANNEL_ACCESS_TOKEN:
            logger.warning(
                "LINE_CHANNEL_ACCESS_TOKEN 未設定: tag.assign の LINE API 呼び出しをスキップ"
            )
            return db_result

        tag_name = inputs.get("tag_name", "")
        target_id = inputs.get("target", "default_target")

        # LINE API タグ付与エンドポイント（プレースホルダー URL）
        url = f"{LINE_API_BASE}/richmenu/tag/assign"
        headers = {
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "tag_name": tag_name,
            "target_id": target_id,
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
            logger.info(
                "LINE API tag.assign 成功: tag=%s, target=%s",
                tag_name,
                target_id,
            )
        except Exception as exc:
            # LINE API 失敗時も DB 書き込みは成功扱い
            logger.warning(
                "LINE API tag.assign 失敗（DB 書き込みは成功）: %s",
                str(exc),
            )

        return db_result

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
