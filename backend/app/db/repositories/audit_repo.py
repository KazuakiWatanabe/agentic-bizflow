"""
監査ログの CRUD リポジトリを提供する。

本モジュールは execution_audit_logs テーブルに対する操作を提供する。
全操作の証跡を記録する。

入出力: Session と操作情報を受け取り、監査ログレコードを INSERT する。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - detail_json に生の LLM 応答は含めない（要約のみ）
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import ExecutionAuditLogModel


class AuditRepository:
    """監査ログの CRUD 操作を提供する。

    主要メソッド:
        log: 監査ログを記録する
        list_by_plan: plan_id で一覧取得する
        list_by_execution: execution_id で一覧取得する

    Note:
        - commit は行わない
    """

    @staticmethod
    def log(
        db: Session,
        action: str,
        detail: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
        plan_id: Optional[str] = None,
    ) -> ExecutionAuditLogModel:
        """監査ログを記録する。

        Args:
            db: SQLAlchemy セッション
            action: 操作種別（plan_created / step_executed 等）
            detail: 操作の詳細（dict → JSON 文字列に変換）
            execution_id: 関連する execution の ID
            plan_id: 関連する plan の ID

        Returns:
            ExecutionAuditLogModel インスタンス
        """
        record = ExecutionAuditLogModel(
            id=str(uuid.uuid4()),
            execution_id=execution_id,
            plan_id=plan_id,
            action=action,
            detail_json=json.dumps(detail or {}, ensure_ascii=False),
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def list_by_plan(
        db: Session, plan_id: str, limit: int = 50
    ) -> List[ExecutionAuditLogModel]:
        """plan_id で監査ログを取得する。

        Args:
            db: SQLAlchemy セッション
            plan_id: 検索対象の plan_id
            limit: 取得上限件数

        Returns:
            ExecutionAuditLogModel のリスト
        """
        return (
            db.query(ExecutionAuditLogModel)
            .filter_by(plan_id=plan_id)
            .order_by(ExecutionAuditLogModel.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def list_by_execution(
        db: Session, execution_id: str, limit: int = 50
    ) -> List[ExecutionAuditLogModel]:
        """execution_id で監査ログを取得する。

        Args:
            db: SQLAlchemy セッション
            execution_id: 検索対象の execution_id
            limit: 取得上限件数

        Returns:
            ExecutionAuditLogModel のリスト
        """
        return (
            db.query(ExecutionAuditLogModel)
            .filter_by(execution_id=execution_id)
            .order_by(ExecutionAuditLogModel.created_at.desc())
            .limit(limit)
            .all()
        )
