"""
実行履歴照会 API のテスト。

本モジュールは GET /api/executions, GET /api/executions/{execution_id} の
動作を検証する。

入出力: TestClient で各エンドポイントを呼び出す。
制約: 外部 LLM は使わない。in-memory SQLite を使用する。

Note:
    - Task 9.5 の完了条件を検証する
    - 一覧取得、詳細取得、404 レスポンスを確認する
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# テスト用の BusinessDefinition
_DEFINITION = {
    "title": "履歴APIテスト",
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
    """plan 作成 → execute を実行するヘルパー。

    Returns:
        (plan_id, execution_id) のタプル
    """
    resp = client.post("/api/plan", json={"definition": _DEFINITION})
    assert resp.status_code == 200
    plan = resp.json()["plan"]

    resp = client.post("/api/execute", json={"plan": plan, "approved": True})
    assert resp.status_code == 200
    execution_id = resp.json()["result"]["execution_id"]

    return plan["plan_id"], execution_id


class TestExecutionListAPI:
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

    def test_一覧にstep_countが含まれる(self) -> None:
        """一覧の各要素に step_count が含まれることを確認する。

        Variables:
            resp: /api/executions のレスポンス
            item: 一覧の最初の要素
        """
        _create_and_execute()

        resp = client.get("/api/executions")
        body = resp.json()
        item = body["executions"][0]
        assert "step_count" in item
        assert item["step_count"] >= 1


class TestExecutionDetailAPI:
    """GET /api/executions/{execution_id} のテスト。"""

    def test_execution詳細が返る(self) -> None:
        """execution_id で詳細が返ることを確認する。

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
        assert len(body["step_results"]) > 0

    def test_詳細にerrorsとwarningsが含まれる(self) -> None:
        """詳細レスポンスに errors と warnings が含まれることを確認する。

        Variables:
            execution_id: 実行結果の ID
            resp: /api/executions/{id} のレスポンス
            body: レスポンスの JSON
        """
        _, execution_id = _create_and_execute()

        resp = client.get(f"/api/executions/{execution_id}")
        body = resp.json()
        assert "errors" in body
        assert "warnings" in body

    def test_存在しないexecution_idで404が返る(self) -> None:
        """存在しない execution_id で 404 が返ることを確認する。"""
        resp = client.get("/api/executions/nonexistent_id")
        assert resp.status_code == 404
