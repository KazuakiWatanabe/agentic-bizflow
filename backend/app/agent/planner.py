"""
抽出結果を実行可能なタスク/ロールへ分解するPlannerAgentを提供する。

入出力: reader_out(dict) -> dict(tasks, roles)。
制約: タスク/ロールは最低1件生成する。

Note:
    - retry_issues がある場合のみ trigger を補完する
    - actions が複数ある場合は原則タスクも複数にする
"""

from typing import Any, Dict, List

from app.services.text_splitter import extract_trigger_phrase


class PlannerAgent:
    """業務をタスク/ロール/トリガーへ分解するAgent。

    主なメソッド: run()
    制約: 曖昧なタスクを通さず、複数業務を1タスクにまとめない。

    Note:
        - retry_issues がある場合のみ trigger を補完する
        - actions が複数ある場合は原則タスクも複数にする
    """

    def run(self, reader_out: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """抽出結果を基にタスク案とロール案を生成する。

        Args:
            reader_out: ReaderAgent の出力辞書

        Returns:
            tasks と roles を含む辞書

        Variables:
            retry_issues:
                Validatorで検出された問題点の一覧（再試行時のみ）。
            is_retry:
                再試行フラグ。retry_issues の有無で判定する。
            actions:
                ReaderAgent が抽出したアクション候補一覧。
            role_name:
                タスクに割り当てるロール名。
            trigger:
                タスクの実行トリガー（初回は空）。
            task:
                生成したタスク定義の辞書。
            tasks:
                生成したタスク定義の一覧。
            role:
                生成したロール定義の辞書。

        Raises:
            None

        Note:
            - 初回は trigger を空にしてValidatorで検出させる
            - retry_issues がある場合は条件/アクションから trigger を補完する
        """
        retry_issues = reader_out.get("retry_issues", [])
        is_retry = bool(retry_issues)
        actions = reader_out.get("actions") or []

        role_name = "Operator"
        tasks: List[Dict[str, Any]] = []

        if actions:
            for index, action in enumerate(actions, start=1):
                trigger = ""
                if is_retry:
                    trigger = self._build_trigger(action, reader_out)
                task = {
                    "id": f"task_{index}",
                    "name": action or "Process request",
                    "role": role_name,
                    "trigger": trigger,
                    "steps": [action] if action else ["Review input"],
                    "exception_handling": ["Escalate if data is missing"],
                    "notifications": ["Notify requester"],
                }
                tasks.append(task)
        else:
            trigger = ""
            if is_retry:
                trigger = self._build_trigger("", reader_out)
            tasks.append(
                {
                    "id": "task_1",
                    "name": "Process request",
                    "role": role_name,
                    "trigger": trigger,
                    "steps": ["Review input", "Record outcome"],
                    "exception_handling": ["Escalate if data is missing"],
                    "notifications": ["Notify requester"],
                }
            )

        role = {
            "name": role_name,
            "responsibilities": ["Handle incoming requests"],
        }

        return {"tasks": tasks, "roles": [role]}

    def _build_trigger(self, action: str, reader_out: Dict[str, Any]) -> str:
        """タスクのトリガーを補完する。

        Args:
            action: アクション候補文字列
            reader_out: ReaderAgent の出力辞書

        Returns:
            トリガー文字列（補完できない場合は既定値）

        Variables:
            extracted:
                action から抽出した条件節フレーズ。
            conditions:
                ReaderAgent が抽出した条件一覧。

        Note:
            - action から条件節が取れない場合は conditions を参照する
            - それでも無い場合は既定値を返す
        """
        extracted = extract_trigger_phrase(action)
        if extracted:
            return extracted
        conditions = reader_out.get("conditions") or []
        if conditions:
            return str(conditions[0])
        return "when request is received"
