"""
実行履歴照会エンドポイント（GET /api/executions）を提供する。

本モジュールは実行履歴の一覧取得と詳細取得を提供する。

入出力: GET パラメータ → ExecutionListResponse / ExecutionDetailResponse
制約: 読み取り専用。DB への書き込みは行わない。

Note:
    - ページネーション対応（skip / limit）
    - 存在しない execution_id で 404 を返す
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.repositories.execution_repo import ExecutionRepository
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class ExecutionListItem(BaseModel):
    """実行履歴一覧の各要素。

    Variables:
        execution_id: 実行の識別子
        plan_id: 実行元の plan の識別子
        status: 実行結果のステータス
        started_at: 実行開始日時
        finished_at: 実行完了日時
        step_count: ステップ数
        summary: 実行計画の要約
    """

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    plan_id: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    step_count: int
    summary: Optional[str] = None


class ExecutionListResponse(BaseModel):
    """実行履歴一覧レスポンス。

    Variables:
        executions: 実行履歴の一覧
        total: 総件数
    """

    model_config = ConfigDict(extra="forbid")

    executions: List[ExecutionListItem]
    total: int


class StepResultItem(BaseModel):
    """ステップ結果の表示用モデル。

    Variables:
        step_id: ステップの識別子
        kind: workload kind
        status: ステップの結果ステータス
        message: 結果メッセージ
        error_code: エラーコード
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str
    kind: str
    status: str
    message: Optional[str] = None
    error_code: Optional[str] = None


class ExecutionDetailResponse(BaseModel):
    """実行詳細レスポンス。

    Variables:
        execution_id: 実行の識別子
        plan_id: 実行元の plan の識別子
        status: 実行結果のステータス
        started_at: 実行開始日時
        finished_at: 実行完了日時
        step_results: ステップごとの結果
        errors: エラーメッセージ一覧
        warnings: 警告メッセージ一覧
    """

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    plan_id: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    step_results: List[StepResultItem]
    errors: List[str]
    warnings: List[str]


@router.get("/executions", response_model=ExecutionListResponse)
def list_executions(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> ExecutionListResponse:
    """実行履歴一覧を取得する。

    Args:
        skip: スキップ件数
        limit: 取得上限件数
        db: DB セッション（DI）

    Returns:
        ExecutionListResponse: 実行履歴の一覧

    Variables:
        records: DB から取得した実行結果レコード
        total: 実行結果の総件数
    """
    records = ExecutionRepository.list_results(db, skip=skip, limit=limit)
    total = ExecutionRepository.count_results(db)

    items: List[ExecutionListItem] = []
    for r in records:
        # plan の summary を取得
        plan_record = ExecutionRepository.get_plan(db, r.plan_id)
        summary = plan_record.summary if plan_record else None
        # step_results の件数
        step_count = len(r.step_results)

        items.append(
            ExecutionListItem(
                execution_id=r.id,
                plan_id=r.plan_id,
                status=r.status,
                started_at=r.started_at,
                finished_at=r.finished_at,
                step_count=step_count,
                summary=summary,
            )
        )

    return ExecutionListResponse(executions=items, total=total)


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionDetailResponse,
)
def get_execution(
    execution_id: str,
    db: Session = Depends(get_db),
) -> ExecutionDetailResponse:
    """execution_id で実行詳細を取得する。

    Args:
        execution_id: 取得対象の execution_id
        db: DB セッション（DI）

    Returns:
        ExecutionDetailResponse: 実行詳細

    Raises:
        HTTPException: execution が見つからない場合は 404

    Variables:
        record: DB から取得した実行結果レコード
    """
    record = ExecutionRepository.get_result(db, execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="execution not found")

    step_items = [
        StepResultItem(
            step_id=sr.step_id,
            kind=sr.kind,
            status=sr.status,
            message=sr.message,
            error_code=sr.error_code,
        )
        for sr in record.step_results
    ]

    return ExecutionDetailResponse(
        execution_id=record.id,
        plan_id=record.plan_id,
        status=record.status,
        started_at=record.started_at,
        finished_at=record.finished_at,
        step_results=step_items,
        errors=json.loads(record.errors_json),
        warnings=json.loads(record.warnings_json),
    )
