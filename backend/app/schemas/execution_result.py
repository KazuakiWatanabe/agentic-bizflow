"""
実行結果（ExecutionResult）の Pydantic v2 スキーマを定義する。

本モジュールは WorkloadRunner の実行結果を表現する。
StepResult は各ステップの結果、DryRunPreview は dry-run 時のプレビューを保持する。

入出力: ExecutionResult / StepResult / DryRunPreview の型を提供する。
制約: extra fields を禁止し、スキーマ外の入力を拒否する。

Note:
    - ExecutionResult の status は success / partial_success / failed / blocked に限定する
    - StepResult の status は ExecutionStep の StepStatus と同じ型を使用する
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.execution_plan import StepStatus

# --- 実行結果全体のステータス ---
ExecutionStatus = Literal["success", "partial_success", "failed", "blocked"]


class StepResult(BaseModel):
    """個別ステップの実行結果を保持する。

    WorkloadRunner が各ステップの実行後に生成する。

    Variables:
        step_id:
            対応するステップの識別子。
        status:
            ステップの実行結果ステータス。
        error_code:
            エラー発生時のコード（成功時は None）。
        message:
            実行結果の説明メッセージ。

    Note:
        - 成功時は error_code が None となる
        - blocked 時は error_code に "APPROVAL_REQUIRED" が設定される
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str
    status: StepStatus
    error_code: Optional[str] = None
    message: Optional[str] = None


class ExecutionResult(BaseModel):
    """実行結果全体を保持する。

    WorkloadRunner が plan の全ステップ実行後に返す。

    Variables:
        execution_id:
            実行の一意識別子。
        plan_id:
            実行元の ExecutionPlan の識別子。
        status:
            実行全体のステータス。
        started_at:
            実行開始日時。
        finished_at:
            実行完了日時。
        step_results:
            各ステップの実行結果リスト。
        errors:
            実行中に発生したエラーメッセージ一覧。
        warnings:
            実行中の警告メッセージ一覧。

    Note:
        - 全 step が success なら status は success
        - 一部 step が失敗または blocked なら partial_success
        - 全 step が blocked なら blocked
        - 最初の step が失敗なら failed
    """

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    plan_id: str
    status: ExecutionStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    step_results: List[StepResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class DryRunPreview(BaseModel):
    """dry-run 実行のプレビュー結果を保持する。

    WorkloadRunner が dry_run=True で実行した際に返す。
    実際の副作用は発生しない。

    Variables:
        plan_id:
            対象の ExecutionPlan の識別子。
        status:
            dry-run のステータス（常に "dry_run_completed"）。
        warnings:
            ユーザーへの警告メッセージ一覧。
        preview:
            各ステップの実行予告テキストリスト。
        estimated_target_count:
            推定対象ユーザー数（不明な場合は None）。

    Note:
        - dry-run は承認なしでも常に実行可能
    """

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    status: str = "dry_run_completed"
    warnings: List[str] = Field(default_factory=list)
    preview: List[str] = Field(default_factory=list)
    estimated_target_count: Optional[int] = None
