"""
実行計画・実行結果の CRUD リポジトリを提供する。

本モジュールは execution_plans / execution_results / step_results テーブルに
対する保存・取得・更新操作を提供する。

入出力: Session と Pydantic モデルまたは dict を受け取り、ORM モデルを返す。
制約: commit / rollback は行わない。呼び出し側の責務。

Note:
    - plan_json / source_definition_json は JSON 文字列として保存する
    - errors_json / warnings_json も JSON 文字列として保存する
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    ExecutionPlanModel,
    ExecutionResultModel,
    StepResultModel,
)
from app.schemas.execution_plan import ExecutionPlan, ExecutionStep
from app.schemas.execution_result import ExecutionResult, StepResult


class ExecutionRepository:
    """実行計画・実行結果の CRUD 操作を提供する。

    ExecutionPlan / ExecutionResult の DB 保存・取得・ステータス更新を行う。
    全メソッドは staticmethod とし、Session を第一引数で受け取る。

    主要メソッド:
        save_plan: ExecutionPlan を DB に保存する
        get_plan: plan_id で取得する
        list_plans: 一覧取得（ページネーション対応）
        update_plan_status: plan の status を更新する
        save_result: ExecutionResult を DB に保存する
        save_step_results: StepResult 群を DB に保存する
        get_result: execution_id で取得する
        list_results: 一覧取得（ページネーション対応）

    Note:
        - commit は行わない（呼び出し側の責務）
    """

    @staticmethod
    def save_plan(
        db: Session,
        plan: ExecutionPlan,
        definition: Dict[str, Any],
        definition_id: Optional[str] = None,
    ) -> ExecutionPlanModel:
        """ExecutionPlan を DB に保存する。

        Args:
            db: SQLAlchemy セッション
            plan: 保存対象の ExecutionPlan
            definition: 元の BusinessDefinition の dict
            definition_id: BusinessDefinition の識別子

        Returns:
            保存した ExecutionPlanModel

        Variables:
            now: 現在の UTC 日時
            record: 保存する ORM モデルインスタンス

        Note:
            - plan_json は ExecutionPlan を JSON 文字列にシリアライズして保存する
            - source_definition_json は definition を JSON 文字列にシリアライズして保存する
        """
        now = datetime.now(timezone.utc)
        record = ExecutionPlanModel(
            id=plan.plan_id,
            source_definition_id=definition_id or "unknown",
            source_definition_json=json.dumps(definition, ensure_ascii=False),
            plan_json=plan.model_dump_json(),
            requires_approval=plan.requires_approval,
            risk_level=plan.risk_level,
            summary=plan.summary,
            status="created",
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def get_plan(db: Session, plan_id: str) -> Optional[ExecutionPlanModel]:
        """plan_id で ExecutionPlan を取得する。

        Args:
            db: SQLAlchemy セッション
            plan_id: 取得対象の plan_id

        Returns:
            ExecutionPlanModel または None
        """
        return db.query(ExecutionPlanModel).filter_by(id=plan_id).first()

    @staticmethod
    def list_plans(
        db: Session, skip: int = 0, limit: int = 20
    ) -> List[ExecutionPlanModel]:
        """保存済み plan 一覧を取得する。

        Args:
            db: SQLAlchemy セッション
            skip: スキップ件数
            limit: 取得上限件数

        Returns:
            ExecutionPlanModel のリスト

        Note:
            - created_at の降順で返す
        """
        return (
            db.query(ExecutionPlanModel)
            .order_by(ExecutionPlanModel.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_plans(db: Session) -> int:
        """plan の総数を返す。

        Args:
            db: SQLAlchemy セッション

        Returns:
            plan の件数
        """
        return db.query(func.count(ExecutionPlanModel.id)).scalar() or 0

    @staticmethod
    def update_plan_status(
        db: Session, plan_id: str, status: str
    ) -> Optional[ExecutionPlanModel]:
        """plan の status を更新する。

        Args:
            db: SQLAlchemy セッション
            plan_id: 更新対象の plan_id
            status: 新しい status 値

        Returns:
            更新後の ExecutionPlanModel または None（見つからない場合）

        Note:
            - updated_at も同時に更新する
        """
        record = db.query(ExecutionPlanModel).filter_by(id=plan_id).first()
        if record:
            record.status = status
            record.updated_at = datetime.now(timezone.utc)
            db.flush()
        return record

    @staticmethod
    def save_result(
        db: Session,
        result: ExecutionResult,
    ) -> ExecutionResultModel:
        """ExecutionResult を DB に保存する。

        Args:
            db: SQLAlchemy セッション
            result: 保存対象の ExecutionResult

        Returns:
            保存した ExecutionResultModel

        Note:
            - errors / warnings は JSON 文字列として保存する
        """
        record = ExecutionResultModel(
            id=result.execution_id,
            plan_id=result.plan_id,
            status=result.status,
            started_at=result.started_at,
            finished_at=result.finished_at,
            errors_json=json.dumps(result.errors, ensure_ascii=False),
            warnings_json=json.dumps(result.warnings, ensure_ascii=False),
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def save_step_results(
        db: Session,
        execution_id: str,
        step_results: List[StepResult],
        plan_steps: List[ExecutionStep],
    ) -> List[StepResultModel]:
        """StepResult 群を DB に保存する。

        Args:
            db: SQLAlchemy セッション
            execution_id: 所属する execution の ID
            step_results: StepResult のリスト
            plan_steps: ExecutionStep のリスト（sequence / kind / connector 取得用）

        Returns:
            保存した StepResultModel のリスト

        Variables:
            step_map: step_id → ExecutionStep のマッピング
            now: 現在の UTC 日時
            records: 保存する ORM モデルのリスト

        Note:
            - plan_steps から sequence, kind, connector を補完する
        """
        # step_id → ExecutionStep のマッピング
        step_map = {s.step_id: s for s in plan_steps}
        now = datetime.now(timezone.utc)
        records: List[StepResultModel] = []

        for sr in step_results:
            plan_step = step_map.get(sr.step_id)
            record = StepResultModel(
                id=str(uuid.uuid4()),
                execution_id=execution_id,
                step_id=sr.step_id,
                sequence=plan_step.sequence if plan_step else 0,
                kind=plan_step.kind if plan_step else "unknown",
                connector=plan_step.connector if plan_step else "unknown",
                status=sr.status,
                error_code=sr.error_code,
                message=sr.message,
                created_at=now,
            )
            db.add(record)
            records.append(record)

        db.flush()
        return records

    @staticmethod
    def get_result(
        db: Session, execution_id: str
    ) -> Optional[ExecutionResultModel]:
        """execution_id で ExecutionResult を取得する。

        Args:
            db: SQLAlchemy セッション
            execution_id: 取得対象の execution_id

        Returns:
            ExecutionResultModel または None
        """
        return (
            db.query(ExecutionResultModel).filter_by(id=execution_id).first()
        )

    @staticmethod
    def list_results(
        db: Session, skip: int = 0, limit: int = 20
    ) -> List[ExecutionResultModel]:
        """実行結果一覧を取得する。

        Args:
            db: SQLAlchemy セッション
            skip: スキップ件数
            limit: 取得上限件数

        Returns:
            ExecutionResultModel のリスト

        Note:
            - started_at の降順で返す
        """
        return (
            db.query(ExecutionResultModel)
            .order_by(ExecutionResultModel.started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_results(db: Session) -> int:
        """execution_result の総数を返す。

        Args:
            db: SQLAlchemy セッション

        Returns:
            実行結果の件数
        """
        return db.query(func.count(ExecutionResultModel.id)).scalar() or 0
