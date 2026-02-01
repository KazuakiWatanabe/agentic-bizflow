"""
Planner出力を検証し、issues と open_questions を返すValidatorAgentを提供する。

入出力: planner_out(dict) -> {"issues": [...], "open_questions": [...]}。
制約: issues が1つでもあれば失敗扱いとする。

Note:
    - tasks/roles が空の場合は issues に追加する
"""

from typing import Any, Dict, List, Optional

from app.services.role_inference import CONTACT_KEYWORDS
from app.services.text_splitter import BUSINESS_KEYWORDS, NON_BUSINESS_KEYWORDS

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
TRIGGER_MARKERS = ["たら", "なら", "場合", "後", "次第"]  # 条件節を示すキーワード一覧


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


def is_non_business_task(task: Dict[str, Any]) -> bool:
    """タスクが非業務（挨拶/雑談）の可能性があるかを判定する。

    Args:
        task: Plannerで生成したタスク辞書

    Returns:
        非業務タスクの可能性が高い場合は True

    Variables:
        name:
            タスク名。
        steps:
            タスクの手順一覧。
        combined:
            name と steps を結合した判定用文字列。
        has_business:
            業務キーワードを含むかどうか。
        has_non_business:
            非業務キーワードを含むかどうか。

    Note:
        - 非業務キーワードが含まれていて業務キーワードが無い場合に True
    """
    name = str(task.get("name") or "")
    steps = task.get("steps") or []
    combined = " ".join([name] + [str(step) for step in steps])
    has_business = _contains_any(combined, BUSINESS_KEYWORDS)
    has_non_business = _contains_any(combined, NON_BUSINESS_KEYWORDS)
    return bool(has_non_business and not has_business)


def _task_requires_trigger(task: Dict[str, Any]) -> bool:
    """タスクが条件トリガーを必要とするかを判定する。

    Args:
        task: Plannerで生成したタスク辞書

    Returns:
        条件表現を含む場合は True

    Variables:
        name:
            タスク名。
        steps:
            タスクの手順一覧。
        combined:
            name と steps を結合した判定用文字列。

    Note:
        - 条件キーワードの部分一致で判定する
    """
    name = str(task.get("name") or "")
    steps = task.get("steps") or []
    combined = " ".join([name] + [str(step) for step in steps])
    return _contains_any(combined, TRIGGER_MARKERS)


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
        actions_filtered_out: Optional[List[str]] = None,
        entities: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Planner出力の妥当性を検証する。

        Args:
            planner_out: PlannerAgent の出力辞書
            input_text: 入力となる業務文章
            actions: 事前分割したアクション候補一覧
            actions_filtered_out: フィルタで除外された候補一覧
            entities: 抽出したエンティティ情報

        Returns:
            issues と open_questions を含む辞書

        Variables:
            issues:
                検出した問題点の一覧。
            issue_details:
                issues の詳細情報一覧。
            non_business_tasks:
                非業務の可能性があるタスク識別子一覧。
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
            filtered_out_count:
                フィルタで除外された候補の件数。
            people:
                抽出した人名エンティティ一覧。
            role_names:
                タスクのロール名一覧。
            trigger_values:
                各タスクのトリガー値一覧。
            non_empty_triggers:
                空文字を除いたトリガー値一覧。
            unique_triggers:
                重複除外したトリガー値一覧。

        Raises:
            None

        Note:
            - tasks/roles が空の場合は issues に追加する
            - 条件表現があるのに trigger が空の場合は issues に追加する
            - 複合文の可能性があるのに tasks が1件の場合は issue を追加する
            - 非業務タスクが混入している場合は issue を追加する
            - 複数タスクで role が単一の場合は warning を追加する
            - 通知/連絡タスクに recipients が無い場合は warning を追加する
        """
        issues: List[str] = []
        issue_details: List[Dict[str, Any]] = []
        open_questions: List[str] = []
        non_business_tasks: List[str] = []
        people = (entities or {}).get("people") or []
        role_names: List[str] = []

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
                else:
                    role_names.append(str(task.get("role")))
                if _task_requires_trigger(task) and not task.get("trigger"):
                    issues.append(f"missing trigger in {task_id}")
                    open_questions.append(f"What triggers {task_id}?")
                steps = task.get("steps")
                if not isinstance(steps, list) or not steps:
                    issues.append(f"missing steps in {task_id}")
                if is_non_business_task(task):
                    non_business_tasks.append(task_id)
                if people and _is_contact_task(task) and not task.get("recipients"):
                    issues.append("notification_without_recipient")
                    issue_details.append(
                        {
                            "code": "notification_without_recipient",
                            "message": "通知/連絡タスクに通知先が設定されていません。文中の人名 entity を recipients に設定してください。",
                            "severity": "warning",
                            "data": {"task_id": task_id},
                        }
                    )

        roles = planner_out.get("roles")
        if not isinstance(roles, list) or not roles:
            issues.append("roles missing")
            open_questions.append("Who is responsible for each task?")
        else:
            for role in roles:
                if not role.get("name"):
                    issues.append("role name missing")
                    open_questions.append("What are the role names?")

        if non_business_tasks:
            issues.append("non_business_task_detected")
            issue_details.append(
                {
                    "code": "non_business_task_detected",
                    "message": "業務動詞を含まない可能性のある task が含まれています。挨拶/雑談は tasks に含めず除外してください。",
                    "severity": "warning",
                    "data": {
                        "tasks": non_business_tasks,
                        "hints": "remove greetings/small talk",
                    },
                }
            )

        unique_roles = set(role_names)
        if len(role_names) >= 2 and len(unique_roles) == 1:
            issues.append("role_not_inferred")
            issue_details.append(
                {
                    "code": "role_not_inferred",
                    "message": "複数タスクなのに role が単一です。Applicant/Approver/Accounting への割当を検討してください。",
                    "severity": "warning",
                    "data": {"role": next(iter(unique_roles))},
                }
            )

        filtered_out_count = len(actions_filtered_out or [])
        compound_detected = is_compound_text(input_text, actions)
        if (
            compound_detected
            and isinstance(tasks, list)
            and len(tasks) == 1
            and (len(actions or []) >= 2 or filtered_out_count == 0)
        ):
            issues.append("compound_text_single_task")
            issue_details.append(
                {
                    "code": "compound_text_single_task",
                    "message": "入力文が複合文の可能性がありますが tasks が1件です。タスク分割を再検討してください。",
                    "severity": "error",
                    "data": {
                        "actions_count": len(actions or []),
                        "filtered_out_count": filtered_out_count,
                        "text": input_text,
                    },
                }
            )

        if isinstance(tasks, list) and len(tasks) >= 2:
            trigger_values = [str(task.get("trigger") or "") for task in tasks]
            non_empty_triggers = [value for value in trigger_values if value]
            unique_triggers = set(non_empty_triggers)
            if len(non_empty_triggers) == len(tasks) and len(unique_triggers) == 1:
                issues.append("suspicious_global_trigger")
                issue_details.append(
                    {
                        "code": "suspicious_global_trigger",
                        "message": "trigger が全 task に同一で付与されています。条件に関係する task のみに付与してください。",
                        "severity": "warning",
                        "data": {"trigger": next(iter(unique_triggers))},
                    }
                )

        return {
            "issues": issues,
            "issue_details": issue_details,
            "open_questions": open_questions,
            "compound_detected": compound_detected,
        }


def _contains_any(text: str, keywords: List[str]) -> bool:
    """文字列にキーワードの部分一致があるかを判定する。

    Args:
        text: 判定対象の文字列
        keywords: キーワード一覧

    Returns:
        1件でも含まれる場合は True

    Variables:
        keyword:
            判定対象のキーワード。

    Note:
        - 大小文字の正規化は行わない
    """
    for keyword in keywords:
        if keyword and keyword in text:
            return True
    return False


def _is_contact_task(task: Dict[str, Any]) -> bool:
    """通知/連絡タスクかどうかを判定する。

    Args:
        task: Plannerで生成したタスク辞書

    Returns:
        連絡/通知系のタスクであれば True

    Variables:
        name:
            タスク名。
        steps:
            タスクの手順一覧。
        combined:
            name と steps を結合した判定用文字列。

    Note:
        - CONTACT_KEYWORDS の部分一致で判定する
    """
    name = str(task.get("name") or "")
    steps = task.get("steps") or []
    combined = " ".join([name] + [str(step) for step in steps])
    return _contains_any(combined, CONTACT_KEYWORDS)
