"""
実行エンドポイント（POST /api/execute）を提供する。

本モジュールは ExecutionPlan と承認状態を受け取り、
WorkloadRunner で本実行を行い ExecutionResult を返す。
実行結果は DB に永続化される。

入出力: ExecuteRequest → ExecuteResponse
制約: 承認必須 step が未承認の場合は blocked を返す。

Note:
    - approved=False の場合、承認必須 step は実行されず blocked となる
    - dry_run=False で本実行を行う
    - 実行前に execution_plans.status を 'executing' に更新する
    - 実行後に execution_results + step_results を DB に保存する
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.connectors.db_line_connector import DBLineConnector
from app.connectors.mock_internal_job_connector import MockInternalJobConnector
from app.db.repositories.execution_repo import ExecutionRepository
from app.db.session import get_db
from app.execution.approval import check_approval
from app.execution.workload_runner import WorkloadRunner
from app.schemas.execution_plan import ExecutionPlan

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_runner(db: Session) -> WorkloadRunner:
    """DB 対応の connector registry を持つ WorkloadRunner を生成する。

    Args:
        db: SQLAlchemy セッション

    Returns:
        WorkloadRunner インスタンス

    Note:
        - line connector は DBLineConnector を使用する
    """
    registry = {
        "line": DBLineConnector(db=db),
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
def execute(
    request: ExecuteRequest,
    db: Session = Depends(get_db),
) -> ExecuteResponse:
    """ExecutionPlan を本実行し、結果を DB に保存する。

    Args:
        request: ExecutionPlan と承認状態を含むリクエスト
        db: DB セッション（DI）

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
        - 実行前に execution_plans.status を 'executing' に更新する
        - 実行後に execution_results + step_results を DB に保存する
        - 失敗時もエラー情報を保存する
    """
    try:
        plan = ExecutionPlan(**request.plan)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="invalid execution plan format",
        ) from exc

    # 承認要否を確認（ログ用）
    requires_approval, approval_step_ids = check_approval(plan)

    # execution_plans.status を 'executing' に更新（plan が DB に存在する場合）
    plan_record = ExecutionRepository.get_plan(db, plan.plan_id)
    if plan_record:
        ExecutionRepository.update_plan_status(db, plan.plan_id, "executing")

    # WorkloadRunner で本実行
    runner = _build_runner(db)
    try:
        result = runner.run(plan, dry_run=False, approved=request.approved)
    except Exception as exc:
        # 失敗時も plan status を更新
        if plan_record:
            ExecutionRepository.update_plan_status(
                db, plan.plan_id, "failed"
            )
            db.commit()
        raise HTTPException(
            status_code=500,
            detail="execution failed",
        ) from exc

    # 実行結果を DB に保存
    try:
        # execution_results に保存
        ExecutionRepository.save_result(db, result)

        # step_results に保存
        ExecutionRepository.save_step_results(
            db=db,
            execution_id=result.execution_id,
            step_results=result.step_results,
            plan_steps=plan.steps,
        )

        # execution_plans.status を最終状態に更新
        if plan_record:
            final_status = (
                "completed" if result.status == "success" else "failed"
            )
            ExecutionRepository.update_plan_status(
                db, plan.plan_id, final_status
            )

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("実行結果の DB 保存に失敗: %s", exc)
        # DB 保存が失敗してもレスポンスは返す

    return ExecuteResponse(result=result.model_dump())
