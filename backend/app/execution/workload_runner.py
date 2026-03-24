"""
ExecutionPlan を受け取り実行する WorkloadRunner を提供する。

本モジュールは ExecutionPlan の各 step を connector 経由で実行し、
ExecutionResult または DryRunPreview を返す。

入出力: ExecutionPlan → ExecutionResult / DryRunPreview
制約: 業務定義の解釈は行わない。connector registry 経由で connector を解決する。

Note:
    - dry_run=True の場合は connector.dry_run() を呼び、DryRunPreview を返す
    - requires_approval=True で未承認の step は status=blocked とする
    - step 失敗時は後続 step を skipped にする
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.connectors.base_connector import BaseConnector
from app.schemas.execution_plan import ExecutionPlan
from app.schemas.execution_result import (
    DryRunPreview,
    ExecutionResult,
    ExecutionStatus,
    StepResult,
)

# --- ロガー ---
logger = logging.getLogger(__name__)


class WorkloadRunner:
    """ExecutionPlan を受け取り、各 step を実行する。

    connector registry（dict）から connector 名で解決し、
    各 step の action を実行して結果を集約する。

    主要メソッド:
        run: ExecutionPlan を実行し、結果を返す

    制約:
        - 業務定義の解釈は行わない
        - connector の具象実装を直接 import しない

    Variables:
        _registry:
            connector 名 → BaseConnector インスタンスのマッピング。

    Note:
        - registry に存在しない connector は failed として処理する
    """

    def __init__(self, registry: Optional[Dict[str, BaseConnector]] = None) -> None:
        """WorkloadRunner を初期化する。

        Args:
            registry: connector 名 → BaseConnector のマッピング

        Note:
            - registry が None の場合は空の dict で初期化する
        """
        # connector 名 → BaseConnector インスタンスのマッピング
        self._registry: Dict[str, BaseConnector] = registry or {}

    def run(
        self,
        plan: ExecutionPlan,
        dry_run: bool = False,
        approved: bool = False,
    ) -> Any:
        """ExecutionPlan を実行する。

        Args:
            plan: 実行対象の ExecutionPlan
            dry_run: True の場合は副作用なしの DryRunPreview を返す
            approved: 承認済みかどうか

        Returns:
            dry_run=True → DryRunPreview
            dry_run=False → ExecutionResult

        Variables:
            execution_id:
                実行の一意識別子。
            started_at:
                実行開始日時。
            step_results:
                各 step の実行結果リスト。
            has_failure:
                いずれかの step が失敗したかどうか。
            errors:
                実行中のエラーメッセージ一覧。
            warnings:
                実行中の警告メッセージ一覧。

        Note:
            - dry-run は承認なしでも常に実行可能
            - 承認必須 step が未承認時は blocked を返す
            - step 失敗時は後続 step を skipped にする
        """
        if dry_run:
            return self._run_dry(plan)
        return self._run_execute(plan, approved)

    def _run_dry(self, plan: ExecutionPlan) -> DryRunPreview:
        """dry-run を実行し、DryRunPreview を返す。

        Args:
            plan: 実行対象の ExecutionPlan

        Returns:
            DryRunPreview モデル

        Variables:
            previews:
                各 step のプレビューテキストリスト。
            warnings:
                ユーザーへの警告メッセージ。
            total_target_count:
                推定対象ユーザー数の合計。

        Note:
            - 外部システムへの書き込みは一切行わない
            - 承認なしでも実行可能
        """
        previews: List[str] = []
        warnings: List[str] = []
        total_target_count = 0

        for step in plan.steps:
            # connector を registry から解決
            connector = self._registry.get(step.connector)
            if connector is None:
                previews.append(
                    f"{step.kind}: connector '{step.connector}' が未登録です"
                )
                continue

            # connector の dry_run を呼ぶ
            result = connector.dry_run(step.action, step.inputs)
            preview_text = result.get("preview", f"{step.kind} を実行します")
            previews.append(preview_text)

            # 推定対象数を集約
            count = result.get("estimated_target_count", 0)
            if count:
                total_target_count += count

            # 承認が必要な step には警告を追加
            if step.requires_approval:
                warnings.append(f"{step.kind} は承認後にのみ実行可能です")

        logger.info(
            "dry-run 完了: plan_id=%s, steps=%d",
            plan.plan_id,
            len(plan.steps),
        )

        return DryRunPreview(
            plan_id=plan.plan_id,
            status="dry_run_completed",
            warnings=warnings,
            preview=previews,
            estimated_target_count=total_target_count if total_target_count else None,
        )

    def _run_execute(self, plan: ExecutionPlan, approved: bool) -> ExecutionResult:
        """本実行を行い、ExecutionResult を返す。

        Args:
            plan: 実行対象の ExecutionPlan
            approved: 承認済みかどうか

        Returns:
            ExecutionResult モデル

        Variables:
            execution_id:
                実行の一意識別子。
            started_at:
                実行開始日時。
            step_results:
                各 step の実行結果リスト。
            has_failure:
                いずれかの step が失敗したかどうかのフラグ。
            errors:
                実行中のエラーメッセージ一覧。
            warnings:
                実行中の警告メッセージ一覧。

        Note:
            - 承認必須 step が未承認時は blocked として処理する
            - step 失敗時は後続 step を skipped にする
        """
        # 実行の一意識別子
        execution_id = f"exec_{uuid.uuid4().hex[:6]}"
        # 実行開始日時
        started_at = datetime.now(timezone.utc)

        step_results: List[StepResult] = []
        # いずれかの step が失敗したかどうか
        has_failure = False
        errors: List[str] = []
        warnings: List[str] = []

        for step in plan.steps:
            # 前の step が失敗した場合、後続 step を skipped にする
            if has_failure:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        status="skipped",
                        message="前のステップが失敗したためスキップしました",
                    )
                )
                continue

            # 承認必須 step が未承認の場合は blocked
            if step.requires_approval and not approved:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        status="blocked",
                        error_code="APPROVAL_REQUIRED",
                        message=f"{step.kind} は承認が必要です",
                    )
                )
                warnings.append(f"{step.step_id} は承認が必要です")
                continue

            # connector を registry から解決
            connector = self._registry.get(step.connector)
            if connector is None:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        status="failed",
                        error_code="CONNECTOR_NOT_FOUND",
                        message=f"connector '{step.connector}' が未登録です",
                    )
                )
                has_failure = True
                errors.append(
                    f"{step.step_id}: connector '{step.connector}' が未登録です"
                )
                continue

            # connector の execute を呼ぶ
            try:
                result = connector.execute(step.action, step.inputs)
            except Exception as exc:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        status="failed",
                        error_code="EXECUTION_ERROR",
                        message=str(exc),
                    )
                )
                has_failure = True
                errors.append(f"{step.step_id}: {exc}")
                logger.error(
                    "step 実行エラー: step_id=%s, error=%s",
                    step.step_id,
                    str(exc),
                )
                continue

            # connector の返却値から status を判定
            step_status = result.get("status", "failed")
            if step_status == "success":
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        status="success",
                        message=result.get("message", ""),
                    )
                )
            else:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        status="failed",
                        error_code=result.get("error_code", "UNKNOWN"),
                        message=result.get("message", ""),
                    )
                )
                has_failure = True
                errors.append(
                    f"{step.step_id}: {result.get('message', 'unknown error')}"
                )

        # 実行完了日時
        finished_at = datetime.now(timezone.utc)

        # 全体ステータスを決定
        overall_status = self._determine_overall_status(step_results)

        logger.info(
            "実行完了: execution_id=%s, plan_id=%s, status=%s",
            execution_id,
            plan.plan_id,
            overall_status,
        )

        return ExecutionResult(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            status=overall_status,
            started_at=started_at,
            finished_at=finished_at,
            step_results=step_results,
            errors=errors,
            warnings=warnings,
        )

    def _determine_overall_status(
        self, step_results: List[StepResult]
    ) -> ExecutionStatus:
        """全体のステータスを決定する。

        Args:
            step_results: 各 step の実行結果リスト

        Returns:
            全体の ExecutionStatus

        Variables:
            statuses:
                各 step のステータス集合。

        Note:
            - 全 step が success → success
            - 全 step が blocked → blocked
            - success と blocked/skipped が混在 → partial_success
            - failed が含まれ success もある → partial_success
            - failed のみ → failed
        """
        if not step_results:
            return "success"

        # 各 step のステータスを集約
        statuses = {r.status for r in step_results}

        if statuses == {"success"}:
            return "success"
        if statuses == {"blocked"}:
            return "blocked"
        if "success" in statuses:
            return "partial_success"
        return "failed"
