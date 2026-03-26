"""
定期処理 Scheduler を提供する。

本モジュールは APScheduler を使い、5 分間隔で 3 つの Worker を実行する。
FastAPI の lifespan event で起動/停止する。

入出力: アプリ起動時に Scheduler を開始し、シャットダウン時に停止する。
制約: SCHEDULER_ENABLED=false のとき Scheduler を起動しない。

Note:
    - 各処理の開始/終了/件数/エラーを worker_task_logs に記録する
    - 1 処理の失敗が他の処理に影響しない
"""

import logging
import os
import uuid
from datetime import datetime, timezone

from app.db.models import WorkerTaskLogModel
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Scheduler の有効/無効を環境変数で制御
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"

# APScheduler の間隔（分）
INTERVAL_MINUTES = 5

# グローバル Scheduler インスタンス
_scheduler = None


def _run_worker(task_name: str, worker_fn) -> None:
    """Worker を実行し、結果を worker_task_logs に記録する。

    Args:
        task_name: 処理名
        worker_fn: DB セッションと connector を受け取る Worker 関数

    Note:
        - 例外が発生しても他の Worker には影響しない
        - worker_task_logs に実行記録を残す
    """
    db = SessionLocal()
    try:
        # 実行ログを作成
        log_record = WorkerTaskLogModel(
            id=str(uuid.uuid4()),
            task_name=task_name,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        db.add(log_record)
        db.commit()

        # connector を構築
        from app.connectors.registry import get_line_connector

        connector = get_line_connector(db)

        # Worker 実行
        result = worker_fn(db, connector)

        # 完了ログを更新
        log_record.finished_at = datetime.now(timezone.utc)
        log_record.processed_count = result.get("processed_count", 0)
        log_record.error_count = result.get("error_count", 0)
        log_record.status = "completed"
        db.commit()

        logger.info(
            "%s 完了: processed=%d, errors=%d",
            task_name,
            log_record.processed_count,
            log_record.error_count,
        )
    except Exception as exc:
        logger.error("%s 失敗: %s", task_name, str(exc))
        try:
            log_record.finished_at = datetime.now(timezone.utc)
            log_record.status = "failed"
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def _run_step_deliveries() -> None:
    """scenario step 配信を実行する。"""
    from app.workers.step_delivery import process_step_deliveries

    _run_worker("process_step_deliveries", process_step_deliveries)


def _run_scheduled_broadcasts() -> None:
    """scheduled broadcast 送信を実行する。"""
    from app.workers.broadcast_delivery import process_scheduled_broadcasts

    _run_worker("process_scheduled_broadcasts", process_scheduled_broadcasts)


def _run_reminder_deliveries() -> None:
    """reminder 配信を実行する。"""
    from app.workers.reminder_delivery import process_reminder_deliveries

    _run_worker("process_reminder_deliveries", process_reminder_deliveries)


def start_scheduler() -> None:
    """Scheduler を起動する。

    Note:
        - SCHEDULER_ENABLED=false の場合は起動しない
        - 5 分間隔で 3 つの Worker を実行する
    """
    global _scheduler

    if not SCHEDULER_ENABLED:
        logger.info("Scheduler は無効です（SCHEDULER_ENABLED=false）")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        _scheduler = BackgroundScheduler()
        _scheduler.add_job(
            _run_step_deliveries,
            "interval",
            minutes=INTERVAL_MINUTES,
            id="step_deliveries",
        )
        _scheduler.add_job(
            _run_scheduled_broadcasts,
            "interval",
            minutes=INTERVAL_MINUTES,
            id="scheduled_broadcasts",
        )
        _scheduler.add_job(
            _run_reminder_deliveries,
            "interval",
            minutes=INTERVAL_MINUTES,
            id="reminder_deliveries",
        )
        _scheduler.start()
        logger.info("Scheduler 起動: %d分間隔", INTERVAL_MINUTES)
    except Exception as exc:
        logger.error("Scheduler 起動失敗: %s", str(exc))


def stop_scheduler() -> None:
    """Scheduler を停止する。"""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler 停止")
