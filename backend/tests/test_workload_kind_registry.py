"""
WorkloadKindRegistry のユニットテスト。

本モジュールは workload kind の登録・取得・一覧・エイリアス解決など、
WorkloadKindRegistry の全主要メソッドを検証する。

入出力: Registry のメソッド呼び出しと戻り値の検証。
制約: 外部 LLM は使わない。各テストで新規インスタンスを使う。

Note:
    - シングルトンではなく、テストごとに新規 WorkloadKindRegistry を使用する
    - 他テストとの干渉を避けるため独立したインスタンスで検証する
"""

import pytest

from app.connectors.workload_kind_registry import WorkloadKindRegistry
from app.schemas.workload_kind import ApprovalRule


@pytest.fixture()
def registry() -> WorkloadKindRegistry:
    """テスト用の新規 WorkloadKindRegistry インスタンスを返す。

    Returns:
        空の WorkloadKindRegistry
    """
    return WorkloadKindRegistry()


def test_register_and_get(registry: WorkloadKindRegistry) -> None:
    """kind を登録し、get で取得できることを確認する。

    Variables:
        registry: テスト用 Registry
        result: get の戻り値

    Note:
        - register → get の基本フロー
    """
    registry.register(
        kind="line.tag.assign",
        domain="line",
        connector="line",
        requires_approval=ApprovalRule.NONE,
        description="タグ付与",
    )
    result = registry.get("line.tag.assign")
    assert result is not None
    assert result.kind == "line.tag.assign"
    assert result.domain == "line"
    assert result.connector == "line"
    assert result.description == "タグ付与"


def test_list_by_domain_filters_correctly(registry: WorkloadKindRegistry) -> None:
    """list_by_domain がドメインで正しくフィルタすることを確認する。

    Variables:
        registry: テスト用 Registry
        line_kinds: line ドメインの kind 一覧
        email_kinds: email ドメインの kind 一覧

    Note:
        - 異なるドメインの kind を登録し、フィルタ結果を検証
    """
    registry.register(kind="line.tag.assign", domain="line", connector="line")
    registry.register(kind="line.broadcast.schedule", domain="line", connector="line")
    registry.register(
        kind="email.broadcast.schedule", domain="email", connector="email"
    )

    line_kinds = registry.list_by_domain("line")
    email_kinds = registry.list_by_domain("email")

    assert len(line_kinds) == 2
    assert len(email_kinds) == 1
    assert all(k.domain == "line" for k in line_kinds)
    assert email_kinds[0].domain == "email"


def test_list_all_returns_all_registered(registry: WorkloadKindRegistry) -> None:
    """list_all が全登録 kind を返すことを確認する。

    Variables:
        registry: テスト用 Registry
        all_kinds: 全 kind 一覧

    Note:
        - 複数ドメインにまたがる kind を登録して検証
    """
    registry.register(kind="line.tag.assign", domain="line", connector="line")
    registry.register(kind="email.template.create", domain="email", connector="email")
    registry.register(
        kind="email.broadcast.schedule", domain="email", connector="email"
    )

    all_kinds = registry.list_all()
    assert len(all_kinds) == 3

    # 登録した kind が全て含まれていることを検証
    kind_names = {k.kind for k in all_kinds}
    assert kind_names == {
        "line.tag.assign",
        "email.template.create",
        "email.broadcast.schedule",
    }


def test_is_valid_registered_and_unknown(registry: WorkloadKindRegistry) -> None:
    """is_valid が登録済み kind で True、未登録 kind で False を返すことを確認する。

    Variables:
        registry: テスト用 Registry

    Note:
        - 正の判定と負の判定の両方を検証
    """
    registry.register(kind="line.tag.assign", domain="line", connector="line")

    assert registry.is_valid("line.tag.assign") is True
    assert registry.is_valid("unknown.kind") is False


def test_register_alias(registry: WorkloadKindRegistry) -> None:
    """register_alias で旧 kind から新 kind を解決できることを確認する。

    Variables:
        registry: テスト用 Registry
        result_old: 旧 kind で get した結果
        result_new: 新 kind で get した結果

    Note:
        - 旧形式（tag.assign）→ 新形式（line.tag.assign）のエイリアス
    """
    registry.register(kind="line.tag.assign", domain="line", connector="line")
    registry.register_alias("tag.assign", "line.tag.assign")

    result_old = registry.get("tag.assign")
    result_new = registry.get("line.tag.assign")

    assert result_old is not None
    assert result_new is not None
    assert result_old.kind == result_new.kind == "line.tag.assign"


def test_resolve_alias(registry: WorkloadKindRegistry) -> None:
    """resolve_alias が正しい値を返すことを確認する。

    Variables:
        registry: テスト用 Registry
        resolved: エイリアス解決後の kind
        non_alias: エイリアスでない kind の解決結果

    Note:
        - エイリアス登録済みの場合は新 kind を返す
        - エイリアス未登録の場合は引数そのままを返す
    """
    registry.register_alias("tag.assign", "line.tag.assign")

    resolved = registry.resolve_alias("tag.assign")
    assert resolved == "line.tag.assign"

    # エイリアスでない kind はそのまま返る
    non_alias = registry.resolve_alias("line.tag.assign")
    assert non_alias == "line.tag.assign"


def test_is_valid_with_alias(registry: WorkloadKindRegistry) -> None:
    """is_valid がエイリアス経由でも True を返すことを確認する。

    Variables:
        registry: テスト用 Registry

    Note:
        - エイリアスが登録されていれば、旧 kind でも valid と判定される
    """
    registry.register(kind="line.tag.assign", domain="line", connector="line")
    registry.register_alias("tag.assign", "line.tag.assign")

    assert registry.is_valid("tag.assign") is True
