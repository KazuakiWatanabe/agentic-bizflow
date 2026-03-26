"""
データベース基盤パッケージ。

本パッケージは SQLAlchemy ORM モデル、セッション管理、
Alembic マイグレーションを提供する。

Note:
    - 開発環境は SQLite、本番環境は DATABASE_URL で切替可能
    - セッションはリクエストスコープで管理する
"""
