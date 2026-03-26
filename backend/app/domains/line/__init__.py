"""
LINE ドメインモジュール。

本モジュールは LINE 配信に関連する workload kind / connector / worker を
Workload Kind Registry と Connector Registry に登録する。

入出力: register() でドメイン固有のリソースを登録する。
制約: Agent 層には依存しない。

Note:
    - 旧形式（tag.assign 等）のエイリアスも登録する
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
    """LINE ドメインを登録する。

    Args:
        connector_registry: Connector Registry（dict）
        workload_registry: Workload Kind Registry
        db: DB セッション

    Note:
        - 5 つの workload kind を登録する
        - 旧形式のエイリアスを登録する
    """
    if workload_registry is None:
        return

    # LINE workload kind の登録
    workload_registry.register(
        kind="line.tag.assign",
        domain="line",
        connector="line",
        requires_approval=ApprovalRule.NONE,
        description="対象者にタグを付与する",
        keywords=["タグ", "付与", "ラベル", "タグ付け"],
    )
    workload_registry.register(
        kind="line.broadcast.schedule",
        domain="line",
        connector="line",
        requires_approval=ApprovalRule.ALWAYS,
        description="LINE 一斉配信を予約する",
        keywords=["配信", "一斉", "全員", "告知", "メッセージ送信", "ブロードキャスト"],
    )
    workload_registry.register(
        kind="line.scenario.create",
        domain="line",
        connector="line",
        requires_approval=ApprovalRule.NONE,
        description="ステップ配信シナリオを作成する",
        keywords=["シナリオ", "ステップ配信", "フォロー", "ステップ"],
    )
    workload_registry.register(
        kind="line.scenario.start",
        domain="line",
        connector="line",
        requires_approval=ApprovalRule.CONDITIONAL,
        description="シナリオ配信を開始する",
        keywords=["開始", "対象者", "配信開始", "スタート"],
    )
    workload_registry.register(
        kind="line.reminder.create",
        domain="line",
        connector="line",
        requires_approval=ApprovalRule.NONE,
        description="リマインダーを作成する",
        keywords=["リマインド", "リマインダー", "通知予約", "カウントダウン"],
    )

    # 後方互換エイリアス
    workload_registry.register_alias("tag.assign", "line.tag.assign")
    workload_registry.register_alias("broadcast.schedule", "line.broadcast.schedule")
    workload_registry.register_alias("scenario.create", "line.scenario.create")
    workload_registry.register_alias("scenario.start", "line.scenario.start")
    workload_registry.register_alias("reminder.create", "line.reminder.create")

    logger.info("LINE ドメイン登録完了: 5 kind + 5 alias")
