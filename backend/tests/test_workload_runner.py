"""
WorkloadRunner のテスト。

本モジュールは ExecutionPlan の実行ロジックを検証する。
dry-run / 本実行 / 承認チェック / 失敗時 skip の動作を確認する。

入出力: ExecutionPlan → ExecutionResult / DryRunPreview。
制約: mock connector を使用する。外部 LLM は使わない。

Note:
    - dry-run が副作用を起こさないこと
    - 本実行で connector.execute() が呼ばれること
    - 承認必須時に execute が即実行されないこと
    - step 失敗時に後続が skipped になること
"""

from unittest.mock import MagicMock

from app.connectors.mock_line_connector import MockLineConnector
from app.execution.workload_runner import WorkloadRunner
from app.schemas.execution_plan import ExecutionPlan, ExecutionStep


def _make_step(
    step_id="step_001",
    sequence=1,
    kind="tag.assign",
    requires_approval=False,
):
    """テスト用の ExecutionStep を生成するヘルパー。

    Args:
        step_id: ステップ ID
        sequence: 実行順序
        kind: workload kind
        requires_approval: 承認要否

    Returns:
        ExecutionStep インスタンス
    """
    return ExecutionStep(
        step_id=step_id,
        sequence=sequence,
        kind=kind,
        connector="line",
        action=kind,
        inputs={},
        idempotency_key=f"key-{step_id}",
        requires_approval=requires_approval,
    )


def _make_plan(steps, plan_id="plan_test"):
    """テスト用の ExecutionPlan を生成するヘルパー。

    Args:
        steps: ExecutionStep のリスト
        plan_id: plan の識別子

    Returns:
        ExecutionPlan インスタンス
    """
    return ExecutionPlan(
        plan_id=plan_id,
        steps=steps,
    )


def _make_runner():
    """mock connector を登録した WorkloadRunner を生成するヘルパー。

    Returns:
        WorkloadRunner インスタンス
    """
    # mock connector を registry に登録
    registry = {"line": MockLineConnector()}
    return WorkloadRunner(registry=registry)


class TestWorkloadRunnerDryRun:
    """WorkloadRunner の dry-run テスト。"""

    def test_dryrunが副作用を起こさない(self) -> None:
        """dry-run 実行時に connector.execute() が呼ばれないことを確認する。

        Variables:
            mock_connector:
                execute が呼ばれないことを検証する mock connector。
            runner:
                テスト対象の WorkloadRunner。
            plan:
                テスト用の ExecutionPlan。
            result:
                dry-run の結果。

        Note:
            - mock connector の execute をモック化して呼び出しを検証
        """
        # connector の execute をモック化（副作用なしの検証）
        mock_connector = MockLineConnector()
        mock_connector.execute = MagicMock()
        runner = WorkloadRunner(registry={"line": mock_connector})

        plan = _make_plan([_make_step()])
        result = runner.run(plan, dry_run=True)

        # execute が呼ばれていないことを確認
        mock_connector.execute.assert_not_called()
        assert result.status == "dry_run_completed"

    def test_dryrunでpreviewが返る(self) -> None:
        """dry-run 実行時に preview テキストが返ることを確認する。

        Variables:
            runner:
                テスト対象の WorkloadRunner。
            plan:
                テスト用の ExecutionPlan。
            result:
                dry-run の結果。
        """
        runner = _make_runner()
        plan = _make_plan([_make_step()])
        result = runner.run(plan, dry_run=True)

        assert len(result.preview) > 0

    def test_dryrunは承認なしでも実行可能(self) -> None:
        """承認必須の step があっても dry-run は実行可能であることを確認する。

        Variables:
            runner:
                テスト対象の WorkloadRunner。
            plan:
                承認必須の step を含むテスト用 ExecutionPlan。
            result:
                dry-run の結果。
        """
        runner = _make_runner()
        step = _make_step(kind="broadcast.schedule", requires_approval=True)
        plan = _make_plan([step])
        result = runner.run(plan, dry_run=True)

        assert result.status == "dry_run_completed"


class TestWorkloadRunnerExecute:
    """WorkloadRunner の本実行テスト。"""

    def test_本実行でconnector_executeが呼ばれる(self) -> None:
        """本実行時に connector.execute() が呼ばれることを確認する。

        Variables:
            mock_connector:
                execute の呼び出しを検証する mock connector。
            runner:
                テスト対象の WorkloadRunner。
            plan:
                テスト用の ExecutionPlan。
            result:
                実行結果。

        Note:
            - mock connector の execute をモック化して呼び出し回数を検証
        """
        # connector の execute をモック化
        mock_connector = MockLineConnector()
        original_execute = mock_connector.execute
        mock_connector.execute = MagicMock(side_effect=original_execute)
        runner = WorkloadRunner(registry={"line": mock_connector})

        plan = _make_plan([_make_step()])
        result = runner.run(plan, dry_run=False, approved=True)

        # execute が呼ばれたことを確認
        mock_connector.execute.assert_called_once()
        assert result.status == "success"

    def test_承認必須stepが未承認時にblockedが返る(self) -> None:
        """承認必須の step が未承認の場合に blocked が返ることを確認する。

        Variables:
            runner:
                テスト対象の WorkloadRunner。
            step:
                承認必須の ExecutionStep。
            plan:
                テスト用の ExecutionPlan。
            result:
                実行結果。
        """
        runner = _make_runner()
        step = _make_step(kind="broadcast.schedule", requires_approval=True)
        plan = _make_plan([step])
        result = runner.run(plan, dry_run=False, approved=False)

        assert result.step_results[0].status == "blocked"
        assert result.step_results[0].error_code == "APPROVAL_REQUIRED"

    def test_step失敗時に後続がskippedになる(self) -> None:
        """step が失敗した場合に後続 step が skipped になることを確認する。

        Variables:
            mock_connector:
                最初の execute で失敗を返す mock connector。
            runner:
                テスト対象の WorkloadRunner。
            plan:
                2 step の ExecutionPlan。
            result:
                実行結果。

        Note:
            - 最初の step で失敗を返し、2 番目の step が skipped になることを検証
        """
        # 最初の execute で失敗を返す connector
        mock_connector = MockLineConnector()
        call_count = 0

        def failing_execute(action, inputs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "status": "failed",
                    "error_code": "TEST_FAIL",
                    "message": "テスト失敗",
                }
            return {"status": "success", "message": "成功"}

        mock_connector.execute = failing_execute
        runner = WorkloadRunner(registry={"line": mock_connector})

        plan = _make_plan(
            [
                _make_step(step_id="step_001", sequence=1),
                _make_step(step_id="step_002", sequence=2),
            ]
        )
        result = runner.run(plan, dry_run=False, approved=True)

        assert result.step_results[0].status == "failed"
        assert result.step_results[1].status == "skipped"

    def test_承認済みの場合は正常に実行される(self) -> None:
        """承認済みの場合に承認必須 step も正常に実行されることを確認する。

        Variables:
            runner:
                テスト対象の WorkloadRunner。
            step:
                承認必須の ExecutionStep。
            plan:
                テスト用の ExecutionPlan。
            result:
                実行結果。
        """
        runner = _make_runner()
        step = _make_step(kind="broadcast.schedule", requires_approval=True)
        plan = _make_plan([step])
        result = runner.run(plan, dry_run=False, approved=True)

        assert result.step_results[0].status == "success"
        assert result.status == "success"

    def test_idempotency_keyが各stepに付与されている(self) -> None:
        """各 step に idempotency_key が付与されていることを確認する。

        Variables:
            plan:
                複数 step の ExecutionPlan。
        """
        plan = _make_plan(
            [
                _make_step(step_id="step_001", sequence=1),
                _make_step(step_id="step_002", sequence=2),
            ]
        )
        for step in plan.steps:
            assert step.idempotency_key is not None
            assert len(step.idempotency_key) > 0

    def test_全stepがsuccessならstatusはsuccess(self) -> None:
        """全 step が success の場合に全体 status が success になることを確認する。

        Variables:
            runner:
                テスト対象の WorkloadRunner。
            plan:
                2 step の ExecutionPlan。
            result:
                実行結果。
        """
        runner = _make_runner()
        plan = _make_plan(
            [
                _make_step(step_id="step_001", sequence=1),
                _make_step(step_id="step_002", sequence=2),
            ]
        )
        result = runner.run(plan, dry_run=False, approved=True)

        assert result.status == "success"
        assert all(sr.status == "success" for sr in result.step_results)

    def test_execution_idが付与される(self) -> None:
        """実行結果に execution_id が付与されることを確認する。

        Variables:
            runner:
                テスト対象の WorkloadRunner。
            plan:
                テスト用の ExecutionPlan。
            result:
                実行結果。
        """
        runner = _make_runner()
        plan = _make_plan([_make_step()])
        result = runner.run(plan, dry_run=False, approved=True)

        assert result.execution_id is not None
        assert result.execution_id.startswith("exec_")
