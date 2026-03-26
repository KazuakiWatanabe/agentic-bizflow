"""
broadcast 配信 Worker を提供する。

本モジュールは scheduled な broadcasts を送信する定期処理を実装する。

入出力: DB セッションと connector を受け取り、due な broadcasts を送信する。
制約: scheduled_at が未来の broadcasts は処理しない。

Note:
    - scheduled → sending → sent の遷移
    - 失敗時は status=failed に遷移する
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.connectors.base_connector import BaseConnector
from app.db.models import BroadcastModel
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.idempotency_repo import IdempotencyRepository

logger = logging.getLogger(__name__)


def process_scheduled_broadcasts(
    db: Session,
    connector: BaseConnector,
) -> Dict[str, Any]:
    """scheduled な broadcasts を送信する。

    Args:
        db: SQLAlchemy セッション
        connector: 配信用の connector

    Returns:
        処理結果の dict（processed_count, error_count）

    Variables:
        now: 現在の UTC 日時
        broadcasts: 配信対象の broadcast リスト
        processed: 処理件数
        errors: エラー件数
    """
    now = datetime.now(timezone.utc)

    # due な broadcasts を取得
    broadcasts = (
        db.query(BroadcastModel)
        .filter(
            BroadcastModel.status == "scheduled",
            BroadcastModel.scheduled_at <= now,
        )
        .all()
    )

    processed = 0
    errors = 0

    for broadcast in broadcasts:
        try:
            _process_broadcast(db, connector, broadcast, now)
            processed += 1
        except Exception as exc:
            errors += 1
            logger.error(
                "broadcast delivery エラー: id=%s, error=%s",
                broadcast.id,
                str(exc),
            )

    db.commit()
    return {"processed_count": processed, "error_count": errors}


def _process_broadcast(
    db: Session,
    connector: BaseConnector,
    broadcast: BroadcastModel,
    now: datetime,
) -> None:
    """1 件の broadcast を送信する。

    Args:
        db: SQLAlchemy セッション
        connector: 配信用の connector
        broadcast: 対象の broadcast
        now: 現在日時

    Note:
        - 冪等性チェックを行う
        - sending → sent または sending → failed に遷移する
    """
    # 冪等性チェック
    idem_key = f"broadcast_{broadcast.id}"
    if IdempotencyRepository.is_processed(db, idem_key):
        AuditRepository.log(
            db,
            action="step_skipped",
            detail={"broadcast_id": broadcast.id, "reason": "idempotency"},
        )
        return

    # status を sending に更新
    broadcast.status = "sending"
    db.flush()

    # connector で送信
    result = connector.execute(
        "broadcast.send",
        {
            "broadcast_id": broadcast.id,
            "title": broadcast.title,
            "message_content": broadcast.message_content,
            "target_type": broadcast.target_type,
        },
    )

    if result.get("status") == "success":
        broadcast.status = "sent"
        broadcast.sent_at = now
        broadcast.success_count = result.get("success_count", 0)
        IdempotencyRepository.mark_processed(db, idem_key, broadcast.id, "")

        AuditRepository.log(
            db,
            action="step_executed",
            detail={"broadcast_id": broadcast.id, "status": "sent"},
        )
    else:
        broadcast.status = "failed"
        AuditRepository.log(
            db,
            action="step_failed",
            detail={
                "broadcast_id": broadcast.id,
                "error": result.get("message", "unknown"),
            },
        )
