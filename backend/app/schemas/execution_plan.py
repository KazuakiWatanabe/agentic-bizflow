"""
実行計画（ExecutionPlan）の Pydantic v2 スキーマを定義する。

本モジュールは BusinessDefinition から変換された実行計画を表現する。
ExecutionPlanner が生成し、WorkloadRunner が消費する。

入出力: ExecutionPlan / ExecutionStep / ApprovalPolicy の型を提供する。
制約: extra fields を禁止し、スキーマ外の入力を拒否する。

Note:
    - kind は 5 種類の workload kind に限定する
    - status は planned / running / success / failed / skipped / blocked に限定する
    - risk_level は low / medium / high に限定する
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# --- workload kind の定義 ---
# Phase 5: Literal から str に変更。Registry で動的に検証する。
# 後方互換のためエイリアスで旧形式（tag.assign 等）も受け付ける。
WorkloadKind = str

# --- step の実行状態 ---
StepStatus = Literal[
    "planned",
    "running",
    "success",
    "failed",
    "skipped",
    "blocked",
]

# --- plan 全体のリスクレベル ---
RiskLevel = Literal["low", "medium", "high"]

# --- 承認ポリシーのモード ---
ApprovalMode = Literal["none", "always", "conditional"]


class ApprovalPolicy(BaseModel):
    """承認ポリシーを定義する。

    step または plan 単位での承認要否を表現する。

    Variables:
        mode:
            承認モード。none=不要、always=常に必須、conditional=条件付き。
        conditions:
            conditional モード時の承認条件の説明リスト。
        reason:
            承認が必要な理由の説明。

    Note:
        - mode が none の場合、conditions と reason は空でよい
    """

    model_config = ConfigDict(extra="forbid")

    mode: ApprovalMode = "none"
    conditions: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


class ExecutionStep(BaseModel):
    """実行計画内の個別ステップを定義する。

    各ステップは 1 つの workload kind に対応し、
    1 つの connector の 1 アクションを実行する。

    Variables:
        step_id:
            ステップの一意識別子。
        sequence:
            実行順序（1 始まり）。
        kind:
            workload の種類（5 種類の Literal）。
        connector:
            使用する connector 名。
        action:
            connector に対して実行するアクション名。
        inputs:
            アクションに渡す入力パラメータ。
        idempotency_key:
            冪等性を保証するための UUID v4 キー。
        requires_approval:
            このステップが承認を必要とするか。
        rollback_action:
            失敗時のロールバックアクション名（将来用）。
        status:
            ステップの実行状態。

    Note:
        - idempotency_key は ExecutionPlanner が UUID v4 で自動付与する
        - rollback_action は Phase 2.5 では未使用（将来拡張用）
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str
    sequence: int = Field(ge=1)
    kind: WorkloadKind
    connector: str
    action: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    requires_approval: bool = False
    rollback_action: Optional[str] = None
    status: StepStatus = "planned"


class ExecutionPlan(BaseModel):
    """実行計画全体を定義する。

    BusinessDefinition から変換された実行可能なステップ列を保持する。
    WorkloadRunner がこのスキーマを受け取って実行する。

    Variables:
        plan_id:
            実行計画の一意識別子。
        source_definition_id:
            変換元の BusinessDefinition の識別子。
        dry_run:
            dry-run モードかどうか。
        requires_approval:
            plan 全体として承認が必要かどうか。
        risk_level:
            plan 全体のリスクレベル。
        steps:
            実行ステップのリスト（sequence 順）。
        summary:
            実行計画の要約説明。
        warnings:
            ユーザーへの警告メッセージ一覧。
        estimated_side_effects:
            予想される副作用の説明一覧。

    Note:
        - requires_approval は steps 内のいずれかが承認必須なら True となる
        - risk_level は最もリスクの高い step に合わせて決定する
    """

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    source_definition_id: Optional[str] = None
    dry_run: bool = False
    requires_approval: bool = False
    risk_level: RiskLevel = "low"
    steps: List[ExecutionStep] = Field(default_factory=list)
    summary: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    estimated_side_effects: List[str] = Field(default_factory=list)
