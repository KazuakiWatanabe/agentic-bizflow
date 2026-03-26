"""
承認ワークフローエンドポイントを提供する。

本モジュールは承認リクエストの一覧・詳細・承認・却下 API を提供する。

入出力: GET/POST リクエスト → 承認リクエスト情報
制約: 承認/却下は pending 状態のリクエストのみ受け付ける。

Note:
    - pending → approved / rejected に遷移する
    - 承認済み/却下済みのリクエストを再変更することはできない
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.repositories.approval_repo import ApprovalRepository
from app.db.repositories.audit_repo import AuditRepository
from app.db.session import get_db
from app.schemas.approval import (
    ApprovalDecisionRequest,
    ApprovalItem,
    ApprovalListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/approvals", response_model=ApprovalListResponse)
def list_approvals(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> ApprovalListResponse:
    """承認リクエスト一覧を取得する。

    Args:
        status: フィルタ対象の status（pending / approved / rejected）
        skip: スキップ件数
        limit: 取得上限件数
        db: DB セッション（DI）

    Returns:
        ApprovalListResponse: 承認リクエスト一覧
    """
    records = ApprovalRepository.list_all(db, status=status, skip=skip, limit=limit)
    return ApprovalListResponse(
        approvals=[
            ApprovalItem(
                id=r.id,
                plan_id=r.plan_id,
                status=r.status,
                requested_at=r.requested_at,
                decided_at=r.decided_at,
                decided_by=r.decided_by,
                reason=r.reason,
            )
            for r in records
        ],
        total=len(records),
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalItem)
def get_approval(
    approval_id: str,
    db: Session = Depends(get_db),
) -> ApprovalItem:
    """承認リクエスト詳細を取得する。

    Args:
        approval_id: 取得対象の承認リクエスト ID
        db: DB セッション（DI）

    Returns:
        ApprovalItem: 承認リクエスト詳細

    Raises:
        HTTPException: 見つからない場合は 404
    """
    record = ApprovalRepository.get(db, approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    return ApprovalItem(
        id=record.id,
        plan_id=record.plan_id,
        status=record.status,
        requested_at=record.requested_at,
        decided_at=record.decided_at,
        decided_by=record.decided_by,
        reason=record.reason,
    )


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalItem)
def approve(
    approval_id: str,
    request: Optional[ApprovalDecisionRequest] = None,
    db: Session = Depends(get_db),
) -> ApprovalItem:
    """承認リクエストを承認する。

    Args:
        approval_id: 対象の承認リクエスト ID
        request: 承認者・理由（任意）
        db: DB セッション（DI）

    Returns:
        ApprovalItem: 更新後の承認リクエスト

    Raises:
        HTTPException: 見つからない場合は 404、pending でない場合は 400
    """
    record = ApprovalRepository.get(db, approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    if record.status != "pending":
        raise HTTPException(status_code=400, detail="approval is not pending")

    decided_by = request.decided_by if request else None
    reason = request.reason if request else None

    ApprovalRepository.approve(db, approval_id, decided_by=decided_by, reason=reason)
    AuditRepository.log(
        db,
        action="approval_decided",
        plan_id=record.plan_id,
        detail={"decision": "approved", "decided_by": decided_by},
    )
    db.commit()

    record = ApprovalRepository.get(db, approval_id)
    return ApprovalItem(
        id=record.id,
        plan_id=record.plan_id,
        status=record.status,
        requested_at=record.requested_at,
        decided_at=record.decided_at,
        decided_by=record.decided_by,
        reason=record.reason,
    )


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalItem)
def reject(
    approval_id: str,
    request: Optional[ApprovalDecisionRequest] = None,
    db: Session = Depends(get_db),
) -> ApprovalItem:
    """承認リクエストを却下する。

    Args:
        approval_id: 対象の承認リクエスト ID
        request: 却下者・理由（任意）
        db: DB セッション（DI）

    Returns:
        ApprovalItem: 更新後の承認リクエスト

    Raises:
        HTTPException: 見つからない場合は 404、pending でない場合は 400
    """
    record = ApprovalRepository.get(db, approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    if record.status != "pending":
        raise HTTPException(status_code=400, detail="approval is not pending")

    decided_by = request.decided_by if request else None
    reason = request.reason if request else None

    ApprovalRepository.reject(db, approval_id, decided_by=decided_by, reason=reason)
    AuditRepository.log(
        db,
        action="approval_decided",
        plan_id=record.plan_id,
        detail={"decision": "rejected", "decided_by": decided_by},
    )
    db.commit()

    record = ApprovalRepository.get(db, approval_id)
    return ApprovalItem(
        id=record.id,
        plan_id=record.plan_id,
        status=record.status,
        requested_at=record.requested_at,
        decided_at=record.decided_at,
        decided_by=record.decided_by,
        reason=record.reason,
    )
