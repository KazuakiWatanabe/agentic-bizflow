"""
pytest の実行時設定を提供する。

入出力: sys.path を拡張し、app パッケージの import を可能にする。
また、テスト用 in-memory SQLite DB のセットアップと
FastAPI の get_db 依存の差し替えを行う。
制約: 追加は1回のみとし、外部API依存は持ち込まない。

Note:
    - backend 直下で pytest を実行する前提
    - テスト DB は in-memory SQLite を使用する
    - StaticPool により全セッションが同一の in-memory DB を共有する
    - 各テストは同一セッションを使い、終了後にテーブル内容を全削除する
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# backend ルートの基準パス。
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

# テスト用 in-memory SQLite エンジン。StaticPool で全接続が同一 DB を共有する。
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_test_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """テスト用 SQLite 接続時に外部キー制約を有効化する。

    Args:
        dbapi_connection: DBAPI レベルの接続オブジェクト
        connection_record: 接続プールのレコード
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_TestSessionLocal = sessionmaker(bind=_test_engine)


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """テストセッション開始時に全テーブルを作成する。

    Note:
        - scope="session" でテスト全体で 1 回だけ実行する
        - autouse=True で明示的な指定なしに適用する
    """
    import app.db.models  # noqa: F401 — モデルを Base.metadata に登録

    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture()
def db_session(_override_get_db):
    """テスト用 DB セッションを提供する。

    _override_get_db フィクスチャが作成する同一セッションを返す。
    これにより、直接 DB 操作と FastAPI TestClient の DB 操作が同一セッションを共有する。

    Yields:
        Session: テスト用の SQLAlchemy セッション
    """
    yield _override_get_db


@pytest.fixture(autouse=True)
def _override_get_db():
    """FastAPI の get_db 依存をテスト用セッションに差し替える。

    全テストで同一セッションを使用し、テスト終了後に全テーブルのデータを削除する。

    Note:
        - autouse=True で全テストに自動適用する
        - テスト終了後にデータを全削除してテスト間の独立性を保証する
    """
    session = _TestSessionLocal()

    def _override():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    yield session

    # テスト終了後: 全テーブルのデータを削除
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()
    app.dependency_overrides.clear()
