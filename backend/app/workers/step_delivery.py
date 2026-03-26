"""
scenario step 配信 Worker を提供する。

本モジュールは scenario_enrollments の due な step を配信する定期処理を実装する。

入出力: DB セッションと connector を受け取り、due な enrollment の step を配信する。
制約: 配信ウィンドウ（9:00-23:00 JST）外ではスキップする。

Note:
    - next_delivery_at ≤ now の enrollment を取得して配信する
    - 最終ステップ後に status=completed に遷移する
    - 失敗時は retry_count をインクリメントし、上限超過で failed にする
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.connectors.base_connector import BaseConnector
from app.db.models import ScenarioEnrollmentModel, ScenarioStepModel
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.idempotency_repo import IdempotencyRepository
from app.workers.delivery_window import (
    enforce_delivery_window,
    is_within_delivery_window,
)

logger = logging.getLogger(__name__)

# バックオフ計算: min(5 * 2^retry_count, 60) 分
MAX_BACKOFF_MINUTES = 60


def _backoff_minutes(retry_count: int) -> int:
    """再試行のバックオフ時間（分）を計算する。

    Args:
        retry_count: 現在の再試行回数

    Returns:
        バックオフ時間（分）
    """
    return min(5 * (2**retry_count), MAX_BACKOFF_MINUTES)


def process_step_deliveries(
    db: Session,
    connector: BaseConnector,
) -> Dict[str, Any]:
    """due な scenario step を配信する。

    Args:
        db: SQLAlchemy セッション
        connector: 配信用の connector

    Returns:
        処理結果の dict（processed_count, error_count）

    Variables:
        now: 現在の UTC 日時
        enrollments: 配信対象の enrollment リスト
        processed: 処理件数
        errors: エラー件数

    Note:
        - 配信ウィンドウ外ではスキップする
        - 冪等性チェックを行う
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

    # due な enrollment を取得
    enrollments = (
        db.query(ScenarioEnrollmentModel)
        .filter(
            ScenarioEnrollmentModel.status == "active",
            ScenarioEnrollmentModel.next_delivery_at <= now,
        )
        .all()
    )

    processed = 0
    errors = 0

    for enrollment in enrollments:
        try:
            _process_enrollment(db, connector, enrollment, now)
            processed += 1
        except Exception as exc:
            errors += 1
            logger.error(
                "step delivery エラー: enrollment_id=%s, error=%s",
                enrollment.id,
                str(exc),
            )

    db.commit()
    return {"processed_count": processed, "error_count": errors}


def _process_enrollment(
    db: Session,
    connector: BaseConnector,
    enrollment: ScenarioEnrollmentModel,
    now: datetime,
) -> None:
    """1 件の enrollment の次ステップを配信する。

    Args:
        db: SQLAlchemy セッション
        connector: 配信用の connector
        enrollment: 対象の enrollment
        now: 現在日時

    Note:
        - 次ステップが存在しなければ completed に遷移する
        - 冪等性チェックでスキップする場合がある
    """
    # 次ステップを取得
    next_step_order = enrollment.current_step_order + 1
    next_step = (
        db.query(ScenarioStepModel)
        .filter_by(scenario_id=enrollment.scenario_id, step_order=next_step_order)
        .first()
    )

    if next_step is None:
        # 最終ステップ完了 → completed
        enrollment.status = "completed"
        enrollment.updated_at = now
        AuditRepository.log(
            db,
            action="step_executed",
            detail={"enrollment_id": enrollment.id, "status": "completed"},
        )
        return

    # 冪等性チェック用のキーを生成
    idem_key = f"scenario_{enrollment.id}_step_{next_step_order}"
    if IdempotencyRepository.is_processed(db, idem_key):
        AuditRepository.log(
            db,
            action="step_skipped",
            detail={"enrollment_id": enrollment.id, "reason": "idempotency"},
        )
        return

    # connector で配信
    result = connector.execute(
        "scenario.deliver",
        {
            "enrollment_id": enrollment.id,
            "target_id": enrollment.target_id,
            "message_content": next_step.message_content,
            "message_type": next_step.message_type,
        },
    )

    if result.get("status") == "success":
        # 成功 → ステップ進行
        enrollment.current_step_order = next_step_order
        enrollment.retry_count = 0

        # 次の次ステップが存在するか確認
        further_step = (
            db.query(ScenarioStepModel)
            .filter_by(
                scenario_id=enrollment.scenario_id, step_order=next_step_order + 1
            )
            .first()
        )
        if further_step is None:
            enrollment.status = "completed"
            enrollment.next_delivery_at = None
        else:
            # next_delivery_at を再計算（配信ウィンドウ適用）
            raw_next = now + timedelta(minutes=further_step.delay_minutes)
            enrollment.next_delivery_at = enforce_delivery_window(raw_next)

        enrollment.updated_at = now
        IdempotencyRepository.mark_processed(
            db, idem_key, f"step_{next_step_order}", ""
        )

        AuditRepository.log(
            db,
            action="step_executed",
            detail={
                "enrollment_id": enrollment.id,
                "step_order": next_step_order,
                "status": "success",
            },
        )
    else:
        # 失敗 → retry
        enrollment.retry_count += 1
        if enrollment.retry_count > enrollment.max_retries:
            enrollment.status = "failed"
            AuditRepository.log(
                db,
                action="step_failed",
                detail={
                    "enrollment_id": enrollment.id,
                    "reason": "max_retries_exceeded",
                },
            )
        else:
            backoff = _backoff_minutes(enrollment.retry_count)
            raw_next = now + timedelta(minutes=backoff)
            enrollment.next_delivery_at = enforce_delivery_window(raw_next)
            AuditRepository.log(
                db,
                action="step_retried",
                detail={
                    "enrollment_id": enrollment.id,
                    "retry_count": enrollment.retry_count,
                    "backoff_minutes": backoff,
                },
            )
        enrollment.updated_at = now
