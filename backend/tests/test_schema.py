"""
BusinessDefinitionスキーマの検証を行う。

入出力: Pydanticモデルの生成と例外検証を行う。
制約: extra fields は受け付けない。

Note:
    - extra_field を渡した場合は ValidationError を期待する
"""

import pytest
from pydantic import ValidationError

from app.agent.schemas import BusinessDefinition, RoleDefinition, TaskDefinition


def test_business_definition_schema_forbids_extra() -> None:
    """extra fields が拒否されることを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        task:
            テスト用のタスク定義。
        role:
            テスト用のロール定義。
        definition:
            正常系の業務定義。

    Raises:
        AssertionError: スキーマが想定と異なる場合に発生

    Note:
        - extra_field を渡した場合は ValidationError を期待する
    """
    task = TaskDefinition(
        id="task_1",
        name="Process request",
        role="Operator",
        trigger="when request is received",
        steps=["Review input"],
        exception_handling=[],
        notifications=[],
    )
    role = RoleDefinition(
        name="Operator",
        responsibilities=["Handle incoming requests"],
    )
    definition = BusinessDefinition(
        title="Sample Process",
        overview="Sample overview",
        tasks=[task],
        roles=[role],
        assumptions=["input is complete"],
        open_questions=[],
    )

    assert definition.title == "Sample Process"

    with pytest.raises(ValidationError):
        BusinessDefinition(
            title="Sample Process",
            overview="Sample overview",
            tasks=[task],
            roles=[role],
            assumptions=["input is complete"],
            open_questions=[],
            extra_field="not allowed",
        )
