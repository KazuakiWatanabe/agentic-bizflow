"""
ValidatorAgent の複合文検知と issue 追加を検証する。

入出力: ValidatorAgent.run を呼び、issues と compound_detected を確認する。
制約: planner_out は最小構成でテストする。

Note:
    - 複合文判定は保守的なルールで行う
"""

from app.agent.validator import ValidatorAgent


def test_validator_adds_compound_issue_when_single_task() -> None:
    """複合文なのに tasks=1 の場合に issue が追加されることを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        validator:
            テスト対象のValidatorAgent。
        planner_out:
            1タスクのみのPlanner出力。
        result:
            Validatorの出力辞書。

    Raises:
        AssertionError: 期待する issue が含まれない場合に発生
    """
    validator = ValidatorAgent()
    planner_out = {
        "tasks": [
            {
                "id": "task_1",
                "name": "Process request",
                "role": "Operator",
                "trigger": "when request is received",
                "steps": ["Review input"],
            }
        ],
        "roles": [{"name": "Operator"}],
    }
    result = validator.run(
        planner_out,
        input_text="経費を申請し、承認されたら精算する",
        actions=["経費を申請する"],
    )

    assert result.get("compound_detected") is True
    assert "compound_text_single_task" in (result.get("issues") or [])
    assert any(
        item.get("code") == "compound_text_single_task"
        for item in result.get("issue_details") or []
    )


def test_validator_no_compound_issue_for_simple_text() -> None:
    """単文入力では複合文 issue が出ないことを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        validator:
            テスト対象のValidatorAgent。
        planner_out:
            1タスクのみのPlanner出力。
        result:
            Validatorの出力辞書。

    Raises:
        AssertionError: 不要な issue が含まれる場合に発生
    """
    validator = ValidatorAgent()
    planner_out = {
        "tasks": [
            {
                "id": "task_1",
                "name": "Process request",
                "role": "Operator",
                "trigger": "when request is received",
                "steps": ["Review input"],
            }
        ],
        "roles": [{"name": "Operator"}],
    }
    result = validator.run(
        planner_out,
        input_text="発注する",
        actions=["発注する"],
    )

    assert result.get("compound_detected") is False
    assert "compound_text_single_task" not in (result.get("issues") or [])
