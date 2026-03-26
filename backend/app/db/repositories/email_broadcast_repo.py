"""
メール一斉配信の CRUD リポジトリを提供する。

本モジュールは email_broadcasts テーブルに対する操作を提供する。

入出力: Session と入力パラメータを受け取り、ORM モデルを返す。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - create では status=scheduled で INSERT する
    - get_scheduled_due は配信時刻到来済みのレコードを返す
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import EmailBroadcastModel


class EmailBroadcastRepository:
    """メール一斉配信の CRUD 操作を提供する。

    主要メソッド:
        create: 配信予約を作成する
        get_scheduled_due: 配信時刻到来済みのレコードを取得する

    Note:
        - commit は行わない
    """

    @staticmethod
    def create(
        db: Session,
        subject: str,
        body_html: str,
        from_address: str,
        body_text: Optional[str] = None,
        target_type: str = "all",
        scheduled_at: Optional[datetime] = None,
        execution_plan_id: Optional[str] = None,
    ) -> EmailBroadcastModel:
        """メール配信予約を作成する。

        Args:
            db: SQLAlchemy セッション
            subject: メール件名
            body_html: HTML 本文
            from_address: 送信元メールアドレス
            body_text: テキスト本文（任意）
            target_type: 配信対象種別（all / segment）
            scheduled_at: 配信予約日時
            execution_plan_id: 生成元の plan ID

        Returns:
            EmailBroadcastModel インスタンス

        Note:
            - status は 'scheduled' で作成する
            - scheduled_at 未指定時は現在時刻をデフォルトとする
        """
        record = EmailBroadcastModel(
            id=str(uuid.uuid4()),
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
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def get_scheduled_due(db: Session) -> List[EmailBroadcastModel]:
        """配信時刻到来済みのメール配信レコードを取得する。

        status='scheduled' かつ scheduled_at が現在時刻以前のレコードを返す。

        Args:
            db: SQLAlchemy セッション

        Returns:
            EmailBroadcastModel のリスト

        Note:
            - scheduled_at <= now の条件でフィルタする
        """
        now = datetime.now(timezone.utc)
        return (
            db.query(EmailBroadcastModel)
            .filter(
                EmailBroadcastModel.status == "scheduled",
                EmailBroadcastModel.scheduled_at <= now,
            )
            .all()
        )
