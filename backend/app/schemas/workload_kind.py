"""
Workload Kind の定義スキーマを提供する。

本モジュールは各ドメインの workload kind を表現する Pydantic モデルと
承認ルールの列挙型を定義する。

入出力: WorkloadKindDefinition / ApprovalRule の型を提供する。
制約: extra fields を禁止する。

Note:
    - kind は '{domain}.{action}' 形式（例: line.tag.assign）
    - 旧形式（tag.assign）はエイリアスとして扱う
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict


class ApprovalRule(str, Enum):
    """承認ルールの列挙型。

    Variables:
        NONE: 承認不要
        ALWAYS: 常に承認必須
        CONDITIONAL: 条件付き承認

    Note:
        - broadcast 系は通常 ALWAYS
        - tag.assign 等は NONE
    """

    NONE = "none"
    ALWAYS = "always"
    CONDITIONAL = "conditional"


class WorkloadKindDefinition(BaseModel):
    """workload kind の定義モデル。

    各ドメインが Registry に登録する workload kind の情報を保持する。

    Variables:
        kind: workload kind の識別子（例: line.tag.assign）
        domain: ドメイン名（例: line, email）
        connector: connector registry のキー
        requires_approval: 承認ルール
        description: 人間向け説明
        keywords: ExecutionPlanner のキーワードマッチ用

    Note:
        - keywords は日本語テキストとのマッチングに使用する
    """

    model_config = ConfigDict(extra="forbid")

    kind: str
    domain: str
    connector: str
    requires_approval: ApprovalRule = ApprovalRule.NONE
    description: str = ""
    keywords: List[str] = []
