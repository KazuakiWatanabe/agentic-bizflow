"""
Planner出力を検証し、issues と open_questions を返すValidatorAgentを提供する。

入出力: planner_out(dict) -> {"issues": [...], "open_questions": [...]}。
制約: issues が1つでもあれば失敗扱いとする。

Note:
    - tasks/roles が空の場合は issues に追加する
"""

from typing import Any, Dict, List, Optional

COMPOUND_KEYWORDS = [
    "たら",
    "なら",
    "場合",
    "後",
    "次第",
    "そして",
    "また",
    "および",
    "及び",
]  # 複合文判定で参照するキーワード一覧


def is_compound_text(input_text: str, actions: Optional[List[str]] = None) -> bool:
    """入力文が複合文の可能性があるかを判定する。

    Args:
        input_text: 判定対象の入力文
        actions: split_actions などで抽出したアクション候補一覧

    Returns:
        複合文の可能性が高い場合は True

    Variables:
        cleaned:
            前後空白を除去した入力文。
        actions_count:
            アクション候補の件数。

    Note:
        - actions が2件以上なら最優先で複合文とみなす
        - それ以外は句読点/キーワードの存在で判定する
    """
    actions_count = len(actions or [])
    if actions_count >= 2:
        return True

    cleaned = (input_text or "").strip()
    if not cleaned:
        return False
    if "、" in cleaned or "。" in cleaned:
        return True
    return any(keyword in cleaned for keyword in COMPOUND_KEYWORDS)


class ValidatorAgent:
    """必須項目の欠落や曖昧さを検出するAgent。

    主なメソッド: run()
    制約: issues が1つでもあれば失敗扱い。

    Note:
        - 自動修正や暗黙補完は禁止
    """

    def run(
        self,
        planner_out: Dict[str, Any],
        input_text: str = "",
        actions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Planner出力の妥当性を検証する。

        Args:
            planner_out: PlannerAgent の出力辞書
            input_text: 入力となる業務文章
            actions: 事前分割したアクション候補一覧

        Returns:
            issues と open_questions を含む辞書

        Variables:
            issues:
                検出した問題点の一覧。
            issue_details:
                issues の詳細情報一覧。
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
            compound_detected:
                複合文の可能性があるかどうか。

        Raises:
            None

        Note:
            - tasks/roles が空の場合は issues に追加する
            - trigger や steps が欠落している場合は issues に追加する
            - 複合文の可能性があるのに tasks が1件の場合は issue を追加する
        """
        issues: List[str] = []
        issue_details: List[Dict[str, Any]] = []
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

        compound_detected = is_compound_text(input_text, actions)
        if compound_detected and isinstance(tasks, list) and len(tasks) == 1:
            issues.append("compound_text_single_task")
            issue_details.append(
                {
                    "code": "compound_text_single_task",
                    "message": "入力文が複合文の可能性がありますが tasks が1件です。タスク分割を再検討してください。",
                    "severity": "error",
                    "data": {
                        "actions_count": len(actions or []),
                        "text": input_text,
                    },
                }
            )

        return {
            "issues": issues,
            "issue_details": issue_details,
            "open_questions": open_questions,
            "compound_detected": compound_detected,
        }
