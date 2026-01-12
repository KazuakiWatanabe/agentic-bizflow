"""
FastAPIアプリケーションのエントリポイントを提供する。

本モジュールは /health と /api を公開し、CORS 設定を行う。
入出力: HTTPリクエストを受け取り、JSONレスポンスを返す。
制約: Agenticコアは変更せず、ログは要約のみを扱う。

Variables:
    app:
        ASGIアプリ本体。uvicorn から参照される。

Note:
    - CORS_ALLOW_ORIGINS が未設定または "*" の場合は全許可とする
"""

import os
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.convert import router as convert_router

load_dotenv()


def _parse_cors_origins(value: str) -> List[str]:
    """CORSの許可オリジン文字列をリスト化する。

    Args:
        value: CORS_ALLOW_ORIGINS の値（カンマ区切りまたは "*"）

    Returns:
        許可オリジンのリスト

    Variables:
        cleaned:
            環境変数の値を正規化した文字列。

    Raises:
        None

    Note:
        - 空文字または "*" の場合は ["*"] を返す
    """
    cleaned = value.strip()
    if not cleaned or cleaned == "*":
        return ["*"]
    return [origin.strip() for origin in cleaned.split(",") if origin.strip()]


def create_app() -> FastAPI:
    """FastAPIアプリを生成する。

    Args:
        None

    Returns:
        FastAPIアプリケーション

    Variables:
        app:
            FastAPIアプリ本体。
        origins:
            CORSで許可するオリジンのリスト。

    Raises:
        None

    Note:
        - CORS_ALLOW_ORIGINS を環境変数から読み込み、必要に応じて全許可とする
    """
    app = FastAPI()
    origins = _parse_cors_origins(os.getenv("CORS_ALLOW_ORIGINS", "*"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(convert_router, prefix="/api")
    app.add_api_route("/health", health, methods=["GET"])
    return app


def health() -> str:
    """ヘルスチェック用のレスポンスを返す。

    Args:
        None

    Returns:
        "ok" の文字列

    Raises:
        None
    """
    return "ok"


# ASGIアプリ本体。uvicornの起動対象となる。
app = create_app()
