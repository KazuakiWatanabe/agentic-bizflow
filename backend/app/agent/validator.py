"""
Planner出力を検証し、issues と open_questions を返すValidatorAgentを提供する。

入出力: planner_out(dict) -> {"issues": [...], "open_questions": [...]}。
制約: issues が1つでもあれば失敗扱いとする。

Note:
    - tasks/roles が空の場合は issues に追加する
"""

from typing import Any, Dict, List


class ValidatorAgent:
    """必須項目の欠落や曖昧さを検出するAgent。

    主なメソッド: run()
    制約: issues が1つでもあれば失敗扱い。

    Note:
        - 自動修正や暗黙補完は禁止
    """

    def run(self, planner_out: Dict[str, Any]) -> Dict[str, List[str]]:
        """Planner出力の妥当性を検証する。

        Args:
            planner_out: PlannerAgent の出力辞書

        Returns:
            issues と open_questions を含む辞書

        Variables:
            issues:
                検出した問題点の一覧。
            open_questions:
                未解決事項の一覧。
            tasks:
                Plannerが生成したタスク一覧。
            roles:
                Plannerが生成したロール一覧。
            task_id:
                検証対象タスクの識別子。
            steps:
                タスクの手順一覧。

        Raises:
            None

        Note:
            - tasks/roles が空の場合は issues に追加する
            - trigger や steps が欠落している場合は issues に追加する
        """
        issues: List[str] = []
        open_questions: List[str] = []

        tasks = planner_out.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            issues.append("tasks missing")
            open_questions.append("What tasks are required?")
        else:
            for task in tasks:
                task_id = str(task.get("id") or "unknown_task")
                if not task.get("name"):
                    issues.append(f"missing name in {task_id}")
                if not task.get("role"):
                    issues.append(f"missing role in {task_id}")
                if not task.get("trigger"):
                    issues.append(f"missing trigger in {task_id}")
                    open_questions.append(f"What triggers {task_id}?")
                steps = task.get("steps")
                if not isinstance(steps, list) or not steps:
                    issues.append(f"missing steps in {task_id}")

        roles = planner_out.get("roles")
        if not isinstance(roles, list) or not roles:
            issues.append("roles missing")
            open_questions.append("Who is responsible for each task?")
        else:
            for role in roles:
                if not role.get("name"):
                    issues.append("role name missing")
                    open_questions.append("What are the role names?")

        return {"issues": issues, "open_questions": open_questions}
