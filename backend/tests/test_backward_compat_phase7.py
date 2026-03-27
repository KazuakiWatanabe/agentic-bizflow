"""
Phase 7 後方互換性テスト。

本モジュールは Phase 7 の Marketing Channel Abstraction 導入後も、
既存のドメイン kind・Phase 5 エイリアス・plan 生成・connector 直接呼び出しが
引き続き正しく動作することを確認する。

入出力: ExecutionStep の生成、API レスポンス、DBLineConnector の実行結果を検証する。
制約: 外部 LLM は使わない。

Note:
    - workload_kind_registry シングルトンのドメイン kind を検証する
    - ExecutionStep が旧/新どちらの kind でも生成可能であることを検証する
    - POST /api/plan が旧形式 definition でも動作することを検証する
    - DBLineConnector に target_id を直接渡しても動作することを検証する
"""

from fastapi.testclient import TestClient

from app.connectors.registry import _ensure_registry_initialized
from app.main import app
from app.schemas.execution_plan import ExecutionStep

# Registry 初期化（テスト前に全ドメインの kind を登録する）
_ensure_registry_initialized()

# テスト用 HTTP クライアント
client = TestClient(app)


def test_domain_kind_line_tag_assign_in_execution_step() -> None:
    """ドメイン kind 'line.tag.assign' で ExecutionStep を生成できることを確認する。

    Variables:
        step: line.tag.assign で生成した ExecutionStep

    Note:
        - Phase 5 の新形式でも問題なく生成可能であることを検証する
    """
    step = ExecutionStep(
        step_id="step_p7_001",
        sequence=1,
        kind="line.tag.assign",
        connector="line",
        action="line.tag.assign",
        inputs={"tag_name": "VIP"},
        idempotency_key="key-p7-001",
    )
    assert step.kind == "line.tag.assign"
    assert step.connector == "line"


def test_phase5_alias_tag_assign_in_execution_step() -> None:
    """Phase 5 エイリアス 'tag.assign' で ExecutionStep を生成できることを確認する。

    Variables:
        step: tag.assign で生成した ExecutionStep

    Note:
        - WorkloadKind が str 型のため、旧形式もそのまま受け入れられる
    """
    step = ExecutionStep(
        step_id="step_p7_002",
        sequence=1,
        kind="tag.assign",
        connector="line",
        action="tag.assign",
        inputs={"tag_name": "VIP"},
        idempotency_key="key-p7-002",
    )
    assert step.kind == "tag.assign"
    assert step.connector == "line"


def test_post_plan_still_generates_plan() -> None:
    """POST /api/plan が既存 definition で plan を生成できることを確認する。

    Variables:
        definition: テスト用の BusinessDefinition
        resp: POST /api/plan のレスポンス
        body: レスポンスの JSON
        plan: 生成された ExecutionPlan

    Note:
        - Phase 5 以前から存在する plan 生成エンドポイントの後方互換テスト
        - definition を渡して plan が生成されることを確認する
    """
    definition = {
        "title": "Phase7 後方互換テスト業務",
        "tasks": [
            {
                "name": "VIPタグ付与",
                "steps": ["対象者にVIPタグを付与する"],
                "role": "担当者",
            }
        ],
        "roles": [{"name": "担当者", "responsibilities": ["タグ管理"]}],
    }

    resp = client.post("/api/plan", json={"definition": definition})
    assert resp.status_code == 200
    body = resp.json()
    plan = body["plan"]
    assert "plan_id" in plan
    assert "steps" in plan
    assert len(plan["steps"]) > 0


def test_target_id_direct_in_db_line_connector(db_session) -> None:
    """DBLineConnector で target_id を直接指定して tag.assign が動作することを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: DBLineConnector インスタンス
        result: execute の結果

    Note:
        - target_id を inputs["target"] に直接渡す旧来の方式が機能すること
        - commit は呼び出し側の責務だが、テストでは flush のみ確認する
    """
    from app.connectors.db_line_connector import DBLineConnector

    connector = DBLineConnector(db=db_session)
    result = connector.execute(
        "tag.assign",
        {"tag_name": "テストタグ", "target": "direct_target_001"},
    )
    assert result["status"] == "success"
    assert "created_records" in result
