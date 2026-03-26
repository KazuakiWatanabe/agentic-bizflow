"""
後方互換性テスト。

本モジュールは Phase 5 の新 kind 形式（line.tag.assign 等）が導入された後も、
旧形式（tag.assign 等）が引き続き動作することを確認する。

入出力: Registry のエイリアス解決、ExecutionStep の生成、API レスポンスの検証。
制約: 外部 LLM は使わない。

Note:
    - workload_kind_registry シングルトンのエイリアスを検証する
    - ExecutionStep が旧/新どちらの kind でも生成可能であることを検証する
    - POST /api/plan が旧形式 definition でも動作することを検証する
"""

from fastapi.testclient import TestClient

from app.connectors.registry import _ensure_registry_initialized
from app.connectors.workload_kind_registry import workload_kind_registry
from app.main import app
from app.schemas.execution_plan import ExecutionStep

# Registry 初期化（テスト前に全ドメインの kind を登録する）
_ensure_registry_initialized()

# テスト用 HTTP クライアント
client = TestClient(app)


def test_old_kind_tag_assign_resolves_via_alias() -> None:
    """旧 kind 'tag.assign' がエイリアス経由で解決されることを確認する。

    Variables:
        definition: エイリアス解決後の WorkloadKindDefinition

    Note:
        - シングルトン workload_kind_registry を使用する
    """
    definition = workload_kind_registry.get("tag.assign")
    assert definition is not None
    assert definition.kind == "line.tag.assign"
    assert definition.domain == "line"


def test_old_kind_broadcast_schedule_is_valid() -> None:
    """旧 kind 'broadcast.schedule' が有効と判定されることを確認する。

    Note:
        - is_valid がエイリアス経由で True を返す
    """
    assert workload_kind_registry.is_valid("broadcast.schedule") is True


def test_execution_step_with_old_kind_tag_assign() -> None:
    """旧 kind 'tag.assign' で ExecutionStep を生成できることを確認する。

    Variables:
        step: 旧 kind で生成した ExecutionStep

    Note:
        - WorkloadKind が str 型のため、旧形式もそのまま受け入れられる
    """
    step = ExecutionStep(
        step_id="step_compat_001",
        sequence=1,
        kind="tag.assign",
        connector="line",
        action="tag.assign",
        inputs={"tag_name": "VIP"},
        idempotency_key="key-compat-001",
    )
    assert step.kind == "tag.assign"
    assert step.connector == "line"


def test_execution_step_with_new_kind_line_tag_assign() -> None:
    """新 kind 'line.tag.assign' で ExecutionStep を生成できることを確認する。

    Variables:
        step: 新 kind で生成した ExecutionStep

    Note:
        - Phase 5 の新形式でも問題なく生成可能であることを検証
    """
    step = ExecutionStep(
        step_id="step_compat_002",
        sequence=1,
        kind="line.tag.assign",
        connector="line",
        action="line.tag.assign",
        inputs={"tag_name": "VIP"},
        idempotency_key="key-compat-002",
    )
    assert step.kind == "line.tag.assign"
    assert step.connector == "line"


def test_post_plan_with_old_style_definition() -> None:
    """旧形式の definition で POST /api/plan が動作することを確認する。

    Variables:
        definition: 旧形式の BusinessDefinition（タグ付与キーワードを含む）
        resp: /api/plan のレスポンス
        body: レスポンスの JSON
        plan: 生成された ExecutionPlan

    Note:
        - ExecutionPlanner は KIND_KEYWORDS で旧形式の kind を使用している
        - 旧形式の kind（tag.assign）が steps に含まれることを検証する
    """
    definition = {
        "title": "後方互換テスト業務",
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
    assert "steps" in plan
    assert len(plan["steps"]) > 0

    # ExecutionPlanner は旧形式 KIND_KEYWORDS を使うので tag.assign が生成される
    step_kinds = [s["kind"] for s in plan["steps"]]
    assert "tag.assign" in step_kinds
