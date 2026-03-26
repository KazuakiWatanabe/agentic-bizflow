"""
ドメイン設定の Pydantic v2 スキーマを定義する。

本モジュールはドメイン管理 API のリクエスト/レスポンスモデルを提供する。

入出力: ドメイン管理 API の型を提供する。
制約: extra fields を禁止し、スキーマ外の入力を拒否する。

Note:
    - DomainInfo はドメイン一覧の要素
    - DomainDetailResponse はドメイン詳細
    - WorkloadKindItem は workload kind 一覧の要素
"""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict


class DomainInfo(BaseModel):
    """ドメイン情報の一覧表示用モデル。

    Variables:
        domain: ドメイン識別子
        display_name: 管理画面での表示名
        is_enabled: 有効/無効
        workload_kinds: このドメインの workload kind 一覧
    """

    model_config = ConfigDict(extra="forbid")

    domain: str
    display_name: str
    is_enabled: bool
    workload_kinds: List[str]


class DomainListResponse(BaseModel):
    """ドメイン一覧レスポンス。

    Variables:
        domains: ドメイン情報のリスト
    """

    model_config = ConfigDict(extra="forbid")

    domains: List[DomainInfo]


class DomainDetailResponse(BaseModel):
    """ドメイン詳細レスポンス。

    Variables:
        domain: ドメイン識別子
        display_name: 管理画面での表示名
        is_enabled: 有効/無効
        config: ドメイン固有設定（dict）
        workload_kinds: このドメインの workload kind 詳細一覧
    """

    model_config = ConfigDict(extra="forbid")

    domain: str
    display_name: str
    is_enabled: bool
    config: Dict[str, Any]
    workload_kinds: List[Dict[str, Any]]


class DomainConfigUpdateRequest(BaseModel):
    """ドメイン設定更新リクエスト。

    Variables:
        config: 更新するドメイン固有設定（dict）
    """

    model_config = ConfigDict(extra="forbid")

    config: Dict[str, Any]


class WorkloadKindItem(BaseModel):
    """workload kind の一覧表示用モデル。

    Variables:
        kind: workload kind 識別子
        domain: ドメイン名
        connector: connector 名
        description: 人間向け説明
        requires_approval: 承認ルール
    """

    model_config = ConfigDict(extra="forbid")

    kind: str
    domain: str
    connector: str
    description: str
    requires_approval: str


class WorkloadKindListResponse(BaseModel):
    """workload kind 一覧レスポンス。

    Variables:
        kinds: workload kind のリスト
    """

    model_config = ConfigDict(extra="forbid")

    kinds: List[WorkloadKindItem]
