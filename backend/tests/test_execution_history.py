"""
実行履歴照会 API のテスト。

本モジュールは GET /api/executions, GET /api/executions/{id},
GET /api/plans, GET /api/plans/{plan_id} の動作を検証する。

入出力: TestClient で各エンドポイントを呼び出す。
制約: 外部 LLM は使わない。in-memory SQLite を使用する。

Note:
    - plan → execute → history の E2E フローを検証する
    - 存在しない ID で 404 を返すことを検証する
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# テスト用の BusinessDefinition（tag.assign を検出する）
_DEFINITION = {
    "title": "履歴テスト",
    "tasks": [
        {
            "name": "VIPタグ付与",
            "steps": ["対象者にVIPタグを付与する"],
            "role": "担当者",
        }
    ],
    "roles": [{"name": "担当者", "responsibilities": ["タグ管理"]}],
}


def _create_and_execute() -> tuple:
    """plan 作成 → execute の一連のフローを実行するヘルパー。

    Returns:
        (plan_id, execution_id) のタプル
    """
    # plan 作成
    resp = client.post("/api/plan", json={"definition": _DEFINITION})
    assert resp.status_code == 200
    plan = resp.json()["plan"]
    plan_id = plan["plan_id"]

    # 実行
    resp = client.post("/api/execute", json={"plan": plan, "approved": True})
    assert resp.status_code == 200
    execution_id = resp.json()["result"]["execution_id"]

    return plan_id, execution_id


class TestPlanListAPI:
    """GET /api/plans のテスト。"""

    def test_plans一覧が返る(self) -> None:
        """GET /api/plans で一覧が返ることを確認する。

        Variables:
            plan_id: 作成した plan の ID
            resp: /api/plans のレスポンス
            body: レスポンスの JSON
        """
        plan_id, _ = _create_and_execute()

        resp = client.get("/api/plans")
        assert resp.status_code == 200
        body = resp.json()
        assert "plans" in body
        assert "total" in body
        assert body["total"] >= 1

        # 作成した plan が含まれている
        plan_ids = [p["plan_id"] for p in body["plans"]]
        assert plan_id in plan_ids

    def test_plan詳細が返る(self) -> None:
        """GET /api/plans/{plan_id} で詳細が返ることを確認する。

        Variables:
            plan_id: 作成した plan の ID
            resp: /api/plans/{plan_id} のレスポンス
            body: レスポンスの JSON
        """
        plan_id, _ = _create_and_execute()

        resp = client.get(f"/api/plans/{plan_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert "plan" in body
        assert "status" in body
        assert body["plan"]["plan_id"] == plan_id

    def test_存在しないplan_idで404(self) -> None:
        """存在しない plan_id で 404 が返ることを確認する。"""
        resp = client.get("/api/plans/nonexistent_plan")
        assert resp.status_code == 404


class TestExecutionHistoryAPI:
    """GET /api/executions のテスト。"""

    def test_executions一覧が返る(self) -> None:
        """GET /api/executions で一覧が返ることを確認する。

        Variables:
            resp: /api/executions のレスポンス
            body: レスポンスの JSON
        """
        _create_and_execute()

        resp = client.get("/api/executions")
        assert resp.status_code == 200
        body = resp.json()
        assert "executions" in body
        assert "total" in body
        assert body["total"] >= 1

    def test_execution詳細が返る(self) -> None:
        """GET /api/executions/{id} で詳細が返ることを確認する。

        Variables:
            execution_id: 実行結果の ID
            resp: /api/executions/{id} のレスポンス
            body: レスポンスの JSON
        """
        _, execution_id = _create_and_execute()

        resp = client.get(f"/api/executions/{execution_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["execution_id"] == execution_id
        assert "step_results" in body
        assert "errors" in body
        assert "warnings" in body

    def test_存在しないexecution_idで404(self) -> None:
        """存在しない execution_id で 404 が返ることを確認する。"""
        resp = client.get("/api/executions/nonexistent_exec")
        assert resp.status_code == 404

    def test_E2E_plan生成からexecute_から履歴確認(self) -> None:
        """plan → execute → history の E2E フローを確認する。

        Variables:
            plan_id: 作成した plan の ID
            execution_id: 実行結果の ID
        """
        plan_id, execution_id = _create_and_execute()

        # plan が DB に存在する
        resp = client.get(f"/api/plans/{plan_id}")
        assert resp.status_code == 200

        # execution が DB に存在する
        resp = client.get(f"/api/executions/{execution_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan_id"] == plan_id
        assert len(body["step_results"]) > 0
