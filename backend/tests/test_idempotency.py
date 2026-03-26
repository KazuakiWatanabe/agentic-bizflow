"""
冪等性チェックのテスト。

本モジュールは IdempotencyRepository を使用して
同じ idempotency_key での二重実行が防止されることを検証する。

入出力: db_session 経由で DB を操作し、冪等性動作を確認する。
制約: 外部 LLM は使わない。

Note:
    - 同じ key で 2 回実行すると 2 回目はスキップされる
    - 既存の execute フロー（Phase 2.5/3）が壊れていないことも確認する
"""

from fastapi.testclient import TestClient

from app.db.models import ProcessedIdempotencyKeyModel
from app.db.repositories.idempotency_repo import IdempotencyRepository
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


def test_same_idempotency_key_second_is_skipped(db_session) -> None:
    """同じ idempotency_key で 2 回登録すると 2 回目がスキップされることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        key: テスト用の冪等性キー
        first: 1 回目の登録結果
        is_dup: 2 回目の重複チェック結果

    Note:
        - is_processed が True を返せばスキップ扱い
    """
    key = "test_idem_key_001"

    # 1 回目の登録
    IdempotencyRepository.mark_processed(db_session, key, "step_1", "plan_1")
    db_session.commit()

    # 2 回目: 処理済みと判定される
    is_dup = IdempotencyRepository.is_processed(db_session, key)
    assert is_dup is True


def test_first_execution_result_saved(db_session) -> None:
    """最初の実行結果が正常に保存されることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        key: テスト用の冪等性キー
        record: 保存された ProcessedIdempotencyKeyModel

    Note:
        - mark_processed 後に DB にレコードが存在する
    """
    key = "test_idem_key_002"

    IdempotencyRepository.mark_processed(db_session, key, "step_a", "plan_a")
    db_session.commit()

    # DB にレコードが存在する
    record = (
        db_session.query(ProcessedIdempotencyKeyModel)
        .filter_by(idempotency_key=key)
        .first()
    )
    assert record is not None
    assert record.step_id == "step_a"
    assert record.plan_id == "plan_a"
    assert record.processed_at is not None


def test_unprocessed_key_returns_false(db_session) -> None:
    """未登録のキーに対して is_processed が False を返すことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        result: is_processed の結果
    """
    result = IdempotencyRepository.is_processed(db_session, "nonexistent_key_999")
    assert result is False


def test_existing_execute_flow_not_broken() -> None:
    """既存の execute フロー（Phase 2.5/3）が壊れていないことを確認する。

    Variables:
        plan: POST /api/plan で生成された plan
        resp_exec: POST /api/execute のレスポンス
        body: レスポンスの JSON

    Note:
        - Phase 2.5/3 の基本的な plan → execute フローが動作する
    """
    resp_plan = client.post("/api/plan", json={"definition": _DEFINITION})
    assert resp_plan.status_code == 200
    plan = resp_plan.json()["plan"]

    resp_exec = client.post(
        "/api/execute",
        json={"plan": plan, "approved": True},
    )
    assert resp_exec.status_code == 200
    body = resp_exec.json()
    assert "result" in body
    assert "execution_id" in body["result"]
