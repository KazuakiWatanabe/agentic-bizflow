"""
Email ドメインモジュール。

本モジュールは Email 配信に関連する workload kind を
Workload Kind Registry に登録する。

入出力: register() でドメイン固有のリソースを登録する。
制約: Agent 層には依存しない。

Note:
    - 2 つの workload kind を登録する
    - email.broadcast.schedule: 一斉メール配信予約（承認必須）
    - email.template.create: メールテンプレート作成（承認不要）
"""

import logging
from typing import Any

from app.schemas.workload_kind import ApprovalRule

logger = logging.getLogger(__name__)


def register(
    connector_registry: Any = None,
    workload_registry: Any = None,
    db: Any = None,
) -> None:
    """Email ドメインを登録する。

    Args:
        connector_registry: Connector Registry（dict）
        workload_registry: Workload Kind Registry
        db: DB セッション

    Note:
        - 2 つの workload kind を登録する
        - email.broadcast.schedule は承認必須（ALWAYS）
        - email.template.create は承認不要（NONE）
    """
    if workload_registry is None:
        return

    # Email workload kind の登録
    workload_registry.register(
        kind="email.broadcast.schedule",
        domain="email",
        connector="email",
        requires_approval=ApprovalRule.ALWAYS,
        description="一斉メール配信を予約する",
        keywords=["メール", "mail", "一斉メール", "メール配信"],
    )
    workload_registry.register(
        kind="email.template.create",
        domain="email",
        connector="email",
        requires_approval=ApprovalRule.NONE,
        description="メールテンプレートを作成する",
        keywords=["テンプレート", "メールテンプレート"],
    )

    logger.info("Email ドメイン登録完了: 2 kind")
