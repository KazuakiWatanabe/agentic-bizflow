"""
kind_resolver のユニットテスト。

本モジュールは app.execution.kind_resolver.resolve_kind の
各解決パターン（ドメイン kind そのまま、共通 kind + domain_hint、
共通 kind + enabled_domains、解決不可）を検証する。

入出力: resolve_kind の引数と戻り値の検証。
制約: 外部 LLM は使わない。

Note:
    - _ensure_registry_initialized() で全ドメインの kind を事前登録する
    - シングルトン workload_kind_registry を使用する
"""

import pytest

from app.connectors.registry import _ensure_registry_initialized
from app.connectors.workload_kind_registry import workload_kind_registry
from app.execution.kind_resolver import resolve_kind

# Registry 初期化（テスト前に全ドメインの kind を登録する）
_ensure_registry_initialized()


def test_domain_kind_returns_as_is() -> None:
    """ドメイン kind 'line.tag.assign' がそのまま返ることを確認する。

    Variables:
        result: resolve_kind の戻り値

    Note:
        - resolution マッピングが存在しない kind はそのまま返す
    """
    result = resolve_kind("line.tag.assign", workload_kind_registry)
    assert result == "line.tag.assign"


def test_common_kind_with_domain_hint_line() -> None:
    """共通 kind + domain_hint='line' がドメイン固有 kind に解決されることを確認する。

    Variables:
        result: resolve_kind の戻り値

    Note:
        - audience.label.assign + domain_hint="line" → line.tag.assign
    """
    result = resolve_kind(
        "audience.label.assign",
        workload_kind_registry,
        domain_hint="line",
    )
    assert result == "line.tag.assign"


def test_common_kind_without_hint_uses_enabled_domains() -> None:
    """共通 kind + enabled_domains で最初にマッチするドメインに解決されることを確認する。

    Variables:
        result: resolve_kind の戻り値

    Note:
        - campaign.schedule は line でも email でも解決可能
        - enabled_domains=["line"] なら line.broadcast.schedule が返る
    """
    result = resolve_kind(
        "campaign.schedule",
        workload_kind_registry,
        enabled_domains=["line"],
    )
    assert result == "line.broadcast.schedule"


def test_common_kind_no_matching_domain_raises_value_error() -> None:
    """解決先がないドメインヒントで ValueError が発生することを確認する。

    Note:
        - audience.label.assign は email で None なので ValueError
    """
    with pytest.raises(ValueError):
        resolve_kind(
            "audience.label.assign",
            workload_kind_registry,
            domain_hint="email",
        )


def test_phase5_alias_tag_assign_returns_as_is() -> None:
    """Phase 5 エイリアス 'tag.assign' が resolution なしでそのまま返ることを確認する。

    Variables:
        result: resolve_kind の戻り値

    Note:
        - tag.assign は共通 kind ではなくエイリアスのため
          resolution マッピングが存在しない
        - resolve_kind はそのまま返す
    """
    result = resolve_kind("tag.assign", workload_kind_registry)
    assert result == "tag.assign"
