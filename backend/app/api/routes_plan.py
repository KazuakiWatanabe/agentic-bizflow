"""
実行計画エンドポイント（POST /api/plan, GET /api/plans）を提供する。

本モジュールは BusinessDefinition を受け取り、ExecutionPlan を生成して
DB に保存する。また、保存済み plan の一覧・詳細取得を提供する。

入出力: PlanRequest → PlanResponse / GET → PlanListResponse / PlanDetailResponse
制約: 既存の /api/convert には影響しない。

Note:
    - definition が空の場合は 400 を返す
    - ExecutionPlanner の例外は 500 で返す
    - plan 生成後に DB に保存する
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.repositories.execution_repo import ExecutionRepository
from app.db.session import get_db
from app.execution.execution_planner import ExecutionPlanner

logger = logging.getLogger(__name__)

router = APIRouter()


class PlanRequest(BaseModel):
    """実行計画生成APIの入力モデル。

    BusinessDefinition の dict と識別子を受け取る。

    Variables:
        definition_id:
            変換元の BusinessDefinition の識別子（任意）。
        definition:
            BusinessDefinition の dict 表現。

    Note:
        - definition が空の場合はエラーとする
    """

    model_config = ConfigDict(extra="forbid")

    definition_id: Optional[str] = None
    definition: Dict[str, Any]


class PlanResponse(BaseModel):
    """実行計画生成APIのレスポンスモデル。

    ExecutionPlan を dict として返す。

    Variables:
        plan:
            生成された ExecutionPlan の dict 表現。
    """

    model_config = ConfigDict(extra="forbid")

    plan: Dict[str, Any]


class PlanListItem(BaseModel):
    """plan 一覧の各要素。

    Variables:
        plan_id: plan の識別子
        summary: 実行計画の要約
        status: plan の状態
        risk_level: リスクレベル
        requires_approval: 承認要否
        created_at: 作成日時
    """

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    summary: Optional[str] = None
    status: str
    risk_level: str
    requires_approval: bool
    created_at: datetime


class PlanListResponse(BaseModel):
    """plan 一覧レスポンス。

    Variables:
        plans: plan 一覧
        total: 総件数
    """

    model_config = ConfigDict(extra="forbid")

    plans: List[PlanListItem]
    total: int


class PlanDetailResponse(BaseModel):
    """plan 詳細レスポンス。

    Variables:
        plan: ExecutionPlan の JSON
        status: plan の状態
        created_at: 作成日時
        updated_at: 更新日時
    """

    model_config = ConfigDict(extra="forbid")

    plan: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


@router.post("/plan", response_model=PlanResponse)
def create_plan(
    request: PlanRequest,
    db: Session = Depends(get_db),
) -> PlanResponse:
    """BusinessDefinition から ExecutionPlan を生成し、DB に保存する。

    Args:
        request: BusinessDefinition を含むリクエスト
        db: DB セッション（DI）

    Returns:
        PlanResponse: 生成された ExecutionPlan

    Variables:
        planner:
            ExecutionPlanner インスタンス。
        plan:
            生成された ExecutionPlan。

    Raises:
        HTTPException: definition が空の場合は 400、内部エラーは 500

    Note:
        - 既存の /api/convert には影響しない
        - plan 生成後に DB に保存する
    """
    if not request.definition:
        raise HTTPException(status_code=400, detail="definition is required")

    # ExecutionPlanner で変換
    planner = ExecutionPlanner()
    try:
        plan = planner.plan(
            definition=request.definition,
            definition_id=request.definition_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="execution plan generation failed",
        ) from exc

    # DB に保存
    try:
        ExecutionRepository.save_plan(
            db=db,
            plan=plan,
            definition=request.definition,
            definition_id=request.definition_id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("plan の DB 保存に失敗: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="plan persistence failed",
        ) from exc

    return PlanResponse(plan=plan.model_dump())


@router.get("/plans", response_model=PlanListResponse)
def list_plans(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> PlanListResponse:
    """保存済み plan 一覧を取得する。

    Args:
        skip: スキップ件数
        limit: 取得上限件数
        db: DB セッション（DI）

    Returns:
        PlanListResponse: plan 一覧

    Variables:
        records: DB から取得した plan レコード
        total: plan の総件数
    """
    records = ExecutionRepository.list_plans(db, skip=skip, limit=limit)
    total = ExecutionRepository.count_plans(db)

    return PlanListResponse(
        plans=[
            PlanListItem(
                plan_id=r.id,
                summary=r.summary,
                status=r.status,
                risk_level=r.risk_level,
                requires_approval=r.requires_approval,
                created_at=r.created_at,
            )
            for r in records
        ],
        total=total,
    )


@router.get("/plans/{plan_id}", response_model=PlanDetailResponse)
def get_plan(
    plan_id: str,
    db: Session = Depends(get_db),
) -> PlanDetailResponse:
    """plan_id で plan 詳細を取得する。

    Args:
        plan_id: 取得対象の plan_id
        db: DB セッション（DI）

    Returns:
        PlanDetailResponse: plan 詳細

    Raises:
        HTTPException: plan が見つからない場合は 404

    Variables:
        record: DB から取得した plan レコード
    """
    record = ExecutionRepository.get_plan(db, plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="plan not found")

    return PlanDetailResponse(
        plan=json.loads(record.plan_json),
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
