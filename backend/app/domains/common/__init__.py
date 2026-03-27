"""
共通ドメインモジュール。

本モジュールはチャネルに依存しない共通 workload kind を
Workload Kind Registry に登録する。共通 kind は kind_resolver を通じて
各ドメイン固有の kind に解決される二層構造を提供する。

入出力: register() で共通 workload kind と resolution マッピングを登録する。
制約: Agent 層には依存しない。

Note:
    - 5 つの共通 workload kind を登録する
    - 各共通 kind に対して、ドメインごとの解決先マッピングを登録する
    - 解決先が None のドメインはその kind を未サポートとする
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
    """共通ドメインを登録する。

    Args:
        connector_registry: Connector Registry（dict）
        workload_registry: Workload Kind Registry
        db: DB セッション

    Note:
        - 5 つの共通 workload kind を登録する
        - 各 kind に対してドメインごとの resolution マッピングを登録する
        - connector は空文字列（共通 kind は直接実行しない）
    """
    if workload_registry is None:
        return

    # 共通 workload kind の登録
    workload_registry.register(
        kind="audience.label.assign",
        domain="common",
        connector="",
        requires_approval=ApprovalRule.NONE,
        description="対象者にラベル（タグ）を付与する",
        keywords=["タグ", "付与", "ラベル", "セグメント"],
    )
    workload_registry.register(
        kind="campaign.schedule",
        domain="common",
        connector="",
        requires_approval=ApprovalRule.ALWAYS,
        description="一斉配信キャンペーンを予約する",
        keywords=["配信", "一斉", "全員", "告知"],
    )
    workload_registry.register(
        kind="journey.create",
        domain="common",
        connector="",
        requires_approval=ApprovalRule.NONE,
        description="ステップ配信ジャーニーを作成する",
        keywords=["シナリオ", "ステップ配信", "フォロー", "ステップ"],
    )
    workload_registry.register(
        kind="journey.enroll",
        domain="common",
        connector="",
        requires_approval=ApprovalRule.CONDITIONAL,
        description="ジャーニーに対象者を登録する",
        keywords=["開始", "対象者", "配信開始", "スタート"],
    )
    workload_registry.register(
        kind="followup.create",
        domain="common",
        connector="",
        requires_approval=ApprovalRule.NONE,
        description="フォローアップリマインダーを作成する",
        keywords=["リマインド", "リマインダー", "通知予約", "カウントダウン"],
    )

    # resolution マッピングの登録
    # 共通 kind → {ドメイン: ドメイン固有 kind} のマッピング
    workload_registry.register_resolution(
        "audience.label.assign",
        {"line": "line.tag.assign", "email": None},
    )
    workload_registry.register_resolution(
        "campaign.schedule",
        {"line": "line.broadcast.schedule", "email": "email.broadcast.schedule"},
    )
    workload_registry.register_resolution(
        "journey.create",
        {"line": "line.scenario.create", "email": None},
    )
    workload_registry.register_resolution(
        "journey.enroll",
        {"line": "line.scenario.start", "email": None},
    )
    workload_registry.register_resolution(
        "followup.create",
        {"line": "line.reminder.create", "email": None},
    )

    logger.info("共通ドメイン登録完了: 5 kind + 5 resolution")
