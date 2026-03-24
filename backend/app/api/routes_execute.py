"""
実行エンドポイント（POST /api/execute）を提供する。

本モジュールは ExecutionPlan と承認状態を受け取り、
WorkloadRunner で本実行を行い ExecutionResult を返す。

入出力: ExecuteRequest → ExecuteResponse
制約: 承認必須 step が未承認の場合は blocked を返す。

Note:
    - approved=False の場合、承認必須 step は実行されず blocked となる
    - dry_run=False で本実行を行う
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.connectors.mock_internal_job_connector import MockInternalJobConnector
from app.connectors.mock_line_connector import MockLineConnector
from app.execution.approval import check_approval
from app.execution.workload_runner import WorkloadRunner
from app.schemas.execution_plan import ExecutionPlan

router = APIRouter()


def _build_runner() -> WorkloadRunner:
    """デフォルトの connector registry を持つ WorkloadRunner を生成する。

    Returns:
        WorkloadRunner インスタンス

    Note:
        - Phase 2.5 では mock connector のみ登録する
    """
    # connector registry に mock connector を登録
    registry = {
        "line": MockLineConnector(),
        "internal_job": MockInternalJobConnector(),
    }
    return WorkloadRunner(registry=registry)


class ExecuteRequest(BaseModel):
    """実行APIの入力モデル。

    ExecutionPlan の dict と承認状態を受け取る。

    Variables:
        plan:
            ExecutionPlan の dict 表現。
        approved:
            承認済みかどうか。

    Note:
        - approved が False の場合、承認必須 step は blocked となる
    """

    model_config = ConfigDict(extra="forbid")

    plan: Dict[str, Any]
    approved: bool = False


class ExecuteResponse(BaseModel):
    """実行APIのレスポンスモデル。

    ExecutionResult を dict として返す。

    Variables:
        result:
            ExecutionResult の dict 表現。
    """

    model_config = ConfigDict(extra="forbid")

    result: Dict[str, Any]


@router.post("/execute", response_model=ExecuteResponse)
def execute(request: ExecuteRequest) -> ExecuteResponse:
    """ExecutionPlan を本実行する。

    Args:
        request: ExecutionPlan と承認状態を含むリクエスト

    Returns:
        ExecuteResponse: ExecutionResult を含むレスポンス

    Variables:
        plan:
            リクエストから復元した ExecutionPlan。
        requires_approval:
            plan 全体として承認が必要かどうか。
        approval_step_ids:
            承認が必要な step の step_id リスト。
        runner:
            WorkloadRunner インスタンス。
        result:
            実行結果（ExecutionResult）。

    Raises:
        HTTPException: plan のパースに失敗した場合は 400、内部エラーは 500

    Note:
        - 承認必須 step が未承認の場合は blocked として処理される
        - dry_run=False で本実行を行う
    """
    try:
        # dict から ExecutionPlan を復元
        plan = ExecutionPlan(**request.plan)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="invalid execution plan format",
        ) from exc

    # 承認要否を確認（ログ用）
    requires_approval, approval_step_ids = check_approval(plan)

    # WorkloadRunner で本実行
    runner = _build_runner()
    try:
        result = runner.run(plan, dry_run=False, approved=request.approved)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="execution failed",
        ) from exc

    return ExecuteResponse(result=result.model_dump())
