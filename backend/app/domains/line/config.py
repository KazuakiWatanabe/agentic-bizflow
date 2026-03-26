"""
LINE ドメインの設定スキーマを定義する。

本モジュールは LINE 固有の接続設定を Pydantic モデルで定義する。

入出力: LineConfig モデルを提供する。
制約: 秘密値は _env サフィックスで環境変数を参照する。
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class LineDeliveryWindow(BaseModel):
    """配信ウィンドウの設定。

    Variables:
        start_hour: 開始時刻（時）
        end_hour: 終了時刻（時）
        timezone: タイムゾーン
    """

    model_config = ConfigDict(extra="forbid")

    start_hour: int = 9
    end_hour: int = 23
    timezone: str = "Asia/Tokyo"


class LineConfig(BaseModel):
    """LINE ドメインの設定。

    Variables:
        channel_access_token: LINE チャネルアクセストークン
        channel_secret: LINE チャネルシークレット
        connector_mode: mock / db / live
        delivery_window: 配信ウィンドウ設定
    """

    model_config = ConfigDict(extra="forbid")

    channel_access_token: Optional[str] = None
    channel_secret: Optional[str] = None
    connector_mode: str = "db"
    delivery_window: LineDeliveryWindow = LineDeliveryWindow()
