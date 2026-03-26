"""
ExecutionPlan / ExecutionResult の永続化テスト。

本モジュールは plan → execute のフローで
execution_plans / execution_results / step_results が
DB に正しく保存されることを検証する。

入出力: TestClient で /api/plan, /api/execute を呼び出し DB を確認する。
制約: 外部 LLM は使わない。in-memory SQLite を使用する。

Note:
    - Task 9.4 の完了条件を検証する
    - ExecutionPlan の DB 保存・取得
    - ExecutionResult + StepResult の DB 保存・取得
    - execution_plans.status の遷移
"""

from fastapi.testclient import TestClient

from app.db.models import ExecutionPlanModel, ExecutionResultModel, StepResultModel
from app.main import app

client = TestClient(app)

# テスト用の BusinessDefinition
_DEFINITION = {
    "title": "永続化テスト",
    "tasks": [
        {
            "name": "VIPタグ付与",
            "steps": ["ユーザーにVIPタグを付与する"],
            "role": "担当者",
        }
    ],
    "roles": [{"name": "担当者", "responsibilities": ["タグ管理"]}],
}


class TestExecutionPlanPersistence:
    """ExecutionPlan の永続化テスト。"""

    def test_plan生成でexecution_plansにレコードが作成される(
        self, _override_get_db
    ) -> None:
        """POST /api/plan で execution_plans にレコードが作成されることを確認する。

        Variables:
            db: テスト用 DB セッション
            resp: /api/plan のレスポンス
            plan_id: 生成された plan の ID
            record: DB から取得した plan レコード
        """
        db = _override_get_db
        resp = client.post("/api/plan", json={"definition": _DEFINITION})
        assert resp.status_code == 200
        plan_id = resp.json()["plan"]["plan_id"]

        record = db.query(ExecutionPlanModel).filter_by(id=plan_id).first()
        assert record is not None
        assert record.status == "created"
        assert record.plan_json is not None
        assert record.source_definition_json is not None

    def test_plan詳細がAPIから取得できる(self) -> None:
        """GET /api/plans/{plan_id} で保存済み plan が取得できることを確認する。

        Variables:
            resp_plan: /api/plan のレスポンス
            plan_id: 生成された plan の ID
            resp_get: /api/plans/{plan_id} のレスポンス
        """
        resp_plan = client.post("/api/plan", json={"definition": _DEFINITION})
        plan_id = resp_plan.json()["plan"]["plan_id"]

        resp_get = client.get(f"/api/plans/{plan_id}")
        assert resp_get.status_code == 200
        body = resp_get.json()
        assert body["plan"]["plan_id"] == plan_id
        assert body["status"] == "created"


class TestExecutionResultPersistence:
    """ExecutionResult + StepResult の永続化テスト。"""

    def test_execute後にexecution_resultsが作成される(self, _override_get_db) -> None:
        """execute 後に execution_results にレコードが作成されることを確認する。

        Variables:
            db: テスト用 DB セッション
            plan: 生成された ExecutionPlan
            execution_id: 実行結果の ID
            record: DB から取得した result レコード
        """
        db = _override_get_db
        resp = client.post("/api/plan", json={"definition": _DEFINITION})
        plan = resp.json()["plan"]

        resp = client.post("/api/execute", json={"plan": plan, "approved": True})
        assert resp.status_code == 200
        execution_id = resp.json()["result"]["execution_id"]

        record = db.query(ExecutionResultModel).filter_by(id=execution_id).first()
        assert record is not None
        assert record.plan_id == plan["plan_id"]

    def test_execute後にstep_resultsが作成される(self, _override_get_db) -> None:
        """execute 後に step ごとに step_results にレコードが作成されることを確認する。

        Variables:
            db: テスト用 DB セッション
            plan: 生成された ExecutionPlan
            execution_id: 実行結果の ID
            step_records: DB から取得した step_result レコード群
        """
        db = _override_get_db
        resp = client.post("/api/plan", json={"definition": _DEFINITION})
        plan = resp.json()["plan"]
        step_count = len(plan["steps"])

        resp = client.post("/api/execute", json={"plan": plan, "approved": True})
        execution_id = resp.json()["result"]["execution_id"]

        step_records = (
            db.query(StepResultModel).filter_by(execution_id=execution_id).all()
        )
        assert len(step_records) == step_count
        assert all(sr.status == "success" for sr in step_records)


class TestPlanStatusTransition:
    """execution_plans.status の遷移テスト。"""

    def test_execute後にstatusがcompletedに遷移する(self, _override_get_db) -> None:
        """成功時に execution_plans.status が completed に遷移することを確認する。

        Variables:
            db: テスト用 DB セッション
            plan: 生成された ExecutionPlan
            plan_id: plan の ID
            record: DB から取得した plan レコード
        """
        db = _override_get_db
        resp = client.post("/api/plan", json={"definition": _DEFINITION})
        plan = resp.json()["plan"]
        plan_id = plan["plan_id"]

        # 実行前は created
        record = db.query(ExecutionPlanModel).filter_by(id=plan_id).first()
        assert record.status == "created"

        # 実行
        client.post("/api/execute", json={"plan": plan, "approved": True})

        # 実行後は completed
        db.expire_all()
        record = db.query(ExecutionPlanModel).filter_by(id=plan_id).first()
        assert record.status == "completed"
