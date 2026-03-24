"""
実行計画生成エンドポイント（POST /api/plan）を提供する。

本モジュールは BusinessDefinition を受け取り、ExecutionPlan を返す。
ExecutionPlanner を使用してルールベースで変換する。

入出力: PlanRequest → PlanResponse
制約: 既存の /api/convert には影響しない。

Note:
    - definition が空の場合は 400 を返す
    - ExecutionPlanner の例外は 500 で返す
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.execution.execution_planner import ExecutionPlanner

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


@router.post("/plan", response_model=PlanResponse)
def create_plan(request: PlanRequest) -> PlanResponse:
    """BusinessDefinition から ExecutionPlan を生成する。

    Args:
        request: BusinessDefinition を含むリクエスト

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

    return PlanResponse(plan=plan.model_dump())
