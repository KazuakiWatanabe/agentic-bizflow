"""Agentic業務定義のPydantic v2スキーマ（extra禁止）。"""

from typing import List

from pydantic import BaseModel, ConfigDict


class RoleDefinition(BaseModel):
    """業務に関わるロール定義。"""

    model_config = ConfigDict(extra='forbid')

    name: str
    responsibilities: List[str]


class TaskDefinition(BaseModel):
    """実行可能なタスク定義。"""

    model_config = ConfigDict(extra='forbid')

    id: str
    name: str
    role: str
    trigger: str
    steps: List[str]
    exception_handling: List[str]
    notifications: List[str]


class BusinessDefinition(BaseModel):
    """最終出力の業務定義。"""

    model_config = ConfigDict(extra='forbid')

    title: str
    overview: str
    tasks: List[TaskDefinition]
    roles: List[RoleDefinition]
    assumptions: List[str]
    open_questions: List[str]
