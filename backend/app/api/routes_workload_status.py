"""
ワークロード状態照会エンドポイントを提供する。

本モジュールは scenarios / broadcasts / reminders / tags の
集計情報を返す 4 つの GET エンドポイントを提供する。

入出力: GET リクエスト → 各ワークロードの集計情報 JSON
制約: 読み取り専用。DB への書き込みは行わない。

Note:
    - Phase 6 で追加されたダッシュボード用 API
    - 既存テーブルのみを使用し、新規テーブルは追加しない
    - COUNT 集計には sqlalchemy.func を使用する
"""

import logging
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    BroadcastModel,
    ReminderEnrollmentModel,
    ReminderModel,
    ScenarioEnrollmentModel,
    ScenarioModel,
    TagAssignmentModel,
    TagModel,
)
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# レスポンスモデル
# ============================================================


class ScenarioStatusItem(BaseModel):
    """シナリオ状態の個別要素。

    Variables:
        id: シナリオ ID
        name: シナリオ名
        is_active: 有効/無効
        total_enrollments: 登録者総数
        active: active ステータスの登録者数
        completed: completed ステータスの登録者数
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    is_active: bool
    total_enrollments: int
    active: int
    completed: int


class ScenarioListResponse(BaseModel):
    """シナリオ一覧レスポンス。

    Variables:
        scenarios: シナリオ状態のリスト
    """

    model_config = ConfigDict(extra="forbid")

    scenarios: List[ScenarioStatusItem]


class BroadcastStatusResponse(BaseModel):
    """配信ステータス集計レスポンス。

    Variables:
        draft: 下書き件数
        scheduled: 予約済み件数
        sending: 送信中件数
        sent: 送信済み件数
        failed: 失敗件数
        total: 合計件数
    """

    model_config = ConfigDict(extra="forbid")

    draft: int
    scheduled: int
    sending: int
    sent: int
    failed: int
    total: int


class ReminderStatusItem(BaseModel):
    """リマインダー状態の個別要素。

    Variables:
        id: リマインダー ID
        name: リマインダー名
        is_active: 有効/無効
        total_enrollments: 登録者総数
        active_enrollments: active ステータスの登録者数
        completed_enrollments: completed ステータスの登録者数
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    is_active: bool
    total_enrollments: int
    active_enrollments: int
    completed_enrollments: int


class ReminderListResponse(BaseModel):
    """リマインダー一覧レスポンス。

    Variables:
        reminders: リマインダー状態のリスト
    """

    model_config = ConfigDict(extra="forbid")

    reminders: List[ReminderStatusItem]


class ScenarioSummary(BaseModel):
    """シナリオ集計サマリ。

    Variables:
        total: シナリオ総数
        active_enrollments: active 登録者数
        completed_enrollments: completed 登録者数
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    active_enrollments: int
    completed_enrollments: int


class BroadcastSummary(BaseModel):
    """配信集計サマリ。

    Variables:
        draft: 下書き件数
        scheduled: 予約済み件数
        sending: 送信中件数
        sent: 送信済み件数
        failed: 失敗件数
    """

    model_config = ConfigDict(extra="forbid")

    draft: int
    scheduled: int
    sending: int
    sent: int
    failed: int


class ReminderSummary(BaseModel):
    """リマインダー集計サマリ。

    Variables:
        total: リマインダー総数
        active_enrollments: active 登録者数
        completed_enrollments: completed 登録者数
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    active_enrollments: int
    completed_enrollments: int


class TagSummary(BaseModel):
    """タグ集計サマリ。

    Variables:
        total: タグ総数
        total_assignments: タグ付与総数
    """

    model_config = ConfigDict(extra="forbid")

    total: int
    total_assignments: int


class WorkloadSummaryResponse(BaseModel):
    """統合サマリレスポンス。

    Variables:
        scenarios: シナリオ集計
        broadcasts: 配信集計
        reminders: リマインダー集計
        tags: タグ集計
    """

    model_config = ConfigDict(extra="forbid")

    scenarios: ScenarioSummary
    broadcasts: BroadcastSummary
    reminders: ReminderSummary
    tags: TagSummary


# ============================================================
# エンドポイント
# ============================================================


@router.get("/workloads/scenarios", response_model=ScenarioListResponse)
def list_scenario_status(
    db: Session = Depends(get_db),
) -> ScenarioListResponse:
    """シナリオ一覧と登録者数を取得する。

    Args:
        db: DB セッション（DI）

    Returns:
        ScenarioListResponse: シナリオ状態のリスト

    Variables:
        scenarios: DB から取得した全シナリオ
        items: レスポンス用のシナリオ状態リスト

    Note:
        - 各シナリオの enrollment を status ごとにカウントする
    """
    scenarios = db.query(ScenarioModel).all()
    items: List[ScenarioStatusItem] = []

    for scenario in scenarios:
        # enrollment を status ごとにカウント
        total = (
            db.query(func.count(ScenarioEnrollmentModel.id))
            .filter(ScenarioEnrollmentModel.scenario_id == scenario.id)
            .scalar()
            or 0
        )
        active = (
            db.query(func.count(ScenarioEnrollmentModel.id))
            .filter(
                ScenarioEnrollmentModel.scenario_id == scenario.id,
                ScenarioEnrollmentModel.status == "active",
            )
            .scalar()
            or 0
        )
        completed = (
            db.query(func.count(ScenarioEnrollmentModel.id))
            .filter(
                ScenarioEnrollmentModel.scenario_id == scenario.id,
                ScenarioEnrollmentModel.status == "completed",
            )
            .scalar()
            or 0
        )

        items.append(
            ScenarioStatusItem(
                id=scenario.id,
                name=scenario.name,
                is_active=scenario.is_active,
                total_enrollments=total,
                active=active,
                completed=completed,
            )
        )

    return ScenarioListResponse(scenarios=items)


@router.get("/workloads/broadcasts", response_model=BroadcastStatusResponse)
def get_broadcast_status(
    db: Session = Depends(get_db),
) -> BroadcastStatusResponse:
    """配信ステータス別件数を取得する。

    Args:
        db: DB セッション（DI）

    Returns:
        BroadcastStatusResponse: ステータス別の配信件数

    Variables:
        status_counts: ステータスごとの件数 dict

    Note:
        - broadcasts テーブルの status をグループ化してカウントする
    """
    # ステータスごとの件数を集計
    rows = (
        db.query(BroadcastModel.status, func.count(BroadcastModel.id))
        .group_by(BroadcastModel.status)
        .all()
    )

    # dict に変換
    status_counts = {row[0]: row[1] for row in rows}

    # 各ステータスの件数を取得（存在しない場合は 0）
    draft = status_counts.get("draft", 0)
    scheduled = status_counts.get("scheduled", 0)
    sending = status_counts.get("sending", 0)
    sent = status_counts.get("sent", 0)
    failed = status_counts.get("failed", 0)
    total = draft + scheduled + sending + sent + failed

    return BroadcastStatusResponse(
        draft=draft,
        scheduled=scheduled,
        sending=sending,
        sent=sent,
        failed=failed,
        total=total,
    )


@router.get("/workloads/reminders", response_model=ReminderListResponse)
def list_reminder_status(
    db: Session = Depends(get_db),
) -> ReminderListResponse:
    """リマインダー一覧と登録者数を取得する。

    Args:
        db: DB セッション（DI）

    Returns:
        ReminderListResponse: リマインダー状態のリスト

    Variables:
        reminders: DB から取得した全リマインダー
        items: レスポンス用のリマインダー状態リスト

    Note:
        - 各リマインダーの enrollment を status ごとにカウントする
    """
    reminders = db.query(ReminderModel).all()
    items: List[ReminderStatusItem] = []

    for reminder in reminders:
        # enrollment を status ごとにカウント
        total = (
            db.query(func.count(ReminderEnrollmentModel.id))
            .filter(ReminderEnrollmentModel.reminder_id == reminder.id)
            .scalar()
            or 0
        )
        active = (
            db.query(func.count(ReminderEnrollmentModel.id))
            .filter(
                ReminderEnrollmentModel.reminder_id == reminder.id,
                ReminderEnrollmentModel.status == "active",
            )
            .scalar()
            or 0
        )
        completed = (
            db.query(func.count(ReminderEnrollmentModel.id))
            .filter(
                ReminderEnrollmentModel.reminder_id == reminder.id,
                ReminderEnrollmentModel.status == "completed",
            )
            .scalar()
            or 0
        )

        items.append(
            ReminderStatusItem(
                id=reminder.id,
                name=reminder.name,
                is_active=reminder.is_active,
                total_enrollments=total,
                active_enrollments=active,
                completed_enrollments=completed,
            )
        )

    return ReminderListResponse(reminders=items)


@router.get("/workloads/summary", response_model=WorkloadSummaryResponse)
def get_workload_summary(
    db: Session = Depends(get_db),
) -> WorkloadSummaryResponse:
    """ワークロード統合サマリを取得する。

    Args:
        db: DB セッション（DI）

    Returns:
        WorkloadSummaryResponse: 統合サマリ

    Variables:
        scenario_total: シナリオ総数
        scenario_active: シナリオ active 登録者数
        scenario_completed: シナリオ completed 登録者数
        broadcast_rows: 配信ステータス別件数
        broadcast_counts: ステータス -> 件数の dict
        reminder_total: リマインダー総数
        reminder_active: リマインダー active 登録者数
        reminder_completed: リマインダー completed 登録者数
        tag_total: タグ総数
        assignment_total: タグ付与総数

    Note:
        - 全テーブルの集計を 1 レスポンスにまとめる
    """
    # シナリオ集計
    scenario_total = db.query(func.count(ScenarioModel.id)).scalar() or 0
    scenario_active = (
        db.query(func.count(ScenarioEnrollmentModel.id))
        .filter(ScenarioEnrollmentModel.status == "active")
        .scalar()
        or 0
    )
    scenario_completed = (
        db.query(func.count(ScenarioEnrollmentModel.id))
        .filter(ScenarioEnrollmentModel.status == "completed")
        .scalar()
        or 0
    )

    # 配信集計
    broadcast_rows = (
        db.query(BroadcastModel.status, func.count(BroadcastModel.id))
        .group_by(BroadcastModel.status)
        .all()
    )
    broadcast_counts = {row[0]: row[1] for row in broadcast_rows}

    # リマインダー集計
    reminder_total = db.query(func.count(ReminderModel.id)).scalar() or 0
    reminder_active = (
        db.query(func.count(ReminderEnrollmentModel.id))
        .filter(ReminderEnrollmentModel.status == "active")
        .scalar()
        or 0
    )
    reminder_completed = (
        db.query(func.count(ReminderEnrollmentModel.id))
        .filter(ReminderEnrollmentModel.status == "completed")
        .scalar()
        or 0
    )

    # タグ集計
    tag_total = db.query(func.count(TagModel.id)).scalar() or 0
    assignment_total = db.query(func.count(TagAssignmentModel.target_id)).scalar() or 0

    return WorkloadSummaryResponse(
        scenarios=ScenarioSummary(
            total=scenario_total,
            active_enrollments=scenario_active,
            completed_enrollments=scenario_completed,
        ),
        broadcasts=BroadcastSummary(
            draft=broadcast_counts.get("draft", 0),
            scheduled=broadcast_counts.get("scheduled", 0),
            sending=broadcast_counts.get("sending", 0),
            sent=broadcast_counts.get("sent", 0),
            failed=broadcast_counts.get("failed", 0),
        ),
        reminders=ReminderSummary(
            total=reminder_total,
            active_enrollments=reminder_active,
            completed_enrollments=reminder_completed,
        ),
        tags=TagSummary(
            total=tag_total,
            total_assignments=assignment_total,
        ),
    )
