"""
Connector の能力定義（ConnectorCapability）の Pydantic v2 スキーマを定義する。

本モジュールは各 connector がサポートするアクションや機能を宣言的に表現する。
WorkloadRunner が connector 選択時に参照する。

入出力: ConnectorCapability の型を提供する。
制約: extra fields を禁止し、スキーマ外の入力を拒否する。
"""

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ConnectorCapability(BaseModel):
    """Connector の能力を宣言的に定義する。

    各 connector は capabilities() メソッドでこのモデルを返す。
    WorkloadRunner は supported_actions を参照して、
    要求された action が実行可能か判断する。

    Variables:
        connector:
            connector の識別名。
        supported_actions:
            サポートするアクション名のリスト。
        supports_dry_run:
            dry-run 実行をサポートするか。
        supports_rollback:
            ロールバックをサポートするか。
        supports_schedule:
            スケジュール実行をサポートするか。

    Note:
        - supports_rollback は Phase 2.5 では false が想定される（将来拡張用）
    """

    model_config = ConfigDict(extra="forbid")

    connector: str
    supported_actions: List[str] = Field(default_factory=list)
    supports_dry_run: bool = True
    supports_rollback: bool = False
    supports_schedule: bool = False
