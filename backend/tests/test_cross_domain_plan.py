"""
クロスドメイン（LINE + Email）プランのテスト。

本モジュールは LINE と Email の両方のキーワードを含む definition から
POST /api/plan で複合プランを生成し、POST /api/execute で実行できることを検証する。

入出力: TestClient で /api/plan, /api/execute を呼び出す。
制約: 外部 LLM は使わない。

Note:
    - ExecutionPlanner の KIND_KEYWORDS は旧形式（tag.assign 等）を使用する
    - メール配信のキーワードは KIND_KEYWORDS に含まれていない場合があるため、
      検出される steps は LINE 系のみの可能性がある
    - 主目的はシステムが混合コンセプトで壊れないことの確認
"""

from fastapi.testclient import TestClient

from app.connectors.registry import _ensure_registry_initialized
from app.main import app

# Registry 初期化
_ensure_registry_initialized()

# テスト用 HTTP クライアント
client = TestClient(app)


def test_plan_with_line_and_email_keywords() -> None:
    """LINE + Email キーワードを含む definition からプランを生成できることを確認する。

    Variables:
        definition: LINE（タグ付与）と Email（メール配信）のキーワードを含む定義
        resp: /api/plan のレスポンス
        body: レスポンスの JSON
        plan: 生成された ExecutionPlan
        step_kinds: プラン内の全 step の kind リスト

    Note:
        - ExecutionPlanner の KIND_KEYWORDS は旧形式を使用しているため、
          steps は旧形式の kind（tag.assign 等）で生成される
        - メール配信キーワードは KIND_KEYWORDS に含まれていない場合、
          Email 用の step は生成されない可能性がある
        - 主目的はエラーが発生しないことの確認
    """
    definition = {
        "title": "クロスドメインテスト業務",
        "tasks": [
            {
                "name": "VIPタグ付与",
                "steps": ["対象者にVIPタグを付与する"],
                "role": "担当者",
            },
            {
                "name": "メール配信のお知らせ",
                "steps": ["全員に一斉配信でメール配信する"],
                "role": "管理者",
            },
        ],
        "roles": [
            {"name": "担当者", "responsibilities": ["タグ管理"]},
            {"name": "管理者", "responsibilities": ["配信管理"]},
        ],
    }

    resp = client.post("/api/plan", json={"definition": definition})
    assert resp.status_code == 200

    body = resp.json()
    plan = body["plan"]
    assert "steps" in plan

    # 少なくとも 1 つ以上の step が生成されていること
    assert len(plan["steps"]) >= 1

    # step_kinds を確認（タグ付与が含まれるはず）
    step_kinds = [s["kind"] for s in plan["steps"]]
    assert "tag.assign" in step_kinds


def test_execute_cross_domain_plan() -> None:
    """クロスドメインプランを POST /api/execute で実行できることを確認する。

    Variables:
        definition: タグ付与キーワードを含む定義
        resp_plan: /api/plan のレスポンス
        plan: 生成された ExecutionPlan
        resp_exec: /api/execute のレスポンス
        exec_body: 実行レスポンスの JSON

    Note:
        - tag.assign step は DBLineConnector で正常に実行される
        - 主目的はシステムが混合コンセプトで壊れないことの確認
    """
    definition = {
        "title": "クロスドメイン実行テスト",
        "tasks": [
            {
                "name": "VIPタグ付与",
                "steps": ["対象者にVIPタグを付与する"],
                "role": "担当者",
            },
        ],
        "roles": [{"name": "担当者", "responsibilities": ["タグ管理"]}],
    }

    # plan 生成
    resp_plan = client.post("/api/plan", json={"definition": definition})
    assert resp_plan.status_code == 200
    plan = resp_plan.json()["plan"]

    # plan 実行
    resp_exec = client.post(
        "/api/execute",
        json={"plan": plan, "approved": True},
    )
    assert resp_exec.status_code == 200

    exec_body = resp_exec.json()
    assert "result" in exec_body
    # 実行結果のステータスが返ること（success または partial_success）
    assert exec_body["result"]["status"] in ("success", "partial_success")
