"""
dry-run エンドポイント（POST /api/dry-run）を提供する。

本モジュールは ExecutionPlan を受け取り、副作用なしの DryRunPreview を返す。
WorkloadRunner を dry_run=True で実行する。

入出力: DryRunRequest → DryRunResponse
制約: 外部システムへの書き込みは一切行わない。承認なしでも実行可能。

Note:
    - dry-run は承認なしでも常に実行可能
    - connector の dry_run() メソッドを使用する
    - Phase 3 では DBLineConnector を使用するが、dry-run 時は DB 書き込みしない
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.connectors.db_line_connector import DBLineConnector
from app.connectors.mock_internal_job_connector import MockInternalJobConnector
from app.db.session import get_db
from app.execution.workload_runner import WorkloadRunner
from app.schemas.execution_plan import ExecutionPlan

router = APIRouter()


def _build_runner(db: Session) -> WorkloadRunner:
    """DB 対応の connector registry を持つ WorkloadRunner を生成する。

    Args:
        db: SQLAlchemy セッション

    Returns:
        WorkloadRunner インスタンス

    Note:
        - line connector は DBLineConnector を使用する
        - dry-run 時は DB 書き込みを行わない
    """
    registry = {
        "line": DBLineConnector(db=db),
        "internal_job": MockInternalJobConnector(),
    }
    return WorkloadRunner(registry=registry)


class DryRunRequest(BaseModel):
    """dry-run APIの入力モデル。

    ExecutionPlan の dict を受け取る。

    Variables:
        plan:
            ExecutionPlan の dict 表現。

    Note:
        - plan_id のみでの指定は Phase 2.5 では未対応（plan 全体を渡す）
    """

    model_config = ConfigDict(extra="forbid")

    plan: Dict[str, Any]


class DryRunResponse(BaseModel):
    """dry-run APIのレスポンスモデル。

    DryRunPreview を dict として返す。

    Variables:
        preview:
            DryRunPreview の dict 表現。
    """

    model_config = ConfigDict(extra="forbid")

    preview: Dict[str, Any]


@router.post("/dry-run", response_model=DryRunResponse)
def dry_run(
    request: DryRunRequest,
    db: Session = Depends(get_db),
) -> DryRunResponse:
    """ExecutionPlan の dry-run を実行する。

    Args:
        request: ExecutionPlan を含むリクエスト
        db: DB セッション（DI）

    Returns:
        DryRunResponse: DryRunPreview を含むレスポンス

    Variables:
        plan:
            リクエストから復元した ExecutionPlan。
        runner:
            WorkloadRunner インスタンス。
        result:
            dry-run の結果（DryRunPreview）。

    Raises:
        HTTPException: plan のパースに失敗した場合は 400、内部エラーは 500

    Note:
        - dry-run は承認なしでも常に実行可能
        - DB 書き込みは一切行わない
    """
    try:
        plan = ExecutionPlan(**request.plan)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="invalid execution plan format",
        ) from exc

    runner = _build_runner(db)
    try:
        result = runner.run(plan, dry_run=True)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="dry-run execution failed",
        ) from exc

    return DryRunResponse(preview=result.model_dump())
