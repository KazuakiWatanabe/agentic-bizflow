"""
ドメインモジュールパッケージ。

本パッケージはドメインごとの workload kind / connector / worker を管理する。
各ドメインの __init__.py が register() 関数を提供し、
アプリ起動時に自動検出して登録する。

入出力: register_all_domains() で全ドメインを登録する。
制約: domains/__init__.py は自動検出のみを責務とし、ドメイン固有ロジックは持たない。

Note:
    - register() を持つサブパッケージを自動検出する
    - _template は登録対象外
"""

import importlib
import logging
import os
import pkgutil
from typing import Any

logger = logging.getLogger(__name__)


def register_all_domains(
    connector_registry: Any = None,
    workload_registry: Any = None,
    db: Any = None,
) -> None:
    """全ドメインモジュールを検出して登録する。

    Args:
        connector_registry: Connector Registry（dict）
        workload_registry: Workload Kind Registry
        db: DB セッション（connector 構築用）

    Note:
        - _template ディレクトリはスキップする
        - register() 関数を持つモジュールのみ登録する
    """
    package_dir = os.path.dirname(__file__)
    for importer, modname, ispkg in pkgutil.iter_modules([package_dir]):
        if modname.startswith("_"):
            continue
        if not ispkg:
            continue
        try:
            module = importlib.import_module(f"app.domains.{modname}")
            if hasattr(module, "register"):
                module.register(
                    connector_registry=connector_registry,
                    workload_registry=workload_registry,
                    db=db,
                )
                logger.info("ドメイン登録: %s", modname)
        except Exception as exc:
            logger.error("ドメイン登録失敗: %s — %s", modname, str(exc))
