"""
マーケティング API のエンドポイントテスト。

本モジュールは /api/marketing 配下の共通 kind 一覧と
連絡先 CRUD エンドポイントを検証する。

入出力: TestClient で各エンドポイントを呼び出す。
制約: 外部 LLM は使わない。テスト用 in-memory DB を使用する。

Note:
    - conftest.py の _override_get_db フィクスチャで DB を差し替える
    - 各テスト後にデータは自動クリーンアップされる
"""

from fastapi.testclient import TestClient

from app.main import app

# テスト用 HTTP クライアント
client = TestClient(app)


def test_get_marketing_kinds_returns_200() -> None:
    """GET /api/marketing/kinds が 200 を返し kinds リストを含むことを確認する。

    Variables:
        resp: /api/marketing/kinds のレスポンス
        body: レスポンスの JSON
        kinds: kinds リスト

    Note:
        - 共通 kind が含まれていることを検証する
    """
    resp = client.get("/api/marketing/kinds")
    assert resp.status_code == 200
    body = resp.json()
    assert "kinds" in body
    kinds = body["kinds"]
    assert isinstance(kinds, list)
    assert len(kinds) > 0

    # 各 kind に必要なフィールドが含まれていること
    for k in kinds:
        assert "kind" in k
        assert "description" in k
        assert "resolvable_domains" in k


def test_post_marketing_contacts_creates_contact() -> None:
    """POST /api/marketing/contacts が連絡先を作成し 201 を返すことを確認する。

    Variables:
        payload: 連絡先作成リクエスト
        resp: POST /api/marketing/contacts のレスポンス
        body: レスポンスの JSON

    Note:
        - display_name と channels を含むリクエストで作成する
    """
    payload = {
        "display_name": "API テストユーザー",
        "channels": [
            {"channel_type": "line", "external_id": "U_API_001"},
        ],
    }
    resp = client.post("/api/marketing/contacts", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["display_name"] == "API テストユーザー"
    assert "id" in body
    assert len(body["channels"]) == 1
    assert body["channels"][0]["channel_type"] == "line"
    assert body["channels"][0]["external_id"] == "U_API_001"


def test_get_marketing_contacts_returns_list() -> None:
    """GET /api/marketing/contacts が 200 を返し contacts リストを含むことを確認する。

    Variables:
        resp: GET /api/marketing/contacts のレスポンス
        body: レスポンスの JSON

    Note:
        - contacts リストと total フィールドが存在すること
    """
    resp = client.get("/api/marketing/contacts")
    assert resp.status_code == 200
    body = resp.json()
    assert "contacts" in body
    assert "total" in body
    assert isinstance(body["contacts"], list)
    assert isinstance(body["total"], int)


def test_get_marketing_contacts_by_id_returns_404_for_nonexistent() -> None:
    """GET /api/marketing/contacts/{id} が存在しない ID で 404 を返すことを確認する。

    Variables:
        resp: GET /api/marketing/contacts/{id} のレスポンス

    Note:
        - 存在しない UUID で 404 エラーが返ること
    """
    resp = client.get("/api/marketing/contacts/nonexistent-id-00000")
    assert resp.status_code == 404
