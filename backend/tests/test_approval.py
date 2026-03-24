"""
承認フロー（check_approval）のテスト。

本モジュールは ExecutionPlan に対する承認要否判定を検証する。

入出力: ExecutionPlan → (requires_approval, step_ids)。
制約: 外部 LLM は使わない。

Note:
    - broadcast.schedule は常に承認必須
    - 承認不要な plan では False が返ること
"""

from app.execution.approval import check_approval
from app.schemas.execution_plan import ExecutionPlan, ExecutionStep


def _make_step(step_id="step_001", kind="tag.assign", requires_approval=False):
    """テスト用の ExecutionStep を生成するヘルパー。

    Args:
        step_id: ステップ ID
        kind: workload kind
        requires_approval: 承認要否

    Returns:
        ExecutionStep インスタンス
    """
    return ExecutionStep(
        step_id=step_id,
        sequence=1,
        kind=kind,
        connector="line",
        action=kind,
        inputs={},
        idempotency_key=f"key-{step_id}",
        requires_approval=requires_approval,
    )


def test_broadcast_scheduleを含むplanで承認必須と判定される() -> None:
    """broadcast.schedule を含む plan が承認必須と判定されることを確認する。

    Variables:
        plan:
            broadcast.schedule を含むテスト用の ExecutionPlan。
        requires:
            承認要否の判定結果。
        step_ids:
            承認が必要な step の step_id リスト。
    """
    plan = ExecutionPlan(
        plan_id="plan_test",
        steps=[
            _make_step("step_001", "tag.assign", requires_approval=False),
            _make_step("step_002", "broadcast.schedule", requires_approval=True),
        ],
    )
    requires, step_ids = check_approval(plan)

    assert requires is True
    assert "step_002" in step_ids


def test_承認不要なplanではFalseが返る() -> None:
    """承認不要な step のみの plan で False が返ることを確認する。

    Variables:
        plan:
            承認不要な step のみのテスト用 ExecutionPlan。
        requires:
            承認要否の判定結果。
        step_ids:
            承認が必要な step の step_id リスト。
    """
    plan = ExecutionPlan(
        plan_id="plan_test",
        steps=[
            _make_step("step_001", "tag.assign", requires_approval=False),
        ],
    )
    requires, step_ids = check_approval(plan)

    assert requires is False
    assert len(step_ids) == 0


def test_dryrunは承認なしでも実行可能であること() -> None:
    """承認判定は plan 内容に基づくため、dry-run でも結果は同じことを確認する。

    Variables:
        plan:
            承認必須 step を含むテスト用 ExecutionPlan。
        requires:
            承認要否の判定結果。

    Note:
        - dry-run の実行可否は WorkloadRunner 側で制御する
        - check_approval は plan の内容のみで判定する
    """
    plan = ExecutionPlan(
        plan_id="plan_test",
        steps=[
            _make_step("step_001", "broadcast.schedule", requires_approval=True),
        ],
    )
    requires, _ = check_approval(plan)

    # 承認判定自体は True を返すが、dry-run の実行は Runner が許可する
    assert requires is True


def test_空のplanで承認不要と判定される() -> None:
    """空の plan で承認不要と判定されることを確認する。

    Variables:
        plan:
            空の step を持つテスト用 ExecutionPlan。
        requires:
            承認要否の判定結果。
    """
    plan = ExecutionPlan(plan_id="plan_test", steps=[])
    requires, step_ids = check_approval(plan)

    assert requires is False
    assert len(step_ids) == 0


def test_複数の承認必須stepが全て検出される() -> None:
    """複数の承認必須 step が全て step_ids に含まれることを確認する。

    Variables:
        plan:
            複数の承認必須 step を含むテスト用 ExecutionPlan。
        requires:
            承認要否の判定結果。
        step_ids:
            承認が必要な step の step_id リスト。
    """
    plan = ExecutionPlan(
        plan_id="plan_test",
        steps=[
            _make_step("step_001", "broadcast.schedule", requires_approval=True),
            _make_step("step_002", "scenario.start", requires_approval=True),
        ],
    )
    requires, step_ids = check_approval(plan)

    assert requires is True
    assert len(step_ids) == 2
    assert "step_001" in step_ids
    assert "step_002" in step_ids
