"""
ワーカー状態 API のテスト。

本モジュールは routes_worker_status の GET /api/workers/status が
正しいレスポンスを返すことを検証する。

入出力: TestClient でエンドポイントを呼び出し、レスポンスを検証する。
制約: 外部 LLM は使わない。テスト用 in-memory DB を使用する。

Note:
    - 空 DB では workers が空リストであることを確認する
    - WorkerTaskLogModel 挿入後に workers にレコードが現れることを確認する
"""

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.db.models import WorkerTaskLogModel
from app.main import app

# テスト用 HTTP クライアント
client = TestClient(app)


def test_get_worker_status_returns_200() -> None:
    """GET /api/workers/status が 200 を返すことを確認する。

    Variables:
        resp: /api/workers/status のレスポンス
        body: レスポンスの JSON

    Note:
        - scheduler_enabled フィールドが存在すること
    """
    resp = client.get("/api/workers/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "workers" in body
    assert "scheduler_enabled" in body
    assert isinstance(body["scheduler_enabled"], bool)


def test_workers_list_empty_when_no_logs(db_session) -> None:
    """worker_task_logs が空の場合に workers が空リストであることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        resp: /api/workers/status のレスポンス
        body: レスポンスの JSON

    Note:
        - 初期状態では worker_task_logs にレコードがない
    """
    resp = client.get("/api/workers/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["workers"] == []


def test_worker_appears_after_inserting_log(db_session) -> None:
    """WorkerTaskLogModel 挿入後に workers にレコードが現れることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        log_entry: テスト用の WorkerTaskLogModel レコード
        resp: /api/workers/status のレスポンス
        body: レスポンスの JSON
        worker: レスポンス内のワーカー情報

    Note:
        - DB にログを挿入してからエンドポイントを呼び出す
        - task_name, status, processed_count, error_count が正しいこと
    """
    # worker_task_logs にレコードを挿入
    log_entry = WorkerTaskLogModel(
        id=str(uuid.uuid4()),
        task_name="broadcast_sender",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        processed_count=5,
        error_count=1,
        status="completed",
    )
    db_session.add(log_entry)
    db_session.flush()

    # エンドポイント呼び出し
    resp = client.get("/api/workers/status")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["workers"]) == 1

    worker = body["workers"][0]
    assert worker["task_name"] == "broadcast_sender"
    assert worker["status"] == "completed"
    assert worker["processed_count"] == 5
    assert worker["error_count"] == 1
