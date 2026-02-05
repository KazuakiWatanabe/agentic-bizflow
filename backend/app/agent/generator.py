"""
検証済み情報からBusinessDefinitionを生成するGeneratorAgentを提供する。

入出力: text/reader_out/planner_out/validator_out -> BusinessDefinition。
制約: スキーマ外フィールドを追加しない。

Note:
    - 入力不足の場合は既定値で補完する
    - LLMが有効な場合のみタイトル/概要の生成に利用する
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .schemas import (
    BusinessDefinition,
    RecipientDefinition,
    RoleDefinition,
    TaskDefinition,
)

LLM_PROMPT_VERSION = "title_overview_v1"  # LLMプロンプトのバージョン識別子


class GeneratorAgent:
    """BusinessDefinitionを生成するAgent。

    主なメソッド: run()
    制約: 検証済み情報のみを利用し、スキーマ外は追加しない。

    Note:
        - 欠落情報は既定値で補完する
        - LLMが有効な場合のみタイトル/概要の生成に利用する
    """

    def __init__(self) -> None:
        """GeneratorAgentを初期化する。

        Args:
            None

        Returns:
            None

        Variables:
            self._last_llm_usage:
                直近のLLM利用状況（メタ情報として参照する）。

        Note:
            - 直近のLLM利用状況は run() 実行時に更新する
        """
        self._last_llm_usage: Optional[Dict[str, Any]] = None

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
            default_title:
                既定のタイトル文字列。
            default_overview:
                既定の概要文。
            llm_title:
                LLMで生成したタイトル（有効時のみ）。
            llm_overview:
                LLMで生成した概要（有効時のみ）。
            llm_usage:
                LLMの利用状況メタ情報。
            title:
                最終的に採用したタイトル文字列。
            overview:
                最終的に採用した概要文。
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
            - LLMはタイトル/概要の補助生成にのみ利用する
        """
        default_title = self._build_title(text)
        default_overview = f"Generated business definition for: {default_title}"

        llm_title, llm_overview, llm_usage = (
            self._maybe_generate_title_overview_with_llm(text)
        )
        self._last_llm_usage = llm_usage

        title = llm_title or default_title
        overview = llm_overview or default_overview

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

    def get_last_llm_usage(self) -> Optional[Dict[str, Any]]:
        """直近のLLM利用状況を返す。

        Args:
            None

        Returns:
            LLM利用状況の辞書（未実行時は None）

        Variables:
            self._last_llm_usage:
                直近のLLM利用状況。

        Note:
            - run() 実行後に参照されることを想定する
        """
        return self._last_llm_usage

    def _maybe_generate_title_overview_with_llm(
        self,
        text: str,
    ) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
        """LLMでタイトル/概要を生成できる場合のみ実行する。

        Args:
            text: 入力となる業務文章

        Returns:
            (llm_title, llm_overview, llm_usage)

        Variables:
            llm_usage:
                LLM利用状況メタ情報。
            provider:
                LLMプロバイダ名（既定は vertex）。
            model:
                使用するGeminiモデル名。
            cleaned:
                前後空白を除去した入力文。
            prompt:
                LLMに渡すプロンプト。
            response:
                LLMの生成レスポンス。
            payload:
                JSONとして解釈した生成結果。
            llm_title:
                生成されたタイトル。
            llm_overview:
                生成された概要。

        Note:
            - LLM_ENABLED が true の場合のみ呼び出す
            - 生成結果が不正な場合は既定値にフォールバックする
            - プロンプトや生応答をログに保存しない
        """
        provider = os.getenv("LLM_PROVIDER", "vertex").lower()
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        llm_usage: Dict[str, Any] = {
            "enabled": False,
            "used": False,
            "provider": provider,
            "model": model,
            "feature": "title_overview",
            "prompt_version": LLM_PROMPT_VERSION,
            "error": None,
        }

        if not self._is_llm_enabled():
            return None, None, llm_usage

        llm_usage["enabled"] = True
        if provider != "vertex":
            llm_usage["error"] = "unsupported_provider"
            return None, None, llm_usage

        cleaned = (text or "").strip()
        if not cleaned:
            llm_usage["error"] = "empty_text"
            return None, None, llm_usage

        if not os.getenv("GCP_PROJECT_ID"):
            llm_usage["error"] = "missing_gcp_project"
            return None, None, llm_usage

        try:
            from .llm import llm_generate

            prompt = self._build_title_overview_prompt(cleaned)
            response = llm_generate(prompt)
            payload = self._extract_json_object(response)
            if not payload:
                llm_usage["error"] = "invalid_response"
                return None, None, llm_usage

            llm_title = self._normalize_llm_text(
                payload.get("title"),
                limit=60,
            )
            llm_overview = self._normalize_llm_text(
                payload.get("overview"),
                limit=120,
            )
            if not llm_title or not llm_overview:
                llm_usage["error"] = "missing_fields"
                return None, None, llm_usage

            llm_usage["used"] = True
            return llm_title, llm_overview, llm_usage
        except Exception as exc:
            llm_usage["error"] = type(exc).__name__
            return None, None, llm_usage

    def _is_llm_enabled(self) -> bool:
        """LLMを有効化するかどうかを判定する。

        Args:
            None

        Returns:
            LLMを有効化する場合は True

        Variables:
            raw_value:
                環境変数 LLM_ENABLED の値。
            normalized:
                真偽判定用に正規化した値。
            features_raw:
                LLM_FEATURES の生文字列。
            features:
                有効化対象の feature 名一覧。

        Note:
            - "1", "true", "yes", "on" を有効とみなす
            - LLM_FEATURES がある場合は generator が含まれる時のみ有効
        """
        raw_value = os.getenv("LLM_ENABLED", "")
        normalized = raw_value.strip().lower()
        if normalized not in {"1", "true", "yes", "on"}:
            return False

        features_raw = os.getenv("LLM_FEATURES", "").strip().lower()
        if not features_raw:
            return True

        features = {item.strip() for item in features_raw.split(",") if item}
        return "generator" in features

    def _build_title_overview_prompt(self, text: str) -> str:
        """タイトル/概要生成用のプロンプトを組み立てる。

        Args:
            text: 入力となる業務文章

        Returns:
            LLMに渡すプロンプト文字列

        Variables:
            cleaned:
                前後空白を除去した入力文。

        Note:
            - JSONのみを返すように指示する
            - タイトルは短く、概要は1文を想定する
        """
        cleaned = (text or "").strip()
        return (
            "あなたは業務文章のタイトルと概要を作成するアシスタントです。\n"
            "次の業務文章を読み、タイトルと概要を短く作成してください。\n"
            "JSONのみで返してください。\n"
            '出力形式: {"title": "...", "overview": "..."}\n'
            "制約:\n"
            "- title は 20文字以内を目安\n"
            "- overview は 60文字以内を目安\n"
            "- 余計な前後文や箇条書きは出力しない\n"
            "業務文章:\n"
            f"{cleaned}\n"
        )

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        """文字列からJSONオブジェクトを抽出して解析する。

        Args:
            text: 生成されたテキスト

        Returns:
            JSONオブジェクト辞書（失敗時は None）

        Variables:
            start:
                JSON開始位置。
            end:
                JSON終了位置。
            candidate:
                JSON候補文字列。
            parsed:
                JSONとしてパースした結果。

        Note:
            - 最初と最後の波括弧で単一JSONを抽出する
        """
        start = text.find("{") if text else -1
        end = text.rfind("}") if text else -1
        if start < 0 or end < 0 or end <= start:
            return None
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def _normalize_llm_text(self, value: Any, limit: int) -> str:
        """LLM出力の文字列を整形・短縮する。

        Args:
            value: LLM出力の値
            limit: 最大文字数

        Returns:
            整形後の文字列（空の場合は空文字）

        Variables:
            cleaned:
                前後空白を除去した文字列。

        Note:
            - limit を超える場合は末尾を省略する
        """
        cleaned = str(value or "").strip()
        if not cleaned:
            return ""
        if len(cleaned) > limit:
            return f"{cleaned[: limit - 3]}..."
        return cleaned

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
