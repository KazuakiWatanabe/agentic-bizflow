"""
SQLAlchemy の DeclarativeBase を定義する。

本モジュールは全 ORM モデルが継承する Base クラスを提供する。

入出力: ORM モデル定義の基底クラスを公開する。
制約: Base クラスの定義のみを責務とし、モデル定義は models.py に委譲する。

Note:
    - SQLAlchemy 2.0 スタイルの DeclarativeBase を使用する
    - Alembic の env.py から Base.metadata を参照する
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """全 ORM モデルの基底クラス。

    SQLAlchemy 2.0 の DeclarativeBase を継承する。
    全テーブル定義はこのクラスを継承して作成する。

    Note:
        - metadata 属性を Alembic が参照してマイグレーションを生成する
    """

    pass
