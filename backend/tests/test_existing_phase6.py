"""
Phase 6 の既存エンドポイント・モジュール回帰テスト。

本モジュールは Phase 7 の新機能追加によって
Phase 6 の /api/workloads/summary, /api/workers/status, live_line_connector が
壊れていないことを確認する。

入出力: TestClient で各エンドポイントを呼び出す。
制約: 外部 LLM は使わない。

Note:
    - 回帰テストのため最優先で実行する
    - Phase 6 の既存レスポンス形式が維持されていることを検証する
"""

from fastapi.testclient import TestClient

from app.main import app

# テスト用 HTTP クライアント
client = TestClient(app)


def test_get_workloads_summary_returns_200() -> None:
    """GET /api/workloads/summary が 200 を返すことを確認する。

    Variables:
        resp: /api/workloads/summary のレスポンス
        body: レスポンスの JSON

    Note:
        - Phase 6 で追加されたサマリーエンドポイントの回帰テスト
    """
    resp = client.get("/api/workloads/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "scenarios" in body
    assert "broadcasts" in body
    assert "reminders" in body
    assert "tags" in body


def test_get_workers_status_returns_200() -> None:
    """GET /api/workers/status が 200 を返すことを確認する。

    Variables:
        resp: /api/workers/status のレスポンス
        body: レスポンスの JSON

    Note:
        - Phase 6 で追加されたワーカー状態エンドポイントの回帰テスト
    """
    resp = client.get("/api/workers/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "workers" in body
    assert "scheduler_enabled" in body


def test_live_line_connector_module_imports() -> None:
    """live_line_connector モジュールが正常に import できることを確認する。

    Variables:
        LiveLineConnector: import されたクラス

    Note:
        - Phase 6 で追加された LiveLineConnector が壊れていないことを検証する
        - import 自体が成功することが回帰テストの基準
    """
    from app.connectors.live_line_connector import LiveLineConnector

    assert LiveLineConnector is not None
    assert hasattr(LiveLineConnector, "execute")
    assert hasattr(LiveLineConnector, "dry_run")
    assert hasattr(LiveLineConnector, "capabilities")
