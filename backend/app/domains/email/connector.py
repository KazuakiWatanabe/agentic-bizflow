"""
Email ドメインの DB 書き込みコネクタを提供する。

本モジュールは Email 関連の workload kind に対応し、
実行時に DB にドメインレコードを書き込む connector を提供する。

入出力: execute / dry_run で action 名と inputs を受け取り、結果 dict を返す。
制約: 外部 SMTP サーバーへの送信は行わない。DB 書き込みのみ。

Note:
    - execute() は DB にレコードを書き込む（commit は呼び出し側の責務）
    - dry_run() は DB に書き込まず、プレビュー情報を返す
    - 実際の SMTP 送信は Phase 6 以降の責務
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.connectors.base_connector import BaseConnector
from app.db.models import EmailBroadcastModel, EmailTemplateModel
from app.schemas.connector_capability import ConnectorCapability

logger = logging.getLogger(__name__)

# サポートするアクション一覧
SUPPORTED_ACTIONS = [
    "email.broadcast.schedule",
    "email.template.create",
]


class EmailConnector(BaseConnector):
    """Email ドメインの DB 書き込みコネクタ。

    email.broadcast.schedule と email.template.create に対応し、
    execute 時に DB にレコードを書き込む。
    dry_run 時は書き込みを行わず、プレビュー情報を返す。

    主要メソッド:
        execute: DB にレコードを書き込む
        dry_run: プレビュー情報を返す（DB 書き込みなし）
        capabilities: サポートするアクション一覧を返す

    Variables:
        _db: SQLAlchemy セッション
        _smtp_config: SMTP 設定（将来の SMTP 送信用）

    Note:
        - commit は呼び出し側（route handler）の責務
        - execute 内では flush のみ行う
    """

    def __init__(
        self, db: Session, smtp_config: Optional[Dict[str, Any]] = None
    ) -> None:
        """EmailConnector を初期化する。

        Args:
            db: SQLAlchemy セッション
            smtp_config: SMTP 設定（将来の SMTP 送信用、現在は未使用）
        """
        # DB セッション
        self._db = db
        # SMTP 設定（将来用）
        self._smtp_config = smtp_config or {}

    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """workload ステップを本実行し、DB にレコードを書き込む。

        Args:
            action: 実行するアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            実行結果を含む dict（status, message, created_records 等）

        Note:
            - サポート外のアクションは status="failed" を返す
            - commit は行わない（呼び出し側の責務）
        """
        dispatch = {
            "email.broadcast.schedule": self._execute_broadcast_schedule,
            "email.template.create": self._execute_template_create,
        }
        handler = dispatch.get(action)
        if handler is None:
            return {
                "status": "failed",
                "error_code": "UNSUPPORTED_ACTION",
                "message": f"サポートされていないアクション: {action}",
            }
        return handler(inputs)

    def dry_run(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """副作用なしで実行プレビューを返す。

        Args:
            action: プレビュー対象のアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            プレビュー情報を含む dict

        Note:
            - DB への書き込みは一切行わない
        """
        preview_dispatch = {
            "email.broadcast.schedule": self._preview_broadcast_schedule,
            "email.template.create": self._preview_template_create,
        }
        handler = preview_dispatch.get(action)
        if handler is None:
            return {
                "preview": f"{action} を実行します",
                "estimated_target_count": 0,
            }
        return handler(inputs)

    def capabilities(self) -> ConnectorCapability:
        """Email Connector のサポートアクション一覧を返す。

        Returns:
            ConnectorCapability モデル
        """
        return ConnectorCapability(
            connector="email",
            supported_actions=SUPPORTED_ACTIONS,
            supports_dry_run=True,
            supports_rollback=False,
            supports_schedule=True,
        )

    def _execute_broadcast_schedule(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """email.broadcast.schedule を実行し、email_broadcasts に書き込む。

        Args:
            inputs: subject, body_html, from_address 等を含む入力パラメータ

        Returns:
            実行結果 dict

        Variables:
            subject: メール件名
            body_html: HTML 本文
            body_text: テキスト本文（任意）
            from_address: 送信元アドレス
            target_type: 対象種別（all / segment）
            scheduled_at: 配信予約日時

        Note:
            - status=scheduled で INSERT する
        """
        subject = inputs.get("subject", "一斉メール配信")
        body_html = inputs.get("body_html", "<p>本文</p>")
        body_text = inputs.get("body_text")
        from_address = inputs.get("from_address", "noreply@example.com")
        target_type = inputs.get("target_type", "all")
        scheduled_at_str = inputs.get("scheduled_at")
        execution_plan_id = inputs.get("execution_plan_id")

        # 配信予約日時のパース
        scheduled_at = None
        if scheduled_at_str:
            try:
                scheduled_at = datetime.fromisoformat(scheduled_at_str)
            except (ValueError, TypeError):
                scheduled_at = None

        # レコード ID
        record_id = str(uuid.uuid4())

        record = EmailBroadcastModel(
            id=record_id,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            from_address=from_address,
            target_type=target_type,
            status="scheduled",
            scheduled_at=scheduled_at or datetime.now(timezone.utc),
            execution_plan_id=execution_plan_id,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(record)
        self._db.flush()

        logger.info("email.broadcast.schedule 実行: subject=%s", subject)
        return {
            "status": "success",
            "message": "メール配信を予約しました",
            "created_records": {"email_broadcasts": 1},
            "broadcast_id": record_id,
        }

    def _execute_template_create(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """email.template.create を実行し、email_templates に書き込む。

        Args:
            inputs: name, subject, body_html 等を含む入力パラメータ

        Returns:
            実行結果 dict

        Variables:
            name: テンプレート名
            subject: メール件名
            body_html: HTML 本文
            body_text: テキスト本文（任意）
        """
        name = inputs.get("name", "新規テンプレート")
        subject = inputs.get("subject", "件名")
        body_html = inputs.get("body_html", "<p>本文</p>")
        body_text = inputs.get("body_text")

        # レコード ID
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        record = EmailTemplateModel(
            id=record_id,
            name=name,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            created_at=now,
            updated_at=now,
        )
        self._db.add(record)
        self._db.flush()

        logger.info("email.template.create 実行: name=%s", name)
        return {
            "status": "success",
            "message": "メールテンプレートを作成しました",
            "created_records": {"email_templates": 1},
            "template_id": record_id,
        }

    @staticmethod
    def _preview_broadcast_schedule(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """email.broadcast.schedule の dry-run プレビューを返す。

        Args:
            inputs: アクションの入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        subject = inputs.get("subject", "一斉メール配信")
        return {
            "preview": f"メール配信を予約します: {subject}",
            "estimated_target_count": 0,
        }

    @staticmethod
    def _preview_template_create(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """email.template.create の dry-run プレビューを返す。

        Args:
            inputs: アクションの入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        name = inputs.get("name", "新規テンプレート")
        return {
            "preview": f"メールテンプレートを作成します: {name}",
            "estimated_target_count": 0,
        }
