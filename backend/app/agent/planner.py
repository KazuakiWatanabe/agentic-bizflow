"""
抽出結果を実行可能なタスク/ロールへ分解するPlannerAgentを提供する。

入出力: reader_out(dict) -> dict(tasks, roles)。
制約: タスク/ロールは最低1件生成する。

Note:
    - retry_issues がある場合のみ trigger を補完する
"""

from typing import Any, Dict, List


class PlannerAgent:
    """業務をタスク/ロール/トリガーへ分解するAgent。

    主なメソッド: run()
    制約: 曖昧なタスクを通さず、複数業務を1タスクにまとめない。

    Note:
        - retry_issues がある場合のみ trigger を補完する
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
            role_name:
                タスクに割り当てるロール名。
            trigger:
                タスクの実行トリガー（初回は空）。
            conditions:
                ReaderAgent が抽出した条件一覧。
            task:
                生成したタスク定義の辞書。
            role:
                生成したロール定義の辞書。

        Raises:
            None

        Note:
            - 初回は trigger を空にしてValidatorで検出させる
            - retry_issues がある場合は条件から trigger を補完する
        """
        retry_issues = reader_out.get("retry_issues", [])
        is_retry = bool(retry_issues)

        role_name = "Operator"
        trigger = ""
        if is_retry:
            conditions = reader_out.get("conditions") or []
            trigger = conditions[0] if conditions else "when request is received"

        task = {
            "id": "task_1",
            "name": "Process request",
            "role": role_name,
            "trigger": trigger,
            "steps": ["Review input", "Record outcome"],
            "exception_handling": ["Escalate if data is missing"],
            "notifications": ["Notify requester"],
        }

        role = {
            "name": role_name,
            "responsibilities": ["Handle incoming requests"],
        }

        return {"tasks": [task], "roles": [role]}
