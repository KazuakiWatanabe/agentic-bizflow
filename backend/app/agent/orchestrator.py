"""
Reader→Planner→Validator→Generatorの順序で処理するOrchestratorを提供する。

入出力: convert(text) -> (BusinessDefinition, agent_logs, meta)。
制約: issues がある場合のみ最大2回まで再試行する。

Note:
    - Generator は Validation 通過後のみ実行する
    - agent_logs は要約のみを保存する
"""

from typing import Any, Dict, List, Optional, Tuple

from .generator import GeneratorAgent
from .planner import PlannerAgent
from .reader import ReaderAgent
from .schemas import BusinessDefinition
from .validator import ValidatorAgent


class Orchestrator:
    """Agenticパイプラインを制御する。

    主なメソッド: convert()
    制約: issues がある場合のみ最大2回まで再試行する。

    Note:
        - Generator は Validation 通過後のみ実行する
    """

    def __init__(
        self,
        reader: Optional[ReaderAgent] = None,
        planner: Optional[PlannerAgent] = None,
        validator: Optional[ValidatorAgent] = None,
        generator: Optional[GeneratorAgent] = None,
        max_retries: int = 2,
    ) -> None:
        """Orchestratorを初期化する。

        Args:
            reader: ReaderAgent の差し替え
            planner: PlannerAgent の差し替え
            validator: ValidatorAgent の差し替え
            generator: GeneratorAgent の差し替え
            max_retries: 再試行の最大回数

        Returns:
            None

        Raises:
            None

        Note:
            - max_retries は 0 以上を想定する
        """
        self.reader = reader or ReaderAgent()
        self.planner = planner or PlannerAgent()
        self.validator = validator or ValidatorAgent()
        self.generator = generator or GeneratorAgent()
        self.max_retries = max_retries

    def convert(
        self,
        text: str,
    ) -> Tuple[BusinessDefinition, List[Dict[str, Any]], Dict[str, Any]]:
        """業務文章を業務定義に変換する。

        Args:
            text: 入力となる業務文章

        Returns:
            (definition, agent_logs, meta)

        Variables:
            agent_logs:
                各Agentの要約ログ一覧。
            reader_out:
                ReaderAgentの抽出結果。
            actions:
                事前分割されたアクション候補一覧。
            splitter_version:
                分割ルールのバージョン識別子。
            retries:
                Validator失敗時の再試行回数。
            planner_out:
                PlannerAgentの出力辞書。
            validator_out:
                ValidatorAgentの出力辞書。
            issues:
                Validatorが検出した問題点一覧。
            definition:
                生成済みの業務定義。
            meta:
                retries / model / actions / splitter_version を含むメタ情報。

        Raises:
            ValueError: リトライ上限後も issues が残る場合に発生

        Note:
            - issues がある場合のみ再試行する
            - 再試行は最大2回までとする
        """
        agent_logs: List[Dict[str, Any]] = []
        reader_out = self.reader.run(text)
        agent_logs.append(self._log_reader(reader_out))

        actions = reader_out.get("actions") or []
        splitter_version = reader_out.get("splitter_version") or "unknown"
        retries = 0
        planner_out: Dict[str, Any] = {}
        validator_out: Dict[str, Any] = {}

        while True:
            planner_out = self.planner.run(reader_out)
            agent_logs.append(self._log_planner(planner_out))

            validator_out = self.validator.run(planner_out)
            agent_logs.append(self._log_validator(validator_out))

            issues = validator_out.get("issues") or []
            if issues and retries < self.max_retries:
                retries += 1
                reader_out["retry_issues"] = issues
                continue

            if issues:
                raise ValueError(f"Validation failed after retries: {issues}")

            break

        definition = self.generator.run(
            text=text,
            reader_out=reader_out,
            planner_out=planner_out,
            validator_out=validator_out,
        )
        agent_logs.append(self._log_generator(definition))
        meta = {
            "retries": retries,
            "model": "stub",
            "actions": actions,
            "splitter_version": splitter_version,
        }
        return definition, agent_logs, meta

    def _log_reader(self, reader_out: Dict[str, Any]) -> Dict[str, Any]:
        """Readerの要約ログを作成する。

        Args:
            reader_out: ReaderAgent の出力辞書

        Returns:
            要約ログ辞書

        Variables:
            entities:
                Readerで抽出した登場人物の件数。
            actions:
                Readerで抽出した操作の件数。

        Raises:
            None
        """
        entities = len(reader_out.get("entities") or [])
        actions = len(reader_out.get("actions") or [])
        return {"step": "reader", "summary": f"entities={entities} actions={actions}"}

    def _log_planner(self, planner_out: Dict[str, Any]) -> Dict[str, Any]:
        """Plannerの要約ログを作成する。

        Args:
            planner_out: PlannerAgent の出力辞書

        Returns:
            要約ログ辞書

        Variables:
            tasks:
                Plannerで生成したタスク一覧。
            roles:
                Plannerで生成したロール一覧。

        Raises:
            None
        """
        tasks = planner_out.get("tasks") or []
        roles = planner_out.get("roles") or []
        return {
            "step": "planner",
            "summary": f"tasks={len(tasks)} roles={len(roles)}",
        }

    def _log_validator(self, validator_out: Dict[str, Any]) -> Dict[str, Any]:
        """Validatorの要約ログを作成する。

        Args:
            validator_out: ValidatorAgent の出力辞書

        Returns:
            要約ログ辞書

        Variables:
            issues:
                Validatorが検出した問題点一覧。
            summary:
                issues の有無に応じた要約文字列。

        Raises:
            None

        Note:
            - issues がある場合は先頭2件まで概要に含める
        """
        issues = validator_out.get("issues") or []
        if issues:
            summary = "issues: " + ", ".join(issues[:2])
        else:
            summary = "passed"
        return {
            "step": "validator",
            "summary": summary,
            "issues_count": len(issues),
        }

    def _log_generator(self, definition: BusinessDefinition) -> Dict[str, Any]:
        """Generatorの要約ログを作成する。

        Args:
            definition: 生成済みのBusinessDefinition

        Returns:
            要約ログ辞書

        Variables:
            definition:
                生成済みの業務定義。

        Raises:
            None
        """
        return {
            "step": "generator",
            "summary": f"tasks={len(definition.tasks)} roles={len(definition.roles)}",
        }
