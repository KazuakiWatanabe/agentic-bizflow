"""
承認リクエストの CRUD リポジトリを提供する。

本モジュールは approval_requests テーブルに対する操作を提供する。

入出力: Session と plan_id / status を受け取り、承認レコードを操作する。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - 1 plan に対して 1 承認リクエスト（UNIQUE 制約）
    - pending → approved または pending → rejected に遷移する
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import ApprovalRequestModel


class ApprovalRepository:
    """承認リクエストの CRUD 操作を提供する。

    主要メソッド:
        create: 承認リクエストを作成する
        get: ID で取得する
        get_by_plan: plan_id で取得する
        approve: 承認する
        reject: 却下する
        list_all: 一覧取得（status フィルタ対応）

    Note:
        - commit は行わない
    """

    @staticmethod
    def create(db: Session, plan_id: str) -> ApprovalRequestModel:
        """承認リクエストを作成する。

        Args:
            db: SQLAlchemy セッション
            plan_id: 対象 plan の ID

        Returns:
            ApprovalRequestModel インスタンス
        """
        record = ApprovalRequestModel(
            id=str(uuid.uuid4()),
            plan_id=plan_id,
            status="pending",
            requested_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def get(db: Session, approval_id: str) -> Optional[ApprovalRequestModel]:
        """ID で承認リクエストを取得する。

        Args:
            db: SQLAlchemy セッション
            approval_id: 取得対象の ID

        Returns:
            ApprovalRequestModel または None
        """
        return db.query(ApprovalRequestModel).filter_by(id=approval_id).first()

    @staticmethod
    def get_by_plan(db: Session, plan_id: str) -> Optional[ApprovalRequestModel]:
        """plan_id で承認リクエストを取得する。

        Args:
            db: SQLAlchemy セッション
            plan_id: 検索対象の plan_id

        Returns:
            ApprovalRequestModel または None
        """
        return db.query(ApprovalRequestModel).filter_by(plan_id=plan_id).first()

    @staticmethod
    def approve(
        db: Session,
        approval_id: str,
        decided_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Optional[ApprovalRequestModel]:
        """承認リクエストを承認する。

        Args:
            db: SQLAlchemy セッション
            approval_id: 対象の ID
            decided_by: 承認者
            reason: 承認理由

        Returns:
            更新後の ApprovalRequestModel または None

        Note:
            - status が pending でない場合は更新しない
        """
        record = db.query(ApprovalRequestModel).filter_by(id=approval_id).first()
        if record and record.status == "pending":
            record.status = "approved"
            record.decided_at = datetime.now(timezone.utc)
            record.decided_by = decided_by
            record.reason = reason
            db.flush()
        return record

    @staticmethod
    def reject(
        db: Session,
        approval_id: str,
        decided_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Optional[ApprovalRequestModel]:
        """承認リクエストを却下する。

        Args:
            db: SQLAlchemy セッション
            approval_id: 対象の ID
            decided_by: 却下者
            reason: 却下理由

        Returns:
            更新後の ApprovalRequestModel または None

        Note:
            - status が pending でない場合は更新しない
        """
        record = db.query(ApprovalRequestModel).filter_by(id=approval_id).first()
        if record and record.status == "pending":
            record.status = "rejected"
            record.decided_at = datetime.now(timezone.utc)
            record.decided_by = decided_by
            record.reason = reason
            db.flush()
        return record

    @staticmethod
    def list_all(
        db: Session,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[ApprovalRequestModel]:
        """承認リクエスト一覧を取得する。

        Args:
            db: SQLAlchemy セッション
            status: フィルタ対象の status（None で全件）
            skip: スキップ件数
            limit: 取得上限件数

        Returns:
            ApprovalRequestModel のリスト
        """
        query = db.query(ApprovalRequestModel)
        if status:
            query = query.filter_by(status=status)
        return (
            query.order_by(ApprovalRequestModel.requested_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
