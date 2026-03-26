"""
Phase 3 の既存エンドポイント回帰テスト。

本モジュールは Phase 4 の新機能追加によって
Phase 3 の /api/plans, /api/executions, POST /api/plan, POST /api/execute が
壊れていないことを確認する。

入出力: TestClient で各エンドポイントを呼び出す。
制約: 外部 LLM は使わない。

Note:
    - 回帰テストのため最優先で実行する
    - Phase 3 の既存レスポンス形式が維持されていることを検証する
"""

from fastapi.testclient import TestClient

from app.main import app

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


def _create_plan() -> dict:
    """テスト用の ExecutionPlan を生成するヘルパー。

    Returns:
        plan の dict 表現
    """
    resp = client.post("/api/plan", json={"definition": _DEFINITION})
    assert resp.status_code == 200
    return resp.json()["plan"]


def test_get_plans_returns_200() -> None:
    """GET /api/plans が 200 を返すことを確認する。

    Variables:
        resp: /api/plans のレスポンス

    Note:
        - Phase 3 で追加された一覧エンドポイントの回帰テスト
    """
    resp = client.get("/api/plans")
    assert resp.status_code == 200
    body = resp.json()
    assert "plans" in body
    assert "total" in body


def test_get_executions_returns_200() -> None:
    """GET /api/executions が 200 を返すことを確認する。

    Variables:
        resp: /api/executions のレスポンス

    Note:
        - Phase 3 で追加された一覧エンドポイントの回帰テスト
    """
    resp = client.get("/api/executions")
    assert resp.status_code == 200
    body = resp.json()
    assert "executions" in body
    assert "total" in body


def test_plan_then_get_plan_detail() -> None:
    """POST /api/plan で作成後に GET /api/plans/{plan_id} で取得できることを確認する。

    Variables:
        plan: POST /api/plan で生成された plan
        plan_id: plan の識別子
        resp_detail: GET /api/plans/{plan_id} のレスポンス
        detail: レスポンスの JSON

    Note:
        - plan 作成と詳細取得のエンドツーエンド回帰テスト
    """
    plan = _create_plan()
    plan_id = plan["plan_id"]

    resp_detail = client.get(f"/api/plans/{plan_id}")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert "plan" in detail
    assert detail["status"] == "created"
    assert detail["plan"]["plan_id"] == plan_id


def test_execute_then_get_execution_detail() -> None:
    """POST /api/execute で実行後に GET /api/executions/{id} で取得できることを確認する。

    Variables:
        plan: POST /api/plan で生成された plan
        resp_exec: POST /api/execute のレスポンス
        exec_body: 実行レスポンスの JSON
        execution_id: 実行結果の識別子
        resp_detail: GET /api/executions/{execution_id} のレスポンス
        detail: 詳細レスポンスの JSON

    Note:
        - 実行と履歴照会のエンドツーエンド回帰テスト
    """
    plan = _create_plan()

    resp_exec = client.post(
        "/api/execute",
        json={"plan": plan, "approved": True},
    )
    assert resp_exec.status_code == 200
    exec_body = resp_exec.json()
    execution_id = exec_body["result"]["execution_id"]

    resp_detail = client.get(f"/api/executions/{execution_id}")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["execution_id"] == execution_id
    assert "step_results" in detail
