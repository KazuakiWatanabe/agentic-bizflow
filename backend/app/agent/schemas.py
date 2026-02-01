"""
Agentic業務定義のPydantic v2スキーマを定義する。

入出力: BusinessDefinition/TaskDefinition/RoleDefinition の型を提供する。
制約: extra fields を禁止し、スキーマ外の入力を拒否する。

Note:
    - 追加フィールドは ValidationError となる
"""

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class RoleDefinition(BaseModel):
    """ロールの名前と責務を保持する。

    主な属性: name, responsibilities
    主なメソッド: なし（データ保持のみ）
    制約: スキーマ外のフィールドは受け付けない。

    Variables:
        name:
            ロールの名称。
        responsibilities:
            ロールの責務一覧。

    Note:
        - extra fields は禁止する
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    responsibilities: List[str]


class RecipientDefinition(BaseModel):
    """通知先の定義情報を保持する。

    主な属性: type, name, surface
    主なメソッド: なし（データ保持のみ）
    制約: スキーマ外のフィールドは受け付けない。

    Variables:
        type:
            通知先の種別（person など）。
        name:
            通知先の名称。
        surface:
            原文の表記。

    Note:
        - extra fields は禁止する
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    name: str
    surface: str


class TaskDefinition(BaseModel):
    """タスクの定義情報を保持する。

    主な属性: id, name, role, trigger, steps, exception_handling, notifications, recipients
    主なメソッド: なし（データ保持のみ）
    制約: スキーマ外のフィールドは受け付けない。

    Variables:
        id:
            タスク識別子。
        name:
            タスク名。
        role:
            担当ロール名。
        trigger:
            実行トリガー。
        steps:
            実行手順の一覧。
        exception_handling:
            例外時の対応一覧。
        notifications:
            通知内容の一覧。
        recipients:
            通知先の一覧。

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
    recipients: List[RecipientDefinition] = Field(default_factory=list)


class BusinessDefinition(BaseModel):
    """業務定義の最終出力を保持する。

    主な属性: title, overview, tasks, roles, assumptions, open_questions
    主なメソッド: なし（データ保持のみ）
    制約: スキーマ外のフィールドは受け付けない。

    Variables:
        title:
            業務定義のタイトル。
        overview:
            概要説明。
        tasks:
            タスク定義の一覧。
        roles:
            ロール定義の一覧。
        assumptions:
            前提条件の一覧。
        open_questions:
            未解決事項の一覧。

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
