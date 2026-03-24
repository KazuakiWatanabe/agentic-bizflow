"""
BusinessDefinition から ExecutionPlan を生成する ExecutionPlanner を提供する。

本モジュールは Agent 層が生成した BusinessDefinition を受け取り、
ルールベースで workload kind を判定し、実行可能な ExecutionPlan に変換する。

入出力: BusinessDefinition の dict → ExecutionPlan
制約: LLM 呼び出し・外部 API 呼び出しは行わない。

Note:
    - workload kind の判定はキーワードマッチで行う
    - 承認要否は workload kind ごとに決定する
    - risk_level は plan 全体で最もリスクの高い step に合わせる
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Set

from app.schemas.execution_plan import (
    ExecutionPlan,
    ExecutionStep,
    RiskLevel,
    WorkloadKind,
)

# --- ロガー ---
logger = logging.getLogger(__name__)

# --- workload kind 判定用キーワードマップ ---
# 各 workload kind に対応する日本語キーワード
KIND_KEYWORDS: Dict[str, List[str]] = {
    "tag.assign": ["タグ", "付与", "ラベル", "タグ付け"],
    "broadcast.schedule": [
        "配信",
        "一斉",
        "全員",
        "告知",
        "メッセージ送信",
        "ブロードキャスト",
    ],
    "scenario.create": ["シナリオ", "ステップ配信", "フォロー", "ステップ"],
    "scenario.start": ["開始", "対象者", "配信開始", "スタート"],
    "reminder.create": ["リマインド", "リマインダー", "通知予約", "カウントダウン"],
}

# --- 承認が常に必須な workload kind ---
ALWAYS_APPROVAL_REQUIRED: Set[str] = {"broadcast.schedule"}

# --- 承認が条件付きで必要な workload kind ---
CONDITIONAL_APPROVAL_KINDS: Set[str] = {"scenario.start"}

# --- 条件付き承認の閾値（対象人数） ---
CONDITIONAL_APPROVAL_THRESHOLD = 100


class ExecutionPlanner:
    """BusinessDefinition から ExecutionPlan を生成する。

    Agent 層が生成した業務定義を受け取り、
    ルールベースで workload kind を判定して実行計画に変換する。

    主要メソッド:
        plan: BusinessDefinition → ExecutionPlan の変換

    制約:
        - LLM 呼び出しは行わない
        - 外部 API 呼び出しは行わない

    Note:
        - キーワードマッチで workload kind を判定する
        - 判定できない step はスキップする
    """

    def plan(
        self,
        definition: Dict[str, Any],
        definition_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> ExecutionPlan:
        """BusinessDefinition から ExecutionPlan を生成する。

        Args:
            definition: BusinessDefinition の dict 表現
            definition_id: 変換元の BusinessDefinition の識別子
            dry_run: dry-run モードかどうか

        Returns:
            ExecutionPlan モデル

        Variables:
            tasks:
                BusinessDefinition 内のタスク一覧。
            steps:
                生成された ExecutionStep のリスト。
            sequence:
                ステップの実行順序カウンタ。
            plan_id:
                生成された plan の一意識別子。
            requires_approval:
                plan 全体として承認が必要かどうか。
            risk_level:
                plan 全体のリスクレベル。
            warnings:
                ユーザーへの警告メッセージ。
            side_effects:
                予想される副作用の説明。

        Note:
            - tasks が空の場合は空の steps を持つ plan を返す
            - workload kind が判定できない step は生成しない
        """
        # BusinessDefinition 内のタスク一覧を取得
        tasks = definition.get("tasks", [])

        # 各タスクの steps からworkload kind を判定し、ExecutionStep を生成
        steps: List[ExecutionStep] = []
        sequence = 0

        for task in tasks:
            # タスク内の手順テキストを結合して判定に使う
            task_text = self._build_task_text(task)
            # workload kind を判定
            detected_kinds = self._detect_workload_kinds(task_text)

            for kind in detected_kinds:
                sequence += 1
                # 承認要否を判定
                step_requires_approval = self._check_step_approval(kind)
                # ExecutionStep を生成
                step = ExecutionStep(
                    step_id=f"step_{sequence:03d}",
                    sequence=sequence,
                    kind=kind,
                    connector="line",
                    action=kind,
                    inputs=self._build_inputs(kind, task),
                    idempotency_key=str(uuid.uuid4()),
                    requires_approval=step_requires_approval,
                    status="planned",
                )
                steps.append(step)

        # plan 全体の承認要否を判定
        requires_approval = any(s.requires_approval for s in steps)

        # risk_level を判定
        risk_level = self._determine_risk_level(steps)

        # 警告メッセージを生成
        warnings = self._build_warnings(steps)

        # 副作用の説明を生成
        side_effects = self._build_side_effects(steps)

        # plan_id を生成
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        # summary を生成
        summary = self._build_summary(steps)

        logger.info(
            "ExecutionPlan 生成完了: plan_id=%s, steps=%d, risk=%s, approval=%s",
            plan_id,
            len(steps),
            risk_level,
            requires_approval,
        )

        return ExecutionPlan(
            plan_id=plan_id,
            source_definition_id=definition_id,
            dry_run=dry_run,
            requires_approval=requires_approval,
            risk_level=risk_level,
            steps=steps,
            summary=summary,
            warnings=warnings,
            estimated_side_effects=side_effects,
        )

    def _build_task_text(self, task: Dict[str, Any]) -> str:
        """タスクのテキスト情報を結合して返す。

        Args:
            task: タスク定義の dict

        Returns:
            判定用に結合されたテキスト

        Note:
            - name, steps, trigger, notifications を結合する
        """
        parts = []
        # タスク名
        if task.get("name"):
            parts.append(task["name"])
        # トリガー
        if task.get("trigger"):
            parts.append(task["trigger"])
        # 手順一覧
        for step_text in task.get("steps", []):
            parts.append(step_text)
        # 通知内容
        for notification in task.get("notifications", []):
            parts.append(notification)
        return " ".join(parts)

    def _detect_workload_kinds(self, text: str) -> List[WorkloadKind]:
        """テキストから workload kind を判定する。

        Args:
            text: 判定対象のテキスト

        Returns:
            検出された workload kind のリスト（重複なし、優先度順）

        Variables:
            detected:
                検出された workload kind のリスト。

        Note:
            - 複数の kind が検出される場合がある（複合指示）
            - キーワードの一致数が多い kind を優先する
        """
        detected: List[WorkloadKind] = []
        for kind, keywords in KIND_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                detected.append(kind)  # type: ignore[arg-type]

        # scenario.create と scenario.start が同時に検出された場合は両方残す
        # 何も検出されなければ空リストを返す
        return detected

    def _check_step_approval(
        self,
        kind: WorkloadKind,
        target_count: Optional[int] = None,
    ) -> bool:
        """ステップの承認要否を判定する。

        Args:
            kind: workload の種類
            target_count: 対象ユーザー数（scenario.start の条件判定用）

        Returns:
            承認が必要な場合は True

        Note:
            - broadcast.schedule は常に承認必須
            - scenario.start は対象 100 名超で承認必須
        """
        if kind in ALWAYS_APPROVAL_REQUIRED:
            return True
        if kind in CONDITIONAL_APPROVAL_KINDS:
            if (
                target_count is not None
                and target_count > CONDITIONAL_APPROVAL_THRESHOLD
            ):
                return True
        return False

    def _determine_risk_level(self, steps: List[ExecutionStep]) -> RiskLevel:
        """plan 全体の risk_level を判定する。

        Args:
            steps: 実行ステップのリスト

        Returns:
            判定された risk_level

        Variables:
            kinds:
                steps 内の workload kind の集合。
            connectors:
                steps 内の connector 名の集合。

        Note:
            - broadcast.schedule を含む場合は medium 以上
            - 複数の connector にまたがる場合は high
            - 全ステップが create / assign のみなら low
        """
        if not steps:
            return "low"

        # steps 内の workload kind と connector を集約
        kinds = {s.kind for s in steps}
        connectors = {s.connector for s in steps}

        # 複数 connector にまたがる場合は high
        if len(connectors) > 1:
            return "high"

        # broadcast.schedule を含む場合は medium
        if "broadcast.schedule" in kinds:
            return "medium"

        # scenario.start を含む場合は medium
        if "scenario.start" in kinds:
            return "medium"

        # それ以外は low
        return "low"

    def _build_inputs(self, kind: WorkloadKind, task: Dict[str, Any]) -> Dict[str, Any]:
        """ステップの入力パラメータを構築する。

        Args:
            kind: workload の種類
            task: タスク定義の dict

        Returns:
            アクションに渡す入力パラメータ

        Note:
            - Phase 2.5 では最小限の入力パラメータを構築する
        """
        inputs: Dict[str, Any] = {}

        if kind == "tag.assign":
            inputs["tag_name"] = task.get("name", "")
            inputs["target"] = task.get("role", "")
        elif kind == "broadcast.schedule":
            inputs["target_tags"] = []
            inputs["message"] = task.get("name", "")
        elif kind == "scenario.create":
            inputs["scenario_name"] = task.get("name", "")
            inputs["steps"] = task.get("steps", [])
        elif kind == "scenario.start":
            inputs["scenario_name"] = task.get("name", "")
            inputs["target"] = task.get("role", "")
        elif kind == "reminder.create":
            inputs["reminder_name"] = task.get("name", "")
            inputs["steps"] = task.get("steps", [])

        return inputs

    def _build_warnings(self, steps: List[ExecutionStep]) -> List[str]:
        """ユーザーへの警告メッセージを生成する。

        Args:
            steps: 実行ステップのリスト

        Returns:
            警告メッセージのリスト
        """
        warnings: List[str] = []
        for step in steps:
            if step.requires_approval:
                warnings.append(f"{step.kind} は承認後にのみ実行されます")
        return warnings

    def _build_side_effects(self, steps: List[ExecutionStep]) -> List[str]:
        """予想される副作用の説明を生成する。

        Args:
            steps: 実行ステップのリスト

        Returns:
            副作用の説明リスト
        """
        # 副作用の説明マッピング
        effect_map = {
            "tag.assign": "対象ユーザーへのタグ付与",
            "broadcast.schedule": "対象ユーザーへの LINE メッセージ送信",
            "scenario.create": "ステップ配信シナリオの作成",
            "scenario.start": "対象ユーザーへのシナリオ配信開始",
            "reminder.create": "リマインダーの作成",
        }
        effects: List[str] = []
        seen: Set[str] = set()
        for step in steps:
            effect = effect_map.get(step.kind)
            if effect and effect not in seen:
                effects.append(effect)
                seen.add(effect)
        return effects

    def _build_summary(self, steps: List[ExecutionStep]) -> str:
        """実行計画の要約説明を生成する。

        Args:
            steps: 実行ステップのリスト

        Returns:
            要約テキスト
        """
        if not steps:
            return "実行ステップなし"

        # 各 kind の日本語名
        kind_names = {
            "tag.assign": "タグ付与",
            "broadcast.schedule": "一斉配信予約",
            "scenario.create": "シナリオ作成",
            "scenario.start": "シナリオ配信開始",
            "reminder.create": "リマインダー作成",
        }
        parts = []
        for step in steps:
            name = kind_names.get(step.kind, step.kind)
            parts.append(name)
        return "、".join(parts) + "を実行します"
