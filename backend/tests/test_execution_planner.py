"""
ExecutionPlanner のテスト。

本モジュールは BusinessDefinition → ExecutionPlan の変換ロジックを検証する。
6 パターン以上のテストケースを含む。

入出力: BusinessDefinition dict → ExecutionPlan。
制約: 外部 LLM は使わない。

Note:
    - workload kind の判定が正しいこと
    - 承認要否の判定が正しいこと
    - risk_level の判定が正しいこと
"""

from app.execution.execution_planner import ExecutionPlanner


def _make_definition(tasks):
    """テスト用の BusinessDefinition dict を構築するヘルパー。

    Args:
        tasks: タスク定義のリスト

    Returns:
        BusinessDefinition 形式の dict
    """
    return {
        "title": "テスト",
        "overview": "テスト概要",
        "tasks": tasks,
        "roles": [{"name": "担当者", "responsibilities": ["実行"]}],
        "assumptions": [],
        "open_questions": [],
    }


def _make_task(name, steps=None, notifications=None, role="担当者", trigger="手動"):
    """テスト用のタスク dict を構築するヘルパー。

    Args:
        name: タスク名
        steps: 手順リスト
        notifications: 通知リスト
        role: ロール名
        trigger: トリガー

    Returns:
        タスク定義の dict
    """
    return {
        "id": "t1",
        "name": name,
        "role": role,
        "trigger": trigger,
        "steps": steps or [],
        "exception_handling": [],
        "notifications": notifications or [],
    }


class TestExecutionPlanner:
    """ExecutionPlanner のテスト。"""

    def setup_method(self):
        """各テストの前に ExecutionPlanner を初期化する。

        Variables:
            planner:
                テスト対象の ExecutionPlanner インスタンス。
        """
        # テスト対象の ExecutionPlanner
        self.planner = ExecutionPlanner()

    def test_タグ付与のみ(self) -> None:
        """タグ付与のタスクが tag.assign として判定されることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
        """
        definition = _make_definition(
            [
                _make_task("VIPタグ付与", steps=["VIPタグを付与する"]),
            ]
        )
        plan = self.planner.plan(definition)

        assert len(plan.steps) >= 1
        kinds = {s.kind for s in plan.steps}
        assert "tag.assign" in kinds
        assert plan.requires_approval is False
        assert plan.risk_level == "low"

    def test_一斉配信予約(self) -> None:
        """一斉配信のタスクが broadcast.schedule として判定されることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
        """
        definition = _make_definition(
            [
                _make_task("セール告知配信", steps=["友だち全員に一斉配信する"]),
            ]
        )
        plan = self.planner.plan(definition)

        assert len(plan.steps) >= 1
        kinds = {s.kind for s in plan.steps}
        assert "broadcast.schedule" in kinds
        assert plan.requires_approval is True
        assert plan.risk_level == "medium"

    def test_シナリオ作成(self) -> None:
        """シナリオ作成のタスクが scenario.create として判定されることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
        """
        definition = _make_definition(
            [
                _make_task(
                    "フォローシナリオ", steps=["3日間のステップ配信シナリオを設定する"]
                ),
            ]
        )
        plan = self.planner.plan(definition)

        assert len(plan.steps) >= 1
        kinds = {s.kind for s in plan.steps}
        assert "scenario.create" in kinds

    def test_リマインダー作成_複数ステップ(self) -> None:
        """リマインダー作成のタスクが複数ステップとして生成されることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
        """
        definition = _make_definition(
            [
                _make_task(
                    "セミナーリマインダー",
                    steps=["3日前にリマインド送信", "前日にリマインド送信"],
                ),
            ]
        )
        plan = self.planner.plan(definition)

        assert len(plan.steps) >= 1
        kinds = {s.kind for s in plan.steps}
        assert "reminder.create" in kinds

    def test_複合指示_タグとシナリオ(self) -> None:
        """タグ付与とシナリオ作成の複合指示が正しく変換されることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
        """
        definition = _make_definition(
            [
                _make_task(
                    "VIPタグ付与と配信シナリオ",
                    steps=["VIPタグを付与する", "フォローシナリオを作成する"],
                ),
            ]
        )
        plan = self.planner.plan(definition)

        assert len(plan.steps) >= 2
        kinds = {s.kind for s in plan.steps}
        assert "tag.assign" in kinds
        assert "scenario.create" in kinds

    def test_承認必須ケースの判定(self) -> None:
        """broadcast.schedule を含む plan が承認必須と判定されることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
            broadcast_steps:
                broadcast.schedule の step リスト。
        """
        definition = _make_definition(
            [
                _make_task("全員配信", steps=["全員に一斉配信する"]),
            ]
        )
        plan = self.planner.plan(definition)

        assert plan.requires_approval is True
        # broadcast.schedule の step は requires_approval=True
        broadcast_steps = [s for s in plan.steps if s.kind == "broadcast.schedule"]
        assert len(broadcast_steps) >= 1
        assert all(s.requires_approval for s in broadcast_steps)

    def test_risk_level判定_lowケース(self) -> None:
        """create/assign のみの plan が risk_level=low と判定されることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
        """
        definition = _make_definition(
            [
                _make_task("タグ付与", steps=["タグを付与する"]),
            ]
        )
        plan = self.planner.plan(definition)

        assert plan.risk_level == "low"

    def test_idempotency_keyが各stepに付与される(self) -> None:
        """各 step に idempotency_key が UUID v4 形式で付与されることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
        """
        definition = _make_definition(
            [
                _make_task(
                    "タグと配信",
                    steps=["タグを付与する", "全員に一斉配信する"],
                ),
            ]
        )
        plan = self.planner.plan(definition)

        for step in plan.steps:
            assert step.idempotency_key is not None
            assert len(step.idempotency_key) > 0

        # 各 step の key が異なること
        keys = [s.idempotency_key for s in plan.steps]
        assert len(keys) == len(set(keys))

    def test_空のtasksで空のstepsが返る(self) -> None:
        """tasks が空の場合、空の steps を持つ plan が返ることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
        """
        definition = _make_definition([])
        plan = self.planner.plan(definition)

        assert len(plan.steps) == 0
        assert plan.risk_level == "low"

    def test_definition_idが保持される(self) -> None:
        """definition_id が plan に正しく保持されることを確認する。

        Variables:
            definition:
                テスト用の BusinessDefinition dict。
            plan:
                生成された ExecutionPlan。
        """
        definition = _make_definition(
            [
                _make_task("タグ付与", steps=["タグを付与する"]),
            ]
        )
        plan = self.planner.plan(definition, definition_id="def_abc123")

        assert plan.source_definition_id == "def_abc123"
