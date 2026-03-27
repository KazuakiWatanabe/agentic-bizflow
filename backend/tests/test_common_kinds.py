"""
共通 workload kind の登録・resolution テスト。

本モジュールは common ドメインに登録される共通 workload kind の
件数・resolution マッピング・resolve_to_domain メソッドを検証する。

入出力: workload_kind_registry のメソッド呼び出しと戻り値の検証。
制約: 外部 LLM は使わない。

Note:
    - _ensure_registry_initialized() で全ドメインの kind を事前登録する
    - シングルトン workload_kind_registry を使用する
"""

from app.connectors.registry import _ensure_registry_initialized
from app.connectors.workload_kind_registry import workload_kind_registry

# Registry 初期化（テスト前に全ドメインの kind を登録する）
_ensure_registry_initialized()


def test_common_domain_has_5_kinds() -> None:
    """common ドメインに 5 つの kind が登録されていることを確認する。

    Variables:
        common_kinds: domain="common" の workload kind リスト

    Note:
        - audience.label.assign, campaign.schedule, journey.create,
          journey.enroll, followup.create の 5 つ
    """
    common_kinds = workload_kind_registry.list_by_domain("common")
    assert len(common_kinds) == 5


def test_audience_label_assign_resolves_to_line_tag_assign() -> None:
    """audience.label.assign の line 解決先が line.tag.assign であることを確認する。

    Variables:
        resolution: audience.label.assign の resolution マッピング

    Note:
        - line ドメインへの解決先が "line.tag.assign" であること
    """
    resolution = workload_kind_registry.get_resolution("audience.label.assign")
    assert resolution is not None
    assert resolution["line"] == "line.tag.assign"


def test_campaign_schedule_resolves_to_line_and_email() -> None:
    """campaign.schedule が line と email の両方に解決されることを確認する。

    Variables:
        resolution: campaign.schedule の resolution マッピング

    Note:
        - line → line.broadcast.schedule
        - email → email.broadcast.schedule
    """
    resolution = workload_kind_registry.get_resolution("campaign.schedule")
    assert resolution is not None
    assert resolution["line"] == "line.broadcast.schedule"
    assert resolution["email"] == "email.broadcast.schedule"


def test_resolve_to_domain_audience_label_assign_line() -> None:
    """resolve_to_domain で audience.label.assign → line が line.tag.assign を返すことを確認する。

    Variables:
        result: resolve_to_domain の戻り値

    Note:
        - domain="line" で解決可能な場合はドメイン固有 kind を返す
    """
    result = workload_kind_registry.resolve_to_domain("audience.label.assign", "line")
    assert result == "line.tag.assign"


def test_resolve_to_domain_audience_label_assign_email_returns_none() -> None:
    """resolve_to_domain で audience.label.assign → email が None を返すことを確認する。

    Variables:
        result: resolve_to_domain の戻り値

    Note:
        - email ドメインでは audience.label.assign は未サポート（None）
    """
    result = workload_kind_registry.resolve_to_domain("audience.label.assign", "email")
    assert result is None
