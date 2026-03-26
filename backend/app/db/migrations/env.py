"""
Alembic マイグレーション環境設定。

本モジュールは Alembic のマイグレーション実行環境を構成する。
Base.metadata を参照し、ORM モデルの変更を検出する。

入出力: alembic コマンドから呼び出され、DB スキーマを変更する。
制約: backend/ ディレクトリから alembic コマンドを実行する前提。

Note:
    - DATABASE_URL 環境変数が設定されている場合はそちらを優先する
    - models.py の import により全 ORM モデルが Base.metadata に登録される
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# backend/ ディレクトリをパスに追加（app パッケージの import 解決用）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

load_dotenv()

from app.db.base import Base  # noqa: E402

# models.py を import して全 ORM モデルを Base.metadata に登録する
import app.db.models  # noqa: E402, F401

# Alembic の設定オブジェクト
config = context.config

# 環境変数 DATABASE_URL が設定されている場合は alembic.ini の値を上書きする
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# ログ設定
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic が参照するメタデータ
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """オフラインモードでマイグレーションを実行する。

    DB に接続せず、SQL スクリプトのみを生成する。

    Note:
        - alembic upgrade --sql で使用する
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """オンラインモードでマイグレーションを実行する。

    DB に接続し、マイグレーションを直接適用する。

    Note:
        - 通常の alembic upgrade head で使用する
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
