"""
承認リクエストの Pydantic v2 スキーマを定義する。

本モジュールは承認 API のリクエスト/レスポンスモデルを提供する。

入出力: 承認 API の型を提供する。
制約: extra fields を禁止し、スキーマ外の入力を拒否する。
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ApprovalItem(BaseModel):
    """承認リクエストの表示用モデル。

    Variables:
        id: 承認リクエスト ID
        plan_id: 対象 plan の ID
        status: pending / approved / rejected
        requested_at: リクエスト日時
        decided_at: 承認/却下日時
        decided_by: 承認者
        reason: 承認/却下理由
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    plan_id: str
    status: str
    requested_at: datetime
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    reason: Optional[str] = None


class ApprovalListResponse(BaseModel):
    """承認リクエスト一覧レスポンス。

    Variables:
        approvals: 承認リクエストの一覧
        total: 総件数
    """

    model_config = ConfigDict(extra="forbid")

    approvals: List[ApprovalItem]
    total: int


class ApprovalDecisionRequest(BaseModel):
    """承認/却下のリクエストモデル。

    Variables:
        decided_by: 承認者/却下者
        reason: 理由
    """

    model_config = ConfigDict(extra="forbid")

    decided_by: Optional[str] = None
    reason: Optional[str] = None
