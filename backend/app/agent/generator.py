"""
検証済み情報からBusinessDefinitionを生成するGeneratorAgentを提供する。

入出力: text/reader_out/planner_out/validator_out -> BusinessDefinition。
制約: スキーマ外フィールドを追加しない。

Note:
    - 入力不足の場合は既定値で補完する
"""

from typing import Any, Dict, List

from .schemas import BusinessDefinition, RecipientDefinition, RoleDefinition, TaskDefinition


class GeneratorAgent:
    """BusinessDefinitionを生成するAgent。

    主なメソッド: run()
    制約: 検証済み情報のみを利用し、スキーマ外は追加しない。

    Note:
        - 欠落情報は既定値で補完する
    """

    def run(
        self,
        text: str,
        reader_out: Dict[str, Any],
        planner_out: Dict[str, Any],
        validator_out: Dict[str, Any],
    ) -> BusinessDefinition:
        """検証済み情報からBusinessDefinitionを生成する。

        Args:
            text: 入力となる業務文章
            reader_out: ReaderAgent の出力辞書
            planner_out: PlannerAgent の出力辞書
            validator_out: ValidatorAgent の出力辞書

        Returns:
            BusinessDefinition: スキーマに準拠した業務定義

        Variables:
            title:
                生成したタイトル文字列。
            overview:
                タイトルに基づく概要文。
            roles:
                生成したロール定義の一覧。
            tasks:
                生成したタスク定義の一覧。
            assumptions:
                Readerの前提条件一覧。
            open_questions:
                Validatorの未解決事項一覧。
            definition_data:
                BusinessDefinition 検証用の辞書。

        Raises:
            ValidationError: スキーマ検証に失敗した場合に発生

        Note:
            - roles や tasks が不足している場合は既定値で補完する
            - open_questions は validator_out の内容を反映する
        """
        title = self._build_title(text)
        overview = f"Generated business definition for: {title}"

        roles = self._build_roles(planner_out)
        tasks = self._build_tasks(planner_out, reader_out, roles)
        assumptions = reader_out.get("assumptions") or ["input is complete"]
        open_questions = validator_out.get("open_questions") or []

        definition_data = {
            "title": title,
            "overview": overview,
            "tasks": tasks,
            "roles": roles,
            "assumptions": assumptions,
            "open_questions": open_questions,
        }
        return BusinessDefinition.model_validate(definition_data)

    def _build_title(self, text: str) -> str:
        """タイトル文字列を生成する。

        Args:
            text: 入力となる業務文章

        Returns:
            タイトル文字列

        Variables:
            cleaned:
                入力文の前後空白を除去した文字列。
            first_line:
                入力文の先頭行。

        Raises:
            None

        Note:
            - text が空の場合は "Untitled Process" を返す
            - 1行目が長い場合は末尾を省略する
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return "Untitled Process"
        first_line = cleaned.splitlines()[0].strip()
        if len(first_line) > 60:
            return f"{first_line[:57]}..."
        return first_line

    def _build_roles(self, planner_out: Dict[str, Any]) -> List[RoleDefinition]:
        """ロール一覧を生成する。

        Args:
            planner_out: PlannerAgent の出力辞書

        Returns:
            RoleDefinition のリスト

        Variables:
            roles_out:
                Plannerが生成したロール一覧。
            roles:
                RoleDefinition に変換したロール一覧。

        Raises:
            None

        Note:
            - roles が空の場合は既定のロールを追加する
        """
        roles_out = planner_out.get("roles") or []
        roles: List[RoleDefinition] = []
        for role in roles_out:
            roles.append(self._coerce_role(role))
        if not roles:
            roles.append(
                RoleDefinition(
                    name="Operator",
                    responsibilities=["Handle incoming requests"],
                )
            )
        return roles

    def _build_tasks(
        self,
        planner_out: Dict[str, Any],
        reader_out: Dict[str, Any],
        roles: List[RoleDefinition],
    ) -> List[TaskDefinition]:
        """タスク一覧を生成する。

        Args:
            planner_out: PlannerAgent の出力辞書
            reader_out: ReaderAgent の出力辞書
            roles: 生成済みのロール一覧

        Returns:
            TaskDefinition のリスト

        Variables:
            tasks_out:
                Plannerが生成したタスク一覧。
            default_role:
                タスクに割り当てる既定ロール名。
            conditions:
                Readerが抽出した条件一覧。
            default_trigger:
                既定の実行トリガー。
            tasks:
                TaskDefinition に変換したタスク一覧。

        Raises:
            None

        Note:
            - roles が空の場合は既定のロール名を使用する
            - 条件が無い場合は既定の trigger を使用する
            - tasks が空の場合は既定タスクを追加する
        """
        tasks_out = planner_out.get("tasks") or []
        default_role = roles[0].name if roles else "Operator"
        conditions = reader_out.get("conditions") or []
        default_trigger = conditions[0] if conditions else "when request is received"

        tasks: List[TaskDefinition] = []
        for task in tasks_out:
            tasks.append(
                self._coerce_task(
                    task,
                    default_role=default_role,
                    default_trigger=default_trigger,
                )
            )
        if not tasks:
            tasks.append(
                TaskDefinition(
                    id="task_1",
                    name="Process request",
                    role=default_role,
                    trigger=default_trigger,
                    steps=["Review input", "Record outcome"],
                    exception_handling=["Escalate if data is missing"],
                    notifications=["Notify requester"],
                )
            )
        return tasks

    def _coerce_role(self, role: Dict[str, Any]) -> RoleDefinition:
        """ロール情報をRoleDefinitionに整形する。

        Args:
            role: ロール情報の辞書

        Returns:
            RoleDefinition

        Variables:
            responsibilities:
                ロールの責務一覧（既定値込み）。

        Raises:
            None

        Note:
            - name が空の場合は "Operator" を使用する
            - responsibilities が空の場合は既定値を使用する
        """
        responsibilities = role.get("responsibilities") or ["Handle requests"]
        return RoleDefinition(
            name=str(role.get("name") or "Operator"),
            responsibilities=[str(item) for item in responsibilities],
        )

    def _coerce_task(
        self,
        task: Dict[str, Any],
        default_role: str,
        default_trigger: str,
    ) -> TaskDefinition:
        """タスク情報をTaskDefinitionに整形する。

        Args:
            task: タスク情報の辞書
            default_role: 既定のロール名
            default_trigger: 既定のトリガー

        Returns:
            TaskDefinition

        Variables:
            steps:
                タスクの手順一覧（既定値込み）。
            exception_handling:
                例外時の対応一覧。
            notifications:
                通知内容の一覧。
            trigger_value:
                タスクのトリガー値（空文字は維持する）。
            recipients:
                通知先の一覧。

        Raises:
            None

        Note:
            - 不足項目は default_role/default_trigger で補完する
            - steps が空の場合は既定値を使用する
            - trigger が空文字の場合はそのまま保持する
        """
        steps = task.get("steps") or ["Review input"]
        exception_handling = task.get("exception_handling") or []
        notifications = task.get("notifications") or []

        trigger_value = task.get("trigger")
        if trigger_value is None:
            trigger_value = default_trigger
        recipients = self._coerce_recipients(task.get("recipients") or [])

        return TaskDefinition(
            id=str(task.get("id") or "task_1"),
            name=str(task.get("name") or "Process request"),
            role=str(task.get("role") or default_role),
            trigger=str(trigger_value or ""),
            steps=[str(item) for item in steps],
            exception_handling=[str(item) for item in exception_handling],
            notifications=[str(item) for item in notifications],
            recipients=recipients,
        )

    def _coerce_recipients(
        self,
        recipients: List[Dict[str, Any]],
    ) -> List[RecipientDefinition]:
        """通知先情報をRecipientDefinitionに整形する。

        Args:
            recipients: 通知先情報の辞書一覧

        Returns:
            RecipientDefinition の一覧

        Variables:
            results:
                変換後の通知先一覧。
            item:
                通知先情報の辞書。

        Note:
            - type/name/surface が欠落する場合は空文字で補完する
        """
        results: List[RecipientDefinition] = []
        for item in recipients:
            results.append(
                RecipientDefinition(
                    type=str(item.get("type") or ""),
                    name=str(item.get("name") or ""),
                    surface=str(item.get("surface") or ""),
                )
            )
        return results
