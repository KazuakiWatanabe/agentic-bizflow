"""
Agentic業務定義のPydantic v2スキーマを定義する。

入出力: BusinessDefinition/TaskDefinition/RoleDefinition の型を提供する。
制約: extra fields を禁止し、スキーマ外の入力を拒否する。

Note:
    - 追加フィールドは ValidationError となる
"""

from typing import List

from pydantic import BaseModel, ConfigDict


class RoleDefinition(BaseModel):
    """ロールの名前と責務を保持する。

    主な属性: name, responsibilities
    主なメソッド: なし（データ保持のみ）
    制約: スキーマ外のフィールドは受け付けない。

    Note:
        - extra fields は禁止する
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    responsibilities: List[str]


class TaskDefinition(BaseModel):
    """タスクの定義情報を保持する。

    主な属性: id, name, role, trigger, steps, exception_handling, notifications
    主なメソッド: なし（データ保持のみ）
    制約: スキーマ外のフィールドは受け付けない。

    Note:
        - extra fields は禁止する
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    role: str
    trigger: str
    steps: List[str]
    exception_handling: List[str]
    notifications: List[str]


class BusinessDefinition(BaseModel):
    """業務定義の最終出力を保持する。

    主な属性: title, overview, tasks, roles, assumptions, open_questions
    主なメソッド: なし（データ保持のみ）
    制約: スキーマ外のフィールドは受け付けない。

    Note:
        - extra fields は禁止する
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    overview: str
    tasks: List[TaskDefinition]
    roles: List[RoleDefinition]
    assumptions: List[str]
    open_questions: List[str]
