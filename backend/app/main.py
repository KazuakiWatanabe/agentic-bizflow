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
    - SCHEDULER_ENABLED=true のとき Scheduler を起動する
"""

import os
from contextlib import asynccontextmanager
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.convert import router as convert_router
from app.api.routes_approval import router as approval_router
from app.api.routes_dry_run import router as dry_run_router
from app.api.routes_execute import router as execute_router
from app.api.routes_history import router as history_router
from app.api.routes_plan import router as plan_router

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリのライフスパンイベントを管理する。

    起動時に Scheduler を開始し、シャットダウン時に停止する。

    Note:
        - SCHEDULER_ENABLED=true のとき Scheduler を起動する
    """
    from app.workers.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    yield
    stop_scheduler()


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
    app = FastAPI(lifespan=lifespan)
    origins = _parse_cors_origins(os.getenv("CORS_ALLOW_ORIGINS", "*"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(convert_router, prefix="/api")
    app.include_router(plan_router, prefix="/api")
    app.include_router(dry_run_router, prefix="/api")
    app.include_router(execute_router, prefix="/api")
    app.include_router(history_router, prefix="/api")
    app.include_router(approval_router, prefix="/api")
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
