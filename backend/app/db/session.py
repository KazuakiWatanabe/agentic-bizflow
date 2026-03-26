"""
DB セッション管理を提供する。

本モジュールは SQLAlchemy の engine と SessionLocal を生成し、
FastAPI の Depends で利用する get_db ジェネレータを公開する。

入出力: get_db() は Session を yield し、リクエスト終了時に close する。
制約: セッションはリクエストスコープで管理し、必ず close する。

Note:
    - DATABASE_URL 未設定時は SQLite（./dev.db）をデフォルトとする
    - SQLite 使用時は check_same_thread=False を設定する
"""

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

# データベース接続 URL。未設定時は SQLite をデフォルトとする。
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

# SQLite 使用時の追加設定
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

# SQLAlchemy エンジン
engine = create_engine(DATABASE_URL, connect_args=_connect_args)

# SQLite の外部キー制約を有効化する
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        """SQLite 接続時に外部キー制約を有効化する。

        Args:
            dbapi_connection: DBAPI レベルの接続オブジェクト
            connection_record: 接続プールのレコード

        Note:
            - SQLite はデフォルトで FK 制約が無効のため、明示的に有効化する
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# セッションファクトリ
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI の Depends 用 DB セッションジェネレータ。

    Yields:
        Session: SQLAlchemy セッション

    Note:
        - リクエスト終了時に自動で close される
        - commit / rollback は呼び出し側の責務
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
