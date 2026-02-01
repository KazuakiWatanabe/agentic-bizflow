"""
抽出結果を実行可能なタスク/ロールへ分解するPlannerAgentを提供する。

入出力: reader_out(dict) -> dict(tasks, roles)。
制約: タスク/ロールは最低1件生成する。

Note:
    - actions が複数ある場合は原則タスクも複数にする
    - trigger は条件表現を含む action のみに付与する
    - 連絡/通知タスクは recipients を付与する
"""

from typing import Any, Dict, List

from app.services.role_inference import (
    CONTACT_KEYWORDS,
    build_role_definitions,
    infer_roles_with_keywords,
)
from app.services.text_splitter import extract_trigger_phrase, filter_business_actions


class PlannerAgent:
    """業務をタスク/ロール/トリガーへ分解するAgent。

    主なメソッド: run()
    制約: 曖昧なタスクを通さず、複数業務を1タスクにまとめない。

    Note:
        - actions が複数ある場合は原則タスクも複数にする
        - trigger は条件表現を含む action のみに付与する
        - 連絡/通知タスクは recipients を付与する
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
            actions_raw:
                split_actions 直後のアクション候補一覧。
            force_task_split:
                複合文判定などでタスク分割を強制するフラグ。
            avoid_non_business:
                非業務候補の除外を強制するフラグ。
            entities_people:
                抽出した人名エンティティ一覧。
            input_text:
                分割前の入力文。
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
            role_inference:
                役割推定の結果一覧。
            task_index:
                タスクID生成用の連番。

        Raises:
            None

        Note:
            - 非業務候補の除外フラグがある場合は再フィルタを行う
            - trigger は action から条件節が取れる場合のみ付与する
        """
        retry_issues = reader_out.get("retry_issues", [])
        is_retry = bool(retry_issues)
        actions = reader_out.get("actions") or []
        actions_raw = reader_out.get("actions_raw") or actions
        force_task_split = bool(reader_out.get("force_task_split"))
        avoid_non_business = bool(reader_out.get("avoid_non_business")) and is_retry
        entities_people = (
            reader_out.get("entities_detail", {}).get("people") or []
        )
        input_text = str(reader_out.get("input_text") or "")

        if avoid_non_business and actions_raw:
            actions = filter_business_actions(actions_raw)

        if force_task_split and len(actions) <= 1:
            actions = self._force_split_actions(
                action=actions[0] if actions else "",
                input_text=input_text,
            )

        tasks: List[Dict[str, Any]] = []
        role_inference: List[Dict[str, Any]] = []
        task_index = 1

        if actions:
            for action in actions:
                inferred_roles, matched_keywords = infer_roles_with_keywords(action)
                expanded_actions = self._expand_actions_for_roles(
                    action, inferred_roles, matched_keywords
                )
                for expanded in expanded_actions:
                    task_action = expanded["task_action"]
                    role_name = expanded["role"]
                    trigger = self._build_trigger(task_action)
                    recipients = self._extract_recipients(
                        action, role_name, entities_people
                    )
                    task = {
                        "id": f"task_{task_index}",
                        "name": task_action or "Process request",
                        "role": role_name,
                        "trigger": trigger,
                        "steps": [task_action] if task_action else ["Review input"],
                        "exception_handling": ["Escalate if data is missing"],
                        "notifications": ["Notify requester"],
                        "recipients": recipients,
                    }
                    tasks.append(task)
                    role_inference.append(
                        {
                            "action": task_action,
                            "source_action": action,
                            "inferred_role": role_name,
                            "matched_keywords": matched_keywords.get(role_name, []),
                        }
                    )
                    task_index += 1
        else:
            role_name = "Applicant"
            trigger = self._build_trigger("")
            tasks.append(
                {
                    "id": "task_1",
                    "name": "Process request",
                    "role": role_name,
                    "trigger": trigger,
                    "steps": ["Review input", "Record outcome"],
                    "exception_handling": ["Escalate if data is missing"],
                    "notifications": ["Notify requester"],
                    "recipients": [],
                }
            )

        roles = build_role_definitions([task.get("role") for task in tasks])

        return {"tasks": tasks, "roles": roles, "role_inference": role_inference}

    def _build_trigger(self, action: str) -> str:
        """タスクのトリガーを補完する。

        Args:
            action: アクション候補文字列

        Returns:
            トリガー文字列（条件節が無い場合は空文字）

        Variables:
            extracted:
                action から抽出した条件節フレーズ。

        Note:
            - action に条件節が含まれない場合は空文字を返す
        """
        extracted = extract_trigger_phrase(action)
        if extracted:
            return extracted
        return ""

    def _force_split_actions(self, action: str, input_text: str) -> List[str]:
        """強制分割時の簡易アクション候補を生成する。

        Args:
            action: 現在のアクション候補（1件想定）
            input_text: 元の入力文

        Returns:
            強制分割したアクション候補一覧

        Variables:
            candidates:
                強制分割で生成した候補一覧。
            cleaned_action:
                前後空白を除去したアクション文字列。
            cleaned_text:
                前後空白を除去した入力文。
            trigger_phrase:
                条件節として抽出したフレーズ。
            remainder:
                条件節を除いた残りの文。

        Note:
            - 条件節が見つかれば残りの文を追加して2件化する
            - 分割できない場合は既存のアクションを返す
        """
        cleaned_action = (action or "").strip()
        cleaned_text = (input_text or "").strip()
        candidates: List[str] = []

        if cleaned_action:
            candidates.append(cleaned_action)
        elif cleaned_text:
            candidates.append(cleaned_text)

        trigger_phrase = extract_trigger_phrase(candidates[0]) if candidates else ""
        if trigger_phrase and candidates:
            remainder = candidates[0].replace(trigger_phrase, "", 1).strip()
            if remainder and remainder != candidates[0]:
                candidates.append(remainder)

        return candidates or ["Process request"]

    def _extract_recipients(
        self,
        action: str,
        role_name: str,
        people: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """通知/連絡タスクの recipients を抽出する。

        Args:
            action: アクション候補文字列
            role_name: 推定したロール名
            people: 抽出した人名エンティティ一覧

        Returns:
            recipients の辞書配列

        Variables:
            recipients:
                抽出した通知先一覧。
            has_contact:
                連絡/通知系のキーワードが含まれるかどうか。

        Note:
            - 連絡/通知系タスクかつ Applicant ロールの場合のみ付与する
            - people に含まれる name/surface が action に含まれる場合に追加する
        """
        recipients: List[Dict[str, str]] = []
        has_contact = any(keyword in action for keyword in CONTACT_KEYWORDS)
        if not has_contact or role_name != "Applicant":
            return recipients

        for person in people:
            name = str(person.get("name") or "")
            surface = str(person.get("surface") or "")
            if (surface and surface in action) or (name and name in action):
                recipients.append(
                    {"type": "person", "name": name, "surface": surface}
                )
        return recipients

    def _expand_actions_for_roles(
        self,
        action: str,
        inferred_roles: List[str],
        matched_keywords: Dict[str, List[str]],
    ) -> List[Dict[str, str]]:
        """複数ロールに対応するアクションを展開する。

        Args:
            action: 元のアクション文字列
            inferred_roles: 推定ロールの一覧
            matched_keywords: ロール別の一致キーワード一覧

        Returns:
            展開後のタスク情報一覧（role と task_action を含む）

        Variables:
            expanded:
                展開後のタスク情報一覧。
            role:
                展開対象のロール名。
            keywords:
                一致したキーワード一覧。
            task_action:
                タスクに設定するアクション文字列。

        Note:
            - 複数ロールがある場合は role ごとにタスクを生成する
            - Approver は一致キーワードがあれば「承認する」を優先する
        """
        expanded: List[Dict[str, str]] = []
        roles = inferred_roles or ["Applicant"]
        for role in roles:
            keywords = matched_keywords.get(role, [])
            task_action = action
            if role == "Approver" and keywords:
                task_action = f"{keywords[0]}する"
            expanded.append({"role": role, "task_action": task_action})
        return expanded
