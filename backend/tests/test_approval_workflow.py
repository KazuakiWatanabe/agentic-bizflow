"""
承認ワークフロー CRUD と execute 統合のテスト。

本モジュールは承認リクエストの作成・一覧取得・承認・却下の
CRUD 操作と、broadcast を含む plan での承認リクエスト自動作成を検証する。

入出力: TestClient で承認 API エンドポイントを呼び出す。
制約: 外部 LLM は使わない。

Note:
    - broadcast を含む plan は requires_approval=True となる
    - pending → approved / rejected に遷移する
    - pending 以外の状態を再変更すると 400 を返す
    - 存在しない approval_id で 404 を返す
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# broadcast を含む BusinessDefinition（requires_approval=True になる）
_BROADCAST_DEFINITION = {
    "title": "配信テスト",
    "tasks": [
        {
            "name": "全員に告知配信",
            "steps": ["全員に告知メッセージを一斉配信する"],
        }
    ],
    "roles": [],
}

# 通常の BusinessDefinition（タグ付与のみ）
_SIMPLE_DEFINITION = {
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


def _create_broadcast_plan() -> dict:
    """broadcast を含むテスト用 plan を生成するヘルパー。

    Returns:
        plan の dict 表現

    Note:
        - broadcast.schedule は承認必須のため requires_approval=True になる
    """
    resp = client.post("/api/plan", json={"definition": _BROADCAST_DEFINITION})
    assert resp.status_code == 200
    return resp.json()["plan"]


def test_broadcast_plan_creates_approval_request() -> None:
    """broadcast を含む plan が承認リクエストを自動作成することを確認する。

    Variables:
        plan: broadcast を含む plan
        resp_approvals: GET /api/approvals のレスポンス
        approvals: 承認リクエスト一覧
        matched: 該当 plan の承認リクエスト

    Note:
        - requires_approval=True の plan で approval_requests が作成される
    """
    plan = _create_broadcast_plan()
    plan_id = plan["plan_id"]

    resp_approvals = client.get("/api/approvals")
    assert resp_approvals.status_code == 200
    approvals = resp_approvals.json()["approvals"]

    # 該当 plan の承認リクエストが存在する
    matched = [a for a in approvals if a["plan_id"] == plan_id]
    assert len(matched) >= 1
    assert matched[0]["status"] == "pending"


def test_get_approvals_returns_pending() -> None:
    """GET /api/approvals が pending の承認リクエストを返すことを確認する。

    Variables:
        plan: broadcast を含む plan
        resp: GET /api/approvals のレスポンス
        body: レスポンスの JSON
        pending_list: pending 状態の承認リクエスト

    Note:
        - status=pending でフィルタして取得する
    """
    _create_broadcast_plan()

    resp = client.get("/api/approvals", params={"status": "pending"})
    assert resp.status_code == 200
    body = resp.json()
    assert "approvals" in body
    pending_list = body["approvals"]
    assert len(pending_list) >= 1
    for item in pending_list:
        assert item["status"] == "pending"


def test_approve_changes_status_to_approved() -> None:
    """POST /api/approvals/{id}/approve で status が approved に変わることを確認する。

    Variables:
        plan: broadcast を含む plan
        approvals: 承認リクエスト一覧
        approval_id: 対象の承認リクエスト ID
        resp_approve: approve のレスポンス
        body: レスポンスの JSON
    """
    plan = _create_broadcast_plan()
    plan_id = plan["plan_id"]

    resp_list = client.get("/api/approvals")
    approvals = resp_list.json()["approvals"]
    matched = [a for a in approvals if a["plan_id"] == plan_id]
    approval_id = matched[0]["id"]

    resp_approve = client.post(
        f"/api/approvals/{approval_id}/approve",
        json={"decided_by": "admin", "reason": "承認します"},
    )
    assert resp_approve.status_code == 200
    body = resp_approve.json()
    assert body["status"] == "approved"
    assert body["decided_by"] == "admin"


def test_reject_changes_status_to_rejected() -> None:
    """POST /api/approvals/{id}/reject で status が rejected に変わることを確認する。

    Variables:
        plan: broadcast を含む plan
        approvals: 承認リクエスト一覧
        approval_id: 対象の承認リクエスト ID
        resp_reject: reject のレスポンス
        body: レスポンスの JSON
    """
    plan = _create_broadcast_plan()
    plan_id = plan["plan_id"]

    resp_list = client.get("/api/approvals")
    approvals = resp_list.json()["approvals"]
    matched = [a for a in approvals if a["plan_id"] == plan_id]
    approval_id = matched[0]["id"]

    resp_reject = client.post(
        f"/api/approvals/{approval_id}/reject",
        json={"decided_by": "admin", "reason": "却下理由"},
    )
    assert resp_reject.status_code == 200
    body = resp_reject.json()
    assert body["status"] == "rejected"
    assert body["reason"] == "却下理由"


def test_non_pending_approval_returns_400() -> None:
    """pending でない承認リクエストに対する approve/reject が 400 を返すことを確認する。

    Variables:
        plan: broadcast を含む plan
        approval_id: 対象の承認リクエスト ID
        resp_again: 2 回目の approve のレスポンス

    Note:
        - 一度 approved にした後の再承認は 400 となる
    """
    plan = _create_broadcast_plan()
    plan_id = plan["plan_id"]

    resp_list = client.get("/api/approvals")
    approvals = resp_list.json()["approvals"]
    matched = [a for a in approvals if a["plan_id"] == plan_id]
    approval_id = matched[0]["id"]

    # 一度 approve する
    client.post(f"/api/approvals/{approval_id}/approve")

    # 再度 approve を試みる → 400
    resp_again = client.post(f"/api/approvals/{approval_id}/approve")
    assert resp_again.status_code == 400


def test_nonexistent_approval_returns_404() -> None:
    """存在しない承認リクエスト ID で 404 を返すことを確認する。

    Variables:
        resp_approve: approve のレスポンス
        resp_reject: reject のレスポンス
        resp_get: GET のレスポンス
    """
    resp_approve = client.post("/api/approvals/nonexistent-id/approve")
    assert resp_approve.status_code == 404

    resp_reject = client.post("/api/approvals/nonexistent-id/reject")
    assert resp_reject.status_code == 404

    resp_get = client.get("/api/approvals/nonexistent-id")
    assert resp_get.status_code == 404
