"""
Phase 2.5 の既存エンドポイント回帰テスト。

本モジュールは Phase 3 の新機能追加によって
Phase 2.5 の /api/plan, /api/dry-run, /api/execute が壊れていないことを確認する。

入出力: TestClient で各エンドポイントを呼び出す。
制約: 外部 LLM は使わない。

Note:
    - 回帰テストのため、最優先で実行する
    - Phase 2.5 の既存レスポンス形式が維持されていることを検証する
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
    resp = client.post(
        "/api/plan",
        json={"definition": _DEFINITION},
    )
    assert resp.status_code == 200
    return resp.json()["plan"]


def test_plan_正常系_planが生成される() -> None:
    """POST /api/plan が正常にplanを返すことを確認する。

    Variables:
        resp: /api/plan のレスポンス
        body: レスポンスの JSON
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


def test_plan_異常系_空definitionで400() -> None:
    """definition が空の場合に 400 が返ることを確認する。

    Variables:
        resp: /api/plan のレスポンス
    """
    resp = client.post("/api/plan", json={"definition": {}})
    assert resp.status_code == 400


def test_dryrun_正常系_previewが返る() -> None:
    """POST /api/dry-run が正常に preview を返すことを確認する。

    Variables:
        plan: テスト用の ExecutionPlan
        resp: /api/dry-run のレスポンス
        body: レスポンスの JSON
    """
    plan = _create_plan()
    resp = client.post("/api/dry-run", json={"plan": plan})
    assert resp.status_code == 200
    body = resp.json()
    assert "preview" in body
    assert body["preview"]["status"] == "dry_run_completed"


def test_execute_正常系_承認済みで成功する() -> None:
    """POST /api/execute が承認済みで成功することを確認する。

    Variables:
        plan: テスト用の ExecutionPlan
        resp: /api/execute のレスポンス
        body: レスポンスの JSON
    """
    plan = _create_plan()
    resp = client.post(
        "/api/execute",
        json={"plan": plan, "approved": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "result" in body
    assert "execution_id" in body["result"]
    assert "step_results" in body["result"]


def test_execute_承認必須stepが未承認時にblockedを含む() -> None:
    """承認必須 step が未承認時に blocked が含まれることを確認する。

    Variables:
        definition: broadcast を含む BusinessDefinition
        plan: テスト用の ExecutionPlan
        resp: /api/execute のレスポンス
        body: レスポンスの JSON
    """
    definition = {
        "title": "配信テスト",
        "tasks": [
            {
                "name": "全員に告知配信",
                "steps": ["全員に告知メッセージを一斉配信する"],
            }
        ],
        "roles": [],
    }
    resp_plan = client.post(
        "/api/plan",
        json={"definition": definition},
    )
    assert resp_plan.status_code == 200
    plan = resp_plan.json()["plan"]

    resp = client.post(
        "/api/execute",
        json={"plan": plan, "approved": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    # broadcast.schedule は承認必須なので blocked が含まれる
    statuses = [sr["status"] for sr in body["result"]["step_results"]]
    assert "blocked" in statuses


def test_health_回帰() -> None:
    """/health が "ok" を返すことを確認する。"""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == "ok"
