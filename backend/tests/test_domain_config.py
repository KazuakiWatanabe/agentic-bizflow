"""
ドメイン設定の CRUD およびドメイン管理 API のテスト。

本モジュールは DomainConfigRepository の CRUD 操作と、
GET /api/domains, GET /api/workload-kinds エンドポイントを検証する。

入出力: DB 操作の検証、TestClient での API レスポンス検証。
制約: 外部 LLM は使わない。db_session フィクスチャを使用する。

Note:
    - Repository テストは db_session を直接使用する
    - API テストは TestClient を使用する
    - Registry 初期化を事前に行う
"""

from fastapi.testclient import TestClient

from app.connectors.registry import _ensure_registry_initialized
from app.db.repositories.domain_config_repo import DomainConfigRepository
from app.main import app

# Registry 初期化
_ensure_registry_initialized()

# テスト用 HTTP クライアント
client = TestClient(app)


def test_upsert_creates_record(db_session) -> None:
    """DomainConfigRepository.upsert が新規レコードを作成することを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        record: upsert で作成されたレコード
        fetched: DB から再取得したレコード

    Note:
        - 存在しないドメインに対して upsert を呼ぶと INSERT される
    """
    record = DomainConfigRepository.upsert(
        db=db_session,
        domain="test_domain",
        display_name="テストドメイン",
        is_enabled=True,
        config_json={"key": "value"},
    )

    assert record is not None
    assert record.domain == "test_domain"
    assert record.display_name == "テストドメイン"
    assert record.is_enabled is True

    # DB から再取得して検証
    fetched = DomainConfigRepository.get(db_session, "test_domain")
    assert fetched is not None
    assert fetched.domain == "test_domain"


def test_list_enabled_returns_only_enabled(db_session) -> None:
    """DomainConfigRepository.list_enabled が有効なドメインのみ返すことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        enabled_list: 有効ドメインの一覧
        domains: 有効ドメインのドメイン名リスト

    Note:
        - is_enabled=True のレコードのみ含まれる
        - is_enabled=False のレコードは含まれない
    """
    # 有効なドメインを作成
    DomainConfigRepository.upsert(
        db=db_session,
        domain="enabled_domain",
        display_name="有効ドメイン",
        is_enabled=True,
    )
    # 無効なドメインを作成
    DomainConfigRepository.upsert(
        db=db_session,
        domain="disabled_domain",
        display_name="無効ドメイン",
        is_enabled=False,
    )
    db_session.commit()

    enabled_list = DomainConfigRepository.list_enabled(db_session)
    domains = [r.domain for r in enabled_list]

    assert "enabled_domain" in domains
    assert "disabled_domain" not in domains


def test_enable_disable_works(db_session) -> None:
    """DomainConfigRepository.enable / disable が正しく動作することを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        record: upsert で作成されたレコード
        enabled: enable 後のレコード
        disabled: disable 後のレコード

    Note:
        - enable → is_enabled=True
        - disable → is_enabled=False
    """
    # 初期状態は無効で作成
    DomainConfigRepository.upsert(
        db=db_session,
        domain="toggle_domain",
        display_name="トグルドメイン",
        is_enabled=False,
    )
    db_session.commit()

    # 有効化
    enabled = DomainConfigRepository.enable(db_session, "toggle_domain")
    assert enabled is not None
    assert enabled.is_enabled is True

    # 無効化
    disabled = DomainConfigRepository.disable(db_session, "toggle_domain")
    assert disabled is not None
    assert disabled.is_enabled is False


def test_get_domains_api(db_session) -> None:
    """GET /api/domains がドメイン一覧を返すことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        resp: /api/domains のレスポンス
        body: レスポンスの JSON

    Note:
        - 有効なドメインが登録されている場合にリスト形式で返される
    """
    # テスト用のドメイン設定を DB に登録
    DomainConfigRepository.upsert(
        db=db_session,
        domain="line",
        display_name="LINE",
        is_enabled=True,
    )
    db_session.commit()

    resp = client.get("/api/domains")
    assert resp.status_code == 200

    body = resp.json()
    assert "domains" in body
    assert isinstance(body["domains"], list)


def test_get_workload_kinds_api() -> None:
    """GET /api/workload-kinds が kind 一覧を返すことを確認する。

    Variables:
        resp: /api/workload-kinds のレスポンス
        body: レスポンスの JSON

    Note:
        - Registry に登録済みの全 kind が返される
    """
    resp = client.get("/api/workload-kinds")
    assert resp.status_code == 200

    body = resp.json()
    assert "kinds" in body
    assert isinstance(body["kinds"], list)
    # Registry 初期化済みなので少なくとも LINE + Email の kind が存在する
    assert len(body["kinds"]) > 0

    # 各 kind に必要なフィールドが含まれていることを検証
    for kind_item in body["kinds"]:
        assert "kind" in kind_item
        assert "domain" in kind_item
        assert "connector" in kind_item
