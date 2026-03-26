"""
reminder 配信 Worker を提供する。

本モジュールは reminder_enrollments の未配信ステップを配信する定期処理を実装する。

入出力: DB セッションと connector を受け取り、due な reminder step を配信する。
制約: 配信ウィンドウ（9:00-23:00 JST）外ではスキップする。

Note:
    - target_date + offset_minutes ≤ now かつ未配信のステップを配信する
    - reminder_deliveries に配信記録を作成する
    - UNIQUE 制約で二重配信を防止する
    - 全ステップ完了後に enrollment を completed にする
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.connectors.base_connector import BaseConnector
from app.db.models import (
    ReminderDeliveryModel,
    ReminderEnrollmentModel,
    ReminderStepModel,
)
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.idempotency_repo import IdempotencyRepository
from app.workers.delivery_window import is_within_delivery_window

logger = logging.getLogger(__name__)


def process_reminder_deliveries(
    db: Session,
    connector: BaseConnector,
) -> Dict[str, Any]:
    """due な reminder step を配信する。

    Args:
        db: SQLAlchemy セッション
        connector: 配信用の connector

    Returns:
        処理結果の dict（processed_count, error_count）

    Variables:
        now: 現在の UTC 日時
        enrollments: 対象の enrollment リスト
        processed: 処理件数
        errors: エラー件数
    """
    now = datetime.now(timezone.utc)

    # 配信ウィンドウチェック
    if not is_within_delivery_window(now):
        logger.info("配信ウィンドウ外のためスキップ")
        return {
            "processed_count": 0,
            "error_count": 0,
            "skipped_reason": "outside_window",
        }

    # active な enrollment を取得
    enrollments = (
        db.query(ReminderEnrollmentModel)
        .filter(ReminderEnrollmentModel.status == "active")
        .all()
    )

    processed = 0
    errors = 0

    for enrollment in enrollments:
        try:
            count = _process_enrollment(db, connector, enrollment, now)
            processed += count
        except Exception as exc:
            errors += 1
            logger.error(
                "reminder delivery エラー: enrollment_id=%s, error=%s",
                enrollment.id,
                str(exc),
            )

    db.commit()
    return {"processed_count": processed, "error_count": errors}


def _process_enrollment(
    db: Session,
    connector: BaseConnector,
    enrollment: ReminderEnrollmentModel,
    now: datetime,
) -> int:
    """1 件の enrollment の due なステップを配信する。

    Args:
        db: SQLAlchemy セッション
        connector: 配信用の connector
        enrollment: 対象の enrollment
        now: 現在日時

    Returns:
        配信した件数

    Note:
        - target_date + offset_minutes ≤ now の未配信ステップを配信する
    """
    # reminder_steps を取得
    steps = (
        db.query(ReminderStepModel).filter_by(reminder_id=enrollment.reminder_id).all()
    )

    # 配信済みの step ID を取得
    delivered_step_ids = {
        d.reminder_step_id
        for d in (
            db.query(ReminderDeliveryModel).filter_by(enrollment_id=enrollment.id).all()
        )
    }

    delivered_count = 0
    total_steps = len(steps)

    for step in steps:
        # 既に配信済みならスキップ
        if step.id in delivered_step_ids:
            continue

        # due チェック: target_date + offset_minutes ≤ now
        due_time = enrollment.target_date + timedelta(minutes=step.offset_minutes)
        if due_time > now:
            continue

        # 冪等性チェック
        idem_key = f"reminder_{enrollment.id}_step_{step.id}"
        if IdempotencyRepository.is_processed(db, idem_key):
            continue

        # connector で配信
        result = connector.execute(
            "reminder.deliver",
            {
                "enrollment_id": enrollment.id,
                "target_id": enrollment.target_id,
                "message_content": step.message_content,
                "message_type": step.message_type,
            },
        )

        if result.get("status") == "success":
            # reminder_deliveries に INSERT
            try:
                delivery = ReminderDeliveryModel(
                    id=str(uuid.uuid4()),
                    enrollment_id=enrollment.id,
                    reminder_step_id=step.id,
                    delivered_at=now,
                )
                db.add(delivery)
                db.flush()
            except IntegrityError:
                db.rollback()
                logger.info(
                    "二重配信防止: enrollment=%s, step=%s", enrollment.id, step.id
                )
                continue

            IdempotencyRepository.mark_processed(db, idem_key, step.id, "")
            delivered_count += 1
            delivered_step_ids.add(step.id)

            AuditRepository.log(
                db,
                action="step_executed",
                detail={
                    "enrollment_id": enrollment.id,
                    "reminder_step_id": step.id,
                    "status": "delivered",
                },
            )

    # 全ステップ配信済みか確認
    if len(delivered_step_ids) >= total_steps and total_steps > 0:
        enrollment.status = "completed"
        enrollment.updated_at = now

    return delivered_count
