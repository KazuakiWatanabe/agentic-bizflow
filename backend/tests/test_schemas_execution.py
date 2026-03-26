"""
Phase 2.5 の Pydantic スキーマのバリデーションテスト。

本モジュールは ExecutionPlan / ExecutionResult / ConnectorCapability の
バリデーションが正しく動作することを確認する。

入出力: テストデータ → バリデーション結果。
制約: 外部 LLM は使わない。

Note:
    - extra fields が拒否されること
    - 必須フィールドの欠落でエラーになること
    - kind が不正な値の場合にエラーになること
"""

import pytest
from pydantic import ValidationError

from app.schemas.connector_capability import ConnectorCapability
from app.schemas.execution_plan import ApprovalPolicy, ExecutionPlan, ExecutionStep
from app.schemas.execution_result import DryRunPreview, ExecutionResult, StepResult


class TestExecutionStep:
    """ExecutionStep のバリデーションテスト。"""

    def test_正常系_有効なstepが作成できる(self) -> None:
        """有効なパラメータで ExecutionStep が作成できることを確認する。

        Variables:
            step:
                生成された ExecutionStep インスタンス。
        """
        step = ExecutionStep(
            step_id="step_001",
            sequence=1,
            kind="tag.assign",
            connector="line",
            action="tag.assign",
            inputs={"tag_name": "VIP"},
            idempotency_key="test-key-001",
        )
        assert step.step_id == "step_001"
        assert step.kind == "tag.assign"
        assert step.status == "planned"

    def test_任意のkind文字列でstepが作成できる(self) -> None:
        """Phase 5: kind が str 型となり、任意の文字列を受け付けることを確認する。

        Variables:
            step: 任意の kind で作成した ExecutionStep。

        Note:
            - Phase 5 で WorkloadKind を Literal から str に変更した
            - 検証は Registry 側で行う
        """
        step = ExecutionStep(
            step_id="step_001",
            sequence=1,
            kind="email.broadcast.schedule",
            connector="email",
            action="email.broadcast.schedule",
            inputs={},
            idempotency_key="test-key",
        )
        assert step.kind == "email.broadcast.schedule"

    def test_異常系_sequenceが0以下でエラーになる(self) -> None:
        """sequence に 0 を指定した場合に ValidationError になることを確認する。

        Variables:
            なし（例外のみ検証）。
        """
        with pytest.raises(ValidationError):
            ExecutionStep(
                step_id="step_001",
                sequence=0,
                kind="tag.assign",
                connector="line",
                action="tag.assign",
                inputs={},
                idempotency_key="test-key",
            )

    def test_異常系_extraフィールドが拒否される(self) -> None:
        """extra fields が拒否されることを確認する。

        Variables:
            なし（例外のみ検証）。
        """
        with pytest.raises(ValidationError):
            ExecutionStep(
                step_id="step_001",
                sequence=1,
                kind="tag.assign",
                connector="line",
                action="tag.assign",
                inputs={},
                idempotency_key="test-key",
                unknown_field="bad",
            )


class TestExecutionPlan:
    """ExecutionPlan のバリデーションテスト。"""

    def test_正常系_空stepsのplanが作成できる(self) -> None:
        """steps が空の ExecutionPlan が作成できることを確認する。

        Variables:
            plan:
                生成された ExecutionPlan インスタンス。
        """
        plan = ExecutionPlan(
            plan_id="plan_test",
            steps=[],
        )
        assert plan.plan_id == "plan_test"
        assert plan.risk_level == "low"
        assert plan.requires_approval is False

    def test_正常系_stepsありのplanが作成できる(self) -> None:
        """steps を持つ ExecutionPlan が作成できることを確認する。

        Variables:
            step:
                テスト用の ExecutionStep。
            plan:
                生成された ExecutionPlan インスタンス。
        """
        step = ExecutionStep(
            step_id="step_001",
            sequence=1,
            kind="broadcast.schedule",
            connector="line",
            action="broadcast.schedule",
            inputs={},
            idempotency_key="test-key",
            requires_approval=True,
        )
        plan = ExecutionPlan(
            plan_id="plan_test",
            requires_approval=True,
            risk_level="medium",
            steps=[step],
        )
        assert len(plan.steps) == 1
        assert plan.requires_approval is True
        assert plan.risk_level == "medium"


class TestExecutionResult:
    """ExecutionResult のバリデーションテスト。"""

    def test_正常系_successの結果が作成できる(self) -> None:
        """success ステータスの ExecutionResult が作成できることを確認する。

        Variables:
            result:
                生成された ExecutionResult インスタンス。
        """
        result = ExecutionResult(
            execution_id="exec_test",
            plan_id="plan_test",
            status="success",
            step_results=[
                StepResult(step_id="step_001", status="success", message="完了"),
            ],
        )
        assert result.status == "success"
        assert len(result.step_results) == 1

    def test_異常系_不正なstatusでエラーになる(self) -> None:
        """status に無効な値を指定した場合に ValidationError になることを確認する。

        Variables:
            なし（例外のみ検証）。
        """
        with pytest.raises(ValidationError):
            ExecutionResult(
                execution_id="exec_test",
                plan_id="plan_test",
                status="invalid_status",
            )

    def test_正常系_blockedのstep_resultが作成できる(self) -> None:
        """blocked ステータスの StepResult が作成できることを確認する。

        Variables:
            sr:
                生成された StepResult インスタンス。
        """
        sr = StepResult(
            step_id="step_001",
            status="blocked",
            error_code="APPROVAL_REQUIRED",
            message="承認が必要です",
        )
        assert sr.status == "blocked"
        assert sr.error_code == "APPROVAL_REQUIRED"


class TestDryRunPreview:
    """DryRunPreview のバリデーションテスト。"""

    def test_正常系_previewが作成できる(self) -> None:
        """DryRunPreview が正しく作成できることを確認する。

        Variables:
            preview:
                生成された DryRunPreview インスタンス。
        """
        preview = DryRunPreview(
            plan_id="plan_test",
            preview=["タグを付与します"],
            estimated_target_count=10,
        )
        assert preview.status == "dry_run_completed"
        assert len(preview.preview) == 1


class TestConnectorCapability:
    """ConnectorCapability のバリデーションテスト。"""

    def test_正常系_capabilityが作成できる(self) -> None:
        """ConnectorCapability が正しく作成できることを確認する。

        Variables:
            cap:
                生成された ConnectorCapability インスタンス。
        """
        cap = ConnectorCapability(
            connector="line",
            supported_actions=["tag.assign", "broadcast.schedule"],
            supports_dry_run=True,
        )
        assert cap.connector == "line"
        assert len(cap.supported_actions) == 2


class TestApprovalPolicy:
    """ApprovalPolicy のバリデーションテスト。"""

    def test_正常系_デフォルトでnoneモード(self) -> None:
        """デフォルトの ApprovalPolicy が none モードであることを確認する。

        Variables:
            policy:
                生成された ApprovalPolicy インスタンス。
        """
        policy = ApprovalPolicy()
        assert policy.mode == "none"

    def test_正常系_alwaysモードが設定できる(self) -> None:
        """always モードの ApprovalPolicy が作成できることを確認する。

        Variables:
            policy:
                生成された ApprovalPolicy インスタンス。
        """
        policy = ApprovalPolicy(
            mode="always",
            reason="一斉配信のため常に承認必須",
        )
        assert policy.mode == "always"
        assert policy.reason is not None
