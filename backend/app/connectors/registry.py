"""
Connector Registry と Workload Kind Registry の初期化を提供する。

本モジュールは環境変数で connector を切り替え、
Workload Kind Registry に全ドメインの kind を登録する。

入出力: 環境変数と DB セッションを受け取り、connector dict を返す。
制約: デフォルトは 'db' モード。

Note:
    - mock: MockLineConnector（テスト用）
    - db: DBLineConnector（Phase 3 互換、DB 書き込み）
    - live: LiveLineConnector（LINE Messaging API 接続）
    - Workload Kind Registry はシングルトン
"""

import logging
import os
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.connectors.base_connector import BaseConnector
from app.connectors.mock_internal_job_connector import MockInternalJobConnector
from app.connectors.workload_kind_registry import workload_kind_registry

logger = logging.getLogger(__name__)

# connector モードの環境変数（デフォルト: db）
LINE_CONNECTOR_MODE = os.getenv("LINE_CONNECTOR_MODE", "db")

# Registry 初期化フラグ
_initialized = False


def _ensure_registry_initialized() -> None:
    """Workload Kind Registry が初期化されていなければ初期化する。

    Note:
        - 各ドメインの register() を呼び出す
        - 複数回呼ばれても 1 回しか実行しない
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    from app.domains import register_all_domains

    register_all_domains(workload_registry=workload_kind_registry)
    logger.info(
        "Workload Kind Registry 初期化完了: %d kinds",
        len(workload_kind_registry.list_all()),
    )


def get_line_connector(db: Optional[Session] = None) -> BaseConnector:
    """LINE connector を環境変数に基づいて取得する。

    Args:
        db: SQLAlchemy セッション（db / live モードで必要）

    Returns:
        BaseConnector インスタンス

    Note:
        - mock: 外部通信なし
        - db: DB 書き込みのみ
        - live: LINE API + DB 書き込み（Phase 4）
    """
    mode = LINE_CONNECTOR_MODE

    if mode == "mock":
        from app.connectors.mock_line_connector import MockLineConnector

        return MockLineConnector()
    elif mode == "live":
        from app.connectors.live_line_connector import LiveLineConnector

        return LiveLineConnector(db=db)
    else:
        from app.connectors.db_line_connector import DBLineConnector

        return DBLineConnector(db=db)


def build_connector_registry(
    db: Optional[Session] = None,
) -> Dict[str, BaseConnector]:
    """connector registry を構築する。

    Args:
        db: SQLAlchemy セッション

    Returns:
        connector 名 → BaseConnector のマッピング

    Note:
        - Workload Kind Registry も同時に初期化する
        - WorkloadRunner に渡す registry を生成する
    """
    _ensure_registry_initialized()
    return {
        "line": get_line_connector(db),
        "internal_job": MockInternalJobConnector(),
    }
