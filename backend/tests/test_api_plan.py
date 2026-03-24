"""
Phase 2.5 の新規 API エンドポイントのテスト。

本モジュールは POST /api/plan, /api/dry-run, /api/execute の動作を検証する。

入出力: TestClient で各エンドポイントを呼び出す。
制約: 外部 LLM は使わない。mock connector を使用する。

Note:
    - 既存の /api/convert が壊れていないことも確認する
"""

from fastapi.testclient import TestClient

from app.main import app

# テストクライアント
client = TestClient(app)

# テスト用の BusinessDefinition
SAMPLE_DEFINITION = {
    "title": "テスト業務",
    "overview": "テスト概要",
    "tasks": [
        {
            "id": "t1",
            "name": "VIPタグ付与",
            "role": "担当者",
            "trigger": "手動",
            "steps": ["VIPタグを付与する"],
            "exception_handling": [],
            "notifications": [],
        }
    ],
    "roles": [{"name": "担当者", "responsibilities": ["実行"]}],
    "assumptions": [],
    "open_questions": [],
}

# 配信タスクを含む BusinessDefinition（承認必須テスト用）
BROADCAST_DEFINITION = {
    "title": "配信テスト",
    "overview": "テスト",
    "tasks": [
        {
            "id": "t1",
            "name": "セール告知",
            "role": "担当者",
            "trigger": "手動",
            "steps": ["全員に一斉配信する"],
            "exception_handling": [],
            "notifications": [],
        }
    ],
    "roles": [{"name": "担当者", "responsibilities": ["実行"]}],
    "assumptions": [],
    "open_questions": [],
}


class TestPlanEndpoint:
    """POST /api/plan のテスト。"""

    def test_正常系_planが生成される(self) -> None:
        """有効な definition から plan が生成されることを確認する。

        Variables:
            response:
                /api/plan のレスポンス。
            plan:
                レスポンス内の plan dict。
        """
        response = client.post(
            "/api/plan",
            json={"definition": SAMPLE_DEFINITION},
        )
        assert response.status_code == 200

        plan = response.json()["plan"]
        assert "plan_id" in plan
        assert "steps" in plan
        assert len(plan["steps"]) >= 1

    def test_正常系_definition_idが保持される(self) -> None:
        """definition_id が plan に保持されることを確認する。

        Variables:
            response:
                /api/plan のレスポンス。
            plan:
                レスポンス内の plan dict。
        """
        response = client.post(
            "/api/plan",
            json={"definition_id": "def_test", "definition": SAMPLE_DEFINITION},
        )
        assert response.status_code == 200

        plan = response.json()["plan"]
        assert plan["source_definition_id"] == "def_test"

    def test_異常系_空definitionで400が返る(self) -> None:
        """空の definition で 400 エラーが返ることを確認する。

        Variables:
            response:
                /api/plan のレスポンス。
        """
        response = client.post(
            "/api/plan",
            json={"definition": {}},
        )
        assert response.status_code == 400


class TestDryRunEndpoint:
    """POST /api/dry-run のテスト。"""

    def test_正常系_dryrunでpreviewが返る(self) -> None:
        """dry-run 実行で preview が返ることを確認する。

        Variables:
            plan_response:
                /api/plan のレスポンス。
            plan:
                生成された plan dict。
            response:
                /api/dry-run のレスポンス。
            preview:
                dry-run の preview dict。
        """
        # まず plan を生成
        plan_response = client.post(
            "/api/plan",
            json={"definition": SAMPLE_DEFINITION},
        )
        plan = plan_response.json()["plan"]

        # dry-run を実行
        response = client.post("/api/dry-run", json={"plan": plan})
        assert response.status_code == 200

        preview = response.json()["preview"]
        assert preview["status"] == "dry_run_completed"
        assert "preview" in preview

    def test_異常系_不正なplanで400が返る(self) -> None:
        """不正な plan 形式で 400 エラーが返ることを確認する。

        Variables:
            response:
                /api/dry-run のレスポンス。
        """
        response = client.post(
            "/api/dry-run",
            json={"plan": {"invalid": "data"}},
        )
        assert response.status_code == 400


class TestExecuteEndpoint:
    """POST /api/execute のテスト。"""

    def test_正常系_承認済みで実行が成功する(self) -> None:
        """承認済みで execute が success を返すことを確認する。

        Variables:
            plan_response:
                /api/plan のレスポンス。
            plan:
                生成された plan dict。
            response:
                /api/execute のレスポンス。
            result:
                実行結果 dict。
        """
        # plan を生成
        plan_response = client.post(
            "/api/plan",
            json={"definition": SAMPLE_DEFINITION},
        )
        plan = plan_response.json()["plan"]

        # execute を実行
        response = client.post(
            "/api/execute",
            json={"plan": plan, "approved": True},
        )
        assert response.status_code == 200

        result = response.json()["result"]
        assert result["status"] == "success"

    def test_正常系_未承認でbroadcastがblockedになる(self) -> None:
        """未承認で broadcast.schedule が blocked になることを確認する。

        Variables:
            plan_response:
                /api/plan のレスポンス。
            plan:
                配信タスクを含む plan dict。
            response:
                /api/execute のレスポンス。
            result:
                実行結果 dict。
            blocked_steps:
                blocked ステータスの step 結果リスト。
        """
        # 配信タスクの plan を生成
        plan_response = client.post(
            "/api/plan",
            json={"definition": BROADCAST_DEFINITION},
        )
        plan = plan_response.json()["plan"]

        # 未承認で execute
        response = client.post(
            "/api/execute",
            json={"plan": plan, "approved": False},
        )
        assert response.status_code == 200

        result = response.json()["result"]
        # blocked な step が存在する
        blocked_steps = [
            sr for sr in result["step_results"] if sr["status"] == "blocked"
        ]
        assert len(blocked_steps) >= 1

    def test_一連のフロー_convert_plan_dryrun_execute(self) -> None:
        """convert → plan → dry-run → execute の一連のフローが動作することを確認する。

        Variables:
            convert_response:
                /api/convert のレスポンス。
            definition:
                変換された業務定義。
            plan_response:
                /api/plan のレスポンス。
            plan:
                生成された plan dict。
            dryrun_response:
                /api/dry-run のレスポンス。
            exec_response:
                /api/execute のレスポンス。
        """
        # 1. convert
        convert_response = client.post(
            "/api/convert",
            json={"text": "申請者がVIPタグを付与する"},
        )
        assert convert_response.status_code == 200
        definition = convert_response.json()["definition"]

        # 2. plan
        plan_response = client.post(
            "/api/plan",
            json={"definition": definition},
        )
        assert plan_response.status_code == 200
        plan = plan_response.json()["plan"]

        # 3. dry-run
        dryrun_response = client.post("/api/dry-run", json={"plan": plan})
        assert dryrun_response.status_code == 200

        # 4. execute
        exec_response = client.post(
            "/api/execute",
            json={"plan": plan, "approved": True},
        )
        assert exec_response.status_code == 200
