"""
共通 kind からドメイン固有 kind への解決を行う。

本モジュールは Marketing Channel Abstraction の中核となる kind 解決ロジックを提供する。
共通 kind（例: campaign.schedule）をドメイン固有 kind（例: line.broadcast.schedule）に
変換することで、チャネル非依存の業務定義を実現する。

入出力: kind 文字列とレジストリを受け取り、解決後の kind 文字列を返す。
制約: 外部 API 呼び出しや副作用は持たない。

Note:
    - 解決の優先順位: (1) 既にドメイン kind → そのまま返す
    - (2) domain_hint が指定されている → そのドメインの解決先を使用
    - (3) enabled_domains を順番に試行
    - (4) 解決先がない場合は ValueError を送出する
"""

import logging
from typing import List, Optional

from app.connectors.workload_kind_registry import WorkloadKindRegistry

logger = logging.getLogger(__name__)


def resolve_kind(
    kind: str,
    registry: WorkloadKindRegistry,
    domain_hint: Optional[str] = None,
    enabled_domains: Optional[List[str]] = None,
) -> str:
    """共通 kind をドメイン固有 kind に解決する。

    Args:
        kind: 解決対象の workload kind
        registry: Workload Kind Registry
        domain_hint: 優先的に使用するドメイン名
        enabled_domains: 有効なドメイン名のリスト（優先順）

    Returns:
        解決後のドメイン固有 kind 文字列

    Raises:
        ValueError: 解決先が見つからない場合

    Note:
        - 解決の優先順位:
          1. resolution マッピングがない kind → そのまま返す（既にドメイン kind かエイリアス）
          2. domain_hint が指定されている → そのドメインの解決先を使用
          3. domain_hint なし → enabled_domains を順番に試行
          4. いずれでも解決できない場合 → ValueError を送出

    Variables:
        resolution: 共通 kind の resolution マッピング
        resolved: 解決先のドメイン固有 kind
    """
    # resolution マッピングを取得
    resolution = registry.get_resolution(kind)

    # resolution マッピングがない場合は、既にドメイン kind またはエイリアスなので
    # そのまま返す
    if resolution is None:
        logger.debug("resolution なし: %s → そのまま返す", kind)
        return kind

    # domain_hint が指定されている場合、そのドメインの解決先を使用
    if domain_hint is not None:
        resolved = resolution.get(domain_hint)
        if resolved is not None:
            logger.debug(
                "domain_hint '%s' で解決: %s → %s",
                domain_hint,
                kind,
                resolved,
            )
            return resolved
        raise ValueError(
            f"共通 kind '{kind}' はドメイン '{domain_hint}' では"
            f"サポートされていません"
        )

    # enabled_domains を順番に試行
    if enabled_domains:
        for domain in enabled_domains:
            resolved = resolution.get(domain)
            if resolved is not None:
                logger.debug(
                    "enabled_domains で解決: %s → %s (domain=%s)",
                    kind,
                    resolved,
                    domain,
                )
                return resolved

    # いずれでも解決できなかった場合
    raise ValueError(
        f"共通 kind '{kind}' の解決先が見つかりません。"
        f"domain_hint={domain_hint}, enabled_domains={enabled_domains}"
    )
