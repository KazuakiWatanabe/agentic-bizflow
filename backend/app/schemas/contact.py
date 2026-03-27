"""
連絡先の Pydantic v2 スキーマを定義する。

本モジュールは連絡先管理 API のリクエスト/レスポンスモデルを提供する。
チャネル非依存の連絡先管理を実現する。

入出力: 連絡先管理 API の型を提供する。
制約: extra fields を禁止し、スキーマ外の入力を拒否する。

Note:
    - ContactChannel はチャネル情報の表示用モデル
    - ContactItem は連絡先一覧・詳細の要素
    - ContactCreateRequest は連絡先作成リクエスト
    - ContactListResponse はページネーション付き一覧レスポンス
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ContactChannel(BaseModel):
    """チャネル情報モデル。

    Variables:
        channel_type: チャネル種別（例: line, email）
        external_id: チャネル側の外部 ID
    """

    model_config = ConfigDict(extra="forbid")

    channel_type: str
    external_id: str


class ContactItem(BaseModel):
    """連絡先の表示用モデル。

    Variables:
        id: 連絡先 ID
        display_name: 表示名
        channels: 紐付くチャネル情報のリスト
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    display_name: Optional[str] = None
    channels: List[ContactChannel] = []


class ContactCreateRequest(BaseModel):
    """連絡先作成リクエスト。

    Variables:
        display_name: 表示名
        channels: 初期登録するチャネル情報のリスト
    """

    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = None
    channels: List[ContactChannel] = []


class ContactListResponse(BaseModel):
    """連絡先一覧レスポンス。

    Variables:
        contacts: 連絡先のリスト
        total: 総件数
    """

    model_config = ConfigDict(extra="forbid")

    contacts: List[ContactItem]
    total: int
