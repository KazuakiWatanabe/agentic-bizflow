"""
Phase 5 の既存エンドポイント・モジュール回帰テスト。

本モジュールは Phase 6 の新機能追加によって
Phase 5 の /api/domains, /api/workload-kinds, POST /api/plan が
壊れていないことを確認する。

入出力: TestClient で各エンドポイントを呼び出す。
制約: 外部 LLM は使わない。

Note:
    - 回帰テストのため最優先で実行する
    - Phase 5 の既存レスポンス形式が維持されていることを検証する
"""

from fastapi.testclient import TestClient

from app.main import app

# テスト用 HTTP クライアント
client = TestClient(app)

# テスト用の BusinessDefinition
_DEFINITION = {
    "title": "テスト業務",
    "tasks": [
        {
            "name": "VIPタグ付与",
            "steps": ["対象者にVIPタグを付与する"],
            "role": "担当者",
        }
    ],
    "roles": [{"name": "担当者", "responsibilities": ["タグ管理"]}],
}


def test_get_domains_returns_200() -> None:
    """GET /api/domains が 200 を返すことを確認する。

    Variables:
        resp: /api/domains のレスポンス
        body: レスポンスの JSON

    Note:
        - Phase 5 で追加されたドメイン一覧エンドポイントの回帰テスト
    """
    resp = client.get("/api/domains")
    assert resp.status_code == 200
    body = resp.json()
    assert "domains" in body


def test_get_workload_kinds_returns_200() -> None:
    """GET /api/workload-kinds が 200 を返し、kinds リストを含むことを確認する。

    Variables:
        resp: /api/workload-kinds のレスポンス
        body: レスポンスの JSON

    Note:
        - Phase 5 で追加された workload kind 一覧エンドポイントの回帰テスト
    """
    resp = client.get("/api/workload-kinds")
    assert resp.status_code == 200
    body = resp.json()
    assert "kinds" in body
    assert isinstance(body["kinds"], list)


def test_post_plan_still_works() -> None:
    """POST /api/plan が正常に動作することを確認する（後方互換）。

    Variables:
        resp: POST /api/plan のレスポンス
        body: レスポンスの JSON

    Note:
        - Phase 5 以前から存在する plan 生成エンドポイントの回帰テスト
        - definition を渡して plan が生成されることを確認する
    """
    resp = client.post(
        "/api/plan",
        json={"definition": _DEFINITION},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "plan" in body
    assert "plan_id" in body["plan"]
    assert "steps" in body["plan"]
