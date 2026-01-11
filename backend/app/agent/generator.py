"""Generator Agent: 検証済み情報のみでスキーマ出力を生成する。"""

from typing import Any, Dict, List

from .schemas import BusinessDefinition, RoleDefinition, TaskDefinition


class GeneratorAgent:
    """検証済み情報のみでBusinessDefinitionを生成する。

    ルール:
        - 出力はスキーマに準拠
        - 余計なフィールドやスキーマ外の文章は禁止
    """

    def run(
        self,
        text: str,
        reader_out: Dict[str, Any],
        planner_out: Dict[str, Any],
        validator_out: Dict[str, Any],
    ) -> BusinessDefinition:
        title = self._build_title(text)
        overview = f'Generated business definition for: {title}'

        roles = self._build_roles(planner_out)
        tasks = self._build_tasks(planner_out, reader_out, roles)
        assumptions = reader_out.get('assumptions') or ['input is complete']
        open_questions = validator_out.get('open_questions') or []

        definition_data = {
            'title': title,
            'overview': overview,
            'tasks': tasks,
            'roles': roles,
            'assumptions': assumptions,
            'open_questions': open_questions,
        }
        return BusinessDefinition.model_validate(definition_data)

    def _build_title(self, text: str) -> str:
        cleaned = (text or '').strip()
        if not cleaned:
            return 'Untitled Process'
        first_line = cleaned.splitlines()[0].strip()
        if len(first_line) > 60:
            return f'{first_line[:57]}...'
        return first_line

    def _build_roles(self, planner_out: Dict[str, Any]) -> List[RoleDefinition]:
        roles_out = planner_out.get('roles') or []
        roles: List[RoleDefinition] = []
        for role in roles_out:
            roles.append(self._coerce_role(role))
        if not roles:
            roles.append(
                RoleDefinition(
                    name='Operator',
                    responsibilities=['Handle incoming requests'],
                )
            )
        return roles

    def _build_tasks(
        self,
        planner_out: Dict[str, Any],
        reader_out: Dict[str, Any],
        roles: List[RoleDefinition],
    ) -> List[TaskDefinition]:
        tasks_out = planner_out.get('tasks') or []
        default_role = roles[0].name if roles else 'Operator'
        conditions = reader_out.get('conditions') or []
        default_trigger = conditions[0] if conditions else 'when request is received'

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
                    id='task_1',
                    name='Process request',
                    role=default_role,
                    trigger=default_trigger,
                    steps=['Review input', 'Record outcome'],
                    exception_handling=['Escalate if data is missing'],
                    notifications=['Notify requester'],
                )
            )
        return tasks

    def _coerce_role(self, role: Dict[str, Any]) -> RoleDefinition:
        responsibilities = role.get('responsibilities') or ['Handle requests']
        return RoleDefinition(
            name=str(role.get('name') or 'Operator'),
            responsibilities=[str(item) for item in responsibilities],
        )

    def _coerce_task(
        self,
        task: Dict[str, Any],
        default_role: str,
        default_trigger: str,
    ) -> TaskDefinition:
        steps = task.get('steps') or ['Review input']
        exception_handling = task.get('exception_handling') or []
        notifications = task.get('notifications') or []

        return TaskDefinition(
            id=str(task.get('id') or 'task_1'),
            name=str(task.get('name') or 'Process request'),
            role=str(task.get('role') or default_role),
            trigger=str(task.get('trigger') or default_trigger),
            steps=[str(item) for item in steps],
            exception_handling=[str(item) for item in exception_handling],
            notifications=[str(item) for item in notifications],
        )
