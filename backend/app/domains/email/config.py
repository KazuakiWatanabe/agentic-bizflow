"""
Email ドメインの設定スキーマを定義する。

本モジュールは Email 固有の SMTP 接続設定を Pydantic モデルで定義する。

入出力: EmailConfig モデルを提供する。
制約: 秘密値は _env サフィックスで環境変数を参照する。

Note:
    - smtp_password_env は環境変数名を格納する（パスワード本体は格納しない）
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class EmailConfig(BaseModel):
    """Email ドメインの SMTP 接続設定。

    Variables:
        smtp_host: SMTP サーバーのホスト名
        smtp_port: SMTP サーバーのポート番号
        smtp_user: SMTP 認証ユーザー名
        smtp_password_env: SMTP パスワードの環境変数名
        from_address: 送信元メールアドレス
        from_name: 送信元の表示名

    Note:
        - smtp_password_env にはパスワード本体ではなく環境変数名を格納する
        - extra="forbid" で未定義フィールドを拒否する
    """

    model_config = ConfigDict(extra="forbid")

    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password_env: Optional[str] = None
    from_address: str = "noreply@example.com"
    from_name: str = "Agentic BizFlow"
