"""Planner Agent: 実行可能なタスクとロールへ分解する。"""

from typing import Any, Dict, List


class PlannerAgent:
    """業務をタスク/ロール/トリガーへ分解する。

    制約:
        - 曖昧なタスクのまま通過させない
        - 複数業務を1タスクにまとめない
    """

    def run(self, reader_out: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        retry_issues = reader_out.get('retry_issues', [])
        is_retry = bool(retry_issues)

        role_name = 'Operator'
        trigger = ''
        if is_retry:
            conditions = reader_out.get('conditions') or []
            trigger = conditions[0] if conditions else 'when request is received'

        task = {
            'id': 'task_1',
            'name': 'Process request',
            'role': role_name,
            'trigger': trigger,
            'steps': ['Review input', 'Record outcome'],
            'exception_handling': ['Escalate if data is missing'],
            'notifications': ['Notify requester'],
        }

        role = {
            'name': role_name,
            'responsibilities': ['Handle incoming requests'],
        }

        return {'tasks': [task], 'roles': [role]}
