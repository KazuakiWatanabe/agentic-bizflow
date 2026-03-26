"""
Phase 4 の既存エンドポイント・モジュール回帰テスト。

本モジュールは Phase 5 の新機能追加によって
Phase 4 の /api/approvals, delivery_window, WorkloadRunner, scheduler が
壊れていないことを確認する。

入出力: TestClient で各エンドポイントを呼び出す。import の成功を確認する。
制約: 外部 LLM は使わない。

Note:
    - 回帰テストのため最優先で実行する
    - Phase 4 の既存レスポンス形式が維持されていることを検証する
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app

# テスト用 HTTP クライアント
client = TestClient(app)


def test_get_approvals_returns_200() -> None:
    """GET /api/approvals が 200 を返すことを確認する。

    Variables:
        resp: /api/approvals のレスポンス
        body: レスポンスの JSON

    Note:
        - Phase 4 で追加された承認一覧エンドポイントの回帰テスト
    """
    resp = client.get("/api/approvals")
    assert resp.status_code == 200
    body = resp.json()
    assert "approvals" in body
    assert "total" in body


def test_delivery_window_import() -> None:
    """delivery_window モジュールが正常に import できることを確認する。

    Note:
        - Phase 4 で追加された delivery_window の回帰テスト
        - import に失敗する場合は Phase 5 の変更が壊している可能性がある
    """
    from app.workers.delivery_window import is_within_delivery_window  # noqa: F401

    # import が成功すればモジュールは壊れていない
    assert callable(is_within_delivery_window)


def test_workload_runner_with_mock_connector() -> None:
    """WorkloadRunner が mock connector で正常に動作することを確認する。

    Variables:
        mock_connector: dry_run / execute をモック化した connector
        runner: テスト対象の WorkloadRunner
        plan: テスト用の ExecutionPlan
        result: dry-run の結果

    Note:
        - Phase 4 以前から存在する WorkloadRunner が Phase 5 で壊れていないか確認
    """
    from app.connectors.mock_line_connector import MockLineConnector
    from app.execution.workload_runner import WorkloadRunner
    from app.schemas.execution_plan import ExecutionPlan, ExecutionStep

    # mock connector を準備
    mock_connector = MockLineConnector()
    runner = WorkloadRunner(registry={"line": mock_connector})

    # テスト用 step と plan を構築
    step = ExecutionStep(
        step_id="step_regr_001",
        sequence=1,
        kind="tag.assign",
        connector="line",
        action="tag.assign",
        inputs={"tag_name": "VIP"},
        idempotency_key="key-regr-001",
    )
    plan = ExecutionPlan(plan_id="plan_regr_test", steps=[step])

    # dry-run で動作確認
    result = runner.run(plan, dry_run=True)
    assert result.status == "dry_run_completed"

    # 本実行で動作確認
    mock_connector_exec = MockLineConnector()
    mock_connector_exec.execute = MagicMock(
        return_value={"status": "success", "message": "ok"}
    )
    runner_exec = WorkloadRunner(registry={"line": mock_connector_exec})
    result_exec = runner_exec.run(plan, dry_run=False, approved=True)
    assert result_exec.status == "success"


def test_scheduler_module_can_be_imported() -> None:
    """scheduler モジュールが正常に import できることを確認する。

    Note:
        - Phase 4 で追加された scheduler の回帰テスト
        - start_scheduler / stop_scheduler が callable であることを確認
    """
    from app.workers.scheduler import start_scheduler, stop_scheduler  # noqa: F401

    assert callable(start_scheduler)
    assert callable(stop_scheduler)
