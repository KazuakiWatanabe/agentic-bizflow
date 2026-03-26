"""
ワーカー状態照会エンドポイントを提供する。

本モジュールは worker_task_logs テーブルから
各タスクの最新実行ステータスを取得する API を提供する。

入出力: GET リクエスト → ワーカー状態 JSON
制約: 読み取り専用。DB への書き込みは行わない。

Note:
    - Phase 6 で追加されたダッシュボード用 API
    - 各 task_name ごとに最新の 1 件のみを返す
    - SCHEDULER_ENABLED 環境変数でスケジューラ状態を判定する
"""

import logging
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.models import WorkerTaskLogModel
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# レスポンスモデル
# ============================================================


class WorkerStatusItem(BaseModel):
    """ワーカー状態の個別要素。

    Variables:
        task_name: タスク名
        last_run: 最終実行開始日時
        status: 最終実行のステータス（running / completed / failed）
        processed_count: 処理件数
        error_count: エラー件数
    """

    model_config = ConfigDict(extra="forbid")

    task_name: str
    last_run: datetime
    status: str
    processed_count: int
    error_count: int


class WorkerStatusResponse(BaseModel):
    """ワーカー状態レスポンス。

    Variables:
        workers: ワーカー状態のリスト
        scheduler_enabled: スケジューラが有効かどうか

    Note:
        - scheduler_enabled は SCHEDULER_ENABLED 環境変数で判定する
    """

    model_config = ConfigDict(extra="forbid")

    workers: List[WorkerStatusItem]
    scheduler_enabled: bool


# ============================================================
# エンドポイント
# ============================================================


@router.get("/workers/status", response_model=WorkerStatusResponse)
def get_worker_status(
    db: Session = Depends(get_db),
) -> WorkerStatusResponse:
    """各ワーカーの最新実行ステータスを取得する。

    Args:
        db: DB セッション（DI）

    Returns:
        WorkerStatusResponse: ワーカー状態のリスト

    Variables:
        scheduler_enabled: SCHEDULER_ENABLED 環境変数の値
        unique_tasks: DB 内のユニークな task_name 一覧
        workers: レスポンス用のワーカー状態リスト

    Note:
        - 各 task_name ごとに started_at が最新の 1 件を取得する
        - worker_task_logs が空の場合は空リストを返す
        - SCHEDULER_ENABLED=true の場合のみ scheduler_enabled=True
    """
    # スケジューラ有効/無効の判定
    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "false") == "true"

    # ユニークな task_name を取得
    unique_tasks_query = db.query(WorkerTaskLogModel.task_name).distinct().all()
    unique_task_names = [row[0] for row in unique_tasks_query]

    workers: List[WorkerStatusItem] = []

    for task_name in unique_task_names:
        # 各 task_name の最新レコードを取得
        latest_log: Optional[WorkerTaskLogModel] = (
            db.query(WorkerTaskLogModel)
            .filter(WorkerTaskLogModel.task_name == task_name)
            .order_by(WorkerTaskLogModel.started_at.desc())
            .first()
        )

        if latest_log:
            workers.append(
                WorkerStatusItem(
                    task_name=latest_log.task_name,
                    last_run=latest_log.started_at,
                    status=latest_log.status,
                    processed_count=latest_log.processed_count,
                    error_count=latest_log.error_count,
                )
            )

    return WorkerStatusResponse(
        workers=workers,
        scheduler_enabled=scheduler_enabled,
    )
