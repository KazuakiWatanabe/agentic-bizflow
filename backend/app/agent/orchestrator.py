"""Orchestrator: Agentを順に実行し、検証失敗時にリトライする。"""

from typing import Any, Dict, List, Optional, Tuple

from .generator import GeneratorAgent
from .planner import PlannerAgent
from .reader import ReaderAgent
from .schemas import BusinessDefinition
from .validator import ValidatorAgent


class Orchestrator:
    """Reader→Planner→Validator→Generatorを統制する。

    ルール:
        - Validator issues時は最大回数までリトライ
        - agent_logsは要約のみを記録
    """

    def __init__(
        self,
        reader: Optional[ReaderAgent] = None,
        planner: Optional[PlannerAgent] = None,
        validator: Optional[ValidatorAgent] = None,
        generator: Optional[GeneratorAgent] = None,
        max_retries: int = 2,
    ) -> None:
        self.reader = reader or ReaderAgent()
        self.planner = planner or PlannerAgent()
        self.validator = validator or ValidatorAgent()
        self.generator = generator or GeneratorAgent()
        self.max_retries = max_retries

    def convert(
        self, text: str
    ) -> Tuple[BusinessDefinition, List[Dict[str, Any]], Dict[str, Any]]:
        agent_logs: List[Dict[str, Any]] = []
        reader_out = self.reader.run(text)
        agent_logs.append(self._log_reader(reader_out))

        retries = 0
        planner_out: Dict[str, Any] = {}
        validator_out: Dict[str, Any] = {}

        while True:
            planner_out = self.planner.run(reader_out)
            agent_logs.append(self._log_planner(planner_out))

            validator_out = self.validator.run(planner_out)
            agent_logs.append(self._log_validator(validator_out))

            issues = validator_out.get('issues') or []
            if issues and retries < self.max_retries:
                retries += 1
                reader_out['retry_issues'] = issues
                continue

            if issues:
                raise ValueError(f'Validation failed after retries: {issues}')

            break

        definition = self.generator.run(
            text=text,
            reader_out=reader_out,
            planner_out=planner_out,
            validator_out=validator_out,
        )
        agent_logs.append(self._log_generator(definition))
        meta = {'retries': retries, 'model': 'stub'}
        return definition, agent_logs, meta

    def _log_reader(self, reader_out: Dict[str, Any]) -> Dict[str, Any]:
        entities = len(reader_out.get('entities') or [])
        actions = len(reader_out.get('actions') or [])
        return {'step': 'reader', 'summary': f'entities={entities} actions={actions}'}

    def _log_planner(self, planner_out: Dict[str, Any]) -> Dict[str, Any]:
        tasks = planner_out.get('tasks') or []
        roles = planner_out.get('roles') or []
        return {
            'step': 'planner',
            'summary': f'tasks={len(tasks)} roles={len(roles)}',
        }

    def _log_validator(self, validator_out: Dict[str, Any]) -> Dict[str, Any]:
        issues = validator_out.get('issues') or []
        if issues:
            summary = 'issues: ' + ', '.join(issues[:2])
        else:
            summary = 'passed'
        return {
            'step': 'validator',
            'summary': summary,
            'issues_count': len(issues),
        }

    def _log_generator(self, definition: BusinessDefinition) -> Dict[str, Any]:
        return {
            'step': 'generator',
            'summary': f'tasks={len(definition.tasks)} roles={len(definition.roles)}',
        }
