"""Validator Agent: 計画を検証し、issues/open_questionsを返す。"""

from typing import Any, Dict, List


class ValidatorAgent:
    """必須項目を検出し、失敗判定を行う。

    ルール:
        - issuesが1つでもあれば必ず失敗
        - 自動修正・暗黙補完は禁止
    """

    def run(self, planner_out: Dict[str, Any]) -> Dict[str, List[str]]:
        issues: List[str] = []
        open_questions: List[str] = []

        tasks = planner_out.get('tasks')
        if not isinstance(tasks, list) or not tasks:
            issues.append('tasks missing')
            open_questions.append('What tasks are required?')
        else:
            for task in tasks:
                task_id = str(task.get('id') or 'unknown_task')
                if not task.get('name'):
                    issues.append(f'missing name in {task_id}')
                if not task.get('role'):
                    issues.append(f'missing role in {task_id}')
                if not task.get('trigger'):
                    issues.append(f'missing trigger in {task_id}')
                    open_questions.append(f'What triggers {task_id}?')
                steps = task.get('steps')
                if not isinstance(steps, list) or not steps:
                    issues.append(f'missing steps in {task_id}')

        roles = planner_out.get('roles')
        if not isinstance(roles, list) or not roles:
            issues.append('roles missing')
            open_questions.append('Who is responsible for each task?')
        else:
            for role in roles:
                if not role.get('name'):
                    issues.append('role name missing')
                    open_questions.append('What are the role names?')

        return {'issues': issues, 'open_questions': open_questions}
