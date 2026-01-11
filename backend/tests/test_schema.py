import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from app.agent.schemas import (  # noqa: E402
    BusinessDefinition,
    RoleDefinition,
    TaskDefinition,
)


def test_business_definition_schema_forbids_extra() -> None:
    task = TaskDefinition(
        id='task_1',
        name='Process request',
        role='Operator',
        trigger='when request is received',
        steps=['Review input'],
        exception_handling=[],
        notifications=[],
    )
    role = RoleDefinition(
        name='Operator',
        responsibilities=['Handle incoming requests'],
    )
    definition = BusinessDefinition(
        title='Sample Process',
        overview='Sample overview',
        tasks=[task],
        roles=[role],
        assumptions=['input is complete'],
        open_questions=[],
    )

    assert definition.title == 'Sample Process'

    with pytest.raises(ValidationError):
        BusinessDefinition(
            title='Sample Process',
            overview='Sample overview',
            tasks=[task],
            roles=[role],
            assumptions=['input is complete'],
            open_questions=[],
            extra_field='not allowed',
        )
