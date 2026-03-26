"""
テンプレートのドメイン設定スキーマを定義する。

本モジュールは新しいドメイン用の設定スキーマテンプレートを提供する。
Pydantic モデルでドメイン固有の接続設定を定義するパターンを示す。

入出力: TemplateConfig モデルを提供する。
制約: 秘密値は _env サフィックスで環境変数を参照する。

Note:
    - 新しいドメインではこのファイルをコピーして設定項目を追加する
    - 秘密情報（パスワード、トークン等）はコードに直書きしない
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class TemplateConfig(BaseModel):
    """テンプレートのドメイン設定。

    新しいドメインではこのクラスをコピーして設定項目を定義する。

    Variables:
        api_endpoint: 外部 API のエンドポイント URL
        api_key_env: API キーの環境変数名
        timeout_seconds: タイムアウト（秒）

    Note:
        - api_key_env は環境変数名を格納する（キー本体は格納しない）
        - extra="forbid" で未定義フィールドを拒否する
    """

    model_config = ConfigDict(extra="forbid")

    api_endpoint: Optional[str] = None
    api_key_env: Optional[str] = None
    timeout_seconds: int = 30
