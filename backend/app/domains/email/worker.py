"""
Email ドメインのワーカー関数を提供する。

本モジュールは定期実行されるメール配信処理を提供する。
Scheduler から呼び出され、スケジュール済みの一斉メール配信を処理する。

入出力: DB セッションと connector を受け取り、処理結果 dict を返す。
制約: Agent 層には依存しない。

Note:
    - 冪等性は IdempotencyRepository で担保する
    - 監査ログは AuditRepository で記録する
    - commit は worker 側で行う
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.connectors.base_connector import BaseConnector
from app.db.models import EmailBroadcastModel
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.idempotency_repo import IdempotencyRepository

logger = logging.getLogger(__name__)


def process_scheduled_email_broadcasts(
    db: Session,
    connector: BaseConnector,
) -> Dict[str, Any]:
    """スケジュール済みのメール一斉配信を処理する。

    email_broadcasts テーブルから status='scheduled' かつ
    scheduled_at が現在時刻以前のレコードを取得し、配信処理を行う。

    Args:
        db: SQLAlchemy セッション
        connector: Email ドメイン用の connector

    Returns:
        処理結果 dict（processed_count, error_count を含む）

    Note:
        - 各レコードの処理: scheduled → sending → sent / failed
        - 冪等性は idempotency_key で担保する
        - 処理結果は監査ログに記録する
    """
    now = datetime.now(timezone.utc)

    # 処理件数カウンタ
    processed_count = 0
    # エラー件数カウンタ
    error_count = 0

    # 処理対象レコードの取得
    due_broadcasts = (
        db.query(EmailBroadcastModel)
        .filter(
            EmailBroadcastModel.status == "scheduled",
            EmailBroadcastModel.scheduled_at <= now,
        )
        .all()
    )

    for broadcast in due_broadcasts:
        # 冪等性チェック用のキー
        idempotency_key = f"email_broadcast:{broadcast.id}"

        if IdempotencyRepository.is_processed(db, idempotency_key):
            logger.info("メール配信スキップ（処理済み）: broadcast_id=%s", broadcast.id)
            continue

        try:
            # ステータスを sending に更新
            broadcast.status = "sending"
            db.flush()

            # connector 経由で配信処理を実行
            result = connector.execute(
                "email.broadcast.send",
                {
                    "broadcast_id": broadcast.id,
                    "subject": broadcast.subject,
                    "body_html": broadcast.body_html,
                    "body_text": broadcast.body_text,
                    "from_address": broadcast.from_address,
                    "target_type": broadcast.target_type,
                },
            )

            if result.get("status") == "success":
                # 配信成功: ステータスを sent に更新
                broadcast.status = "sent"
                broadcast.sent_at = datetime.now(timezone.utc)
                broadcast.success_count = result.get("success_count", 0)
            else:
                # 配信失敗: ステータスを failed に更新
                broadcast.status = "failed"
                error_count += 1

            # 冪等性キーを記録
            IdempotencyRepository.mark_processed(
                db,
                idempotency_key=idempotency_key,
                step_id=broadcast.id,
                plan_id=broadcast.execution_plan_id or "",
            )

            # 監査ログを記録
            AuditRepository.log(
                db,
                action="email_broadcast_processed",
                detail={
                    "broadcast_id": broadcast.id,
                    "status": broadcast.status,
                    "subject": broadcast.subject,
                },
            )

            db.commit()
            processed_count += 1

        except Exception as exc:
            logger.error(
                "メール配信エラー: broadcast_id=%s, error=%s",
                broadcast.id,
                str(exc),
            )
            db.rollback()
            # ステータスを failed に更新
            broadcast.status = "failed"
            db.commit()
            error_count += 1

    logger.info(
        "メール配信ワーカー完了: processed=%d, errors=%d",
        processed_count,
        error_count,
    )
    return {
        "processed_count": processed_count,
        "error_count": error_count,
    }
