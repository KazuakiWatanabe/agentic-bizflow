"""
承認フローの判定ロジックを提供する。

本モジュールは ExecutionPlan に対して承認要否を判定する。
承認の永続化やワークフローエンジンは対象外。

入出力: ExecutionPlan → (requires_approval: bool, step_ids: list[str])
制約: 永続化は行わない。判定ロジックのみを提供する。

Note:
    - broadcast.schedule は常に承認必須
    - scenario.start は対象 100 名超で承認必須
    - dry-run は承認なしでも常に実行可能
"""

from typing import List, Tuple

from app.schemas.execution_plan import ExecutionPlan

# --- 常に承認が必要な workload kind ---
ALWAYS_APPROVAL_KINDS = {"broadcast.schedule"}

# --- 条件付き承認が必要な workload kind ---
CONDITIONAL_APPROVAL_KINDS = {"scenario.start"}


def check_approval(plan: ExecutionPlan) -> Tuple[bool, List[str]]:
    """ExecutionPlan の承認要否を判定する。

    Args:
        plan: 判定対象の ExecutionPlan

    Returns:
        (requires_approval, approval_step_ids) のタプル
        requires_approval: plan 全体として承認が必要かどうか
        approval_step_ids: 承認が必要な step の step_id リスト

    Variables:
        approval_step_ids:
            承認が必要と判定された step の step_id を格納するリスト。

    Note:
        - 各 step の requires_approval フラグに基づいて判定する
        - plan 内に 1 つでも承認必須 step があれば全体として True を返す
    """
    # 承認が必要な step の step_id を収集
    approval_step_ids: List[str] = []

    for step in plan.steps:
        if step.requires_approval:
            approval_step_ids.append(step.step_id)

    # 1 つでも承認必須 step があれば全体として承認必須
    requires_approval = len(approval_step_ids) > 0

    return requires_approval, approval_step_ids
