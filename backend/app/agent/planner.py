"""
抽出結果を実行可能なタスク/ロールへ分解するPlannerAgentを提供する。

入出力: reader_out(dict) -> dict(tasks, roles)。
制約: タスク/ロールは最低1件生成する。

Note:
    - actions が複数ある場合は原則タスクも複数にする
    - trigger は条件表現を含む action のみに付与する
    - 連絡/通知タスクは recipients を付与する
    - LLMが有効な場合のみ actions/roles の補助推定に利用する
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from app.services.role_inference import (
    CONTACT_KEYWORDS,
    build_role_definitions,
    infer_roles_with_keywords,
)
from app.services.text_splitter import extract_trigger_phrase, filter_business_actions

LLM_PROMPT_VERSION = "planner_roles_v1"  # LLMプロンプトのバージョン識別子


class PlannerAgent:
    """業務をタスク/ロール/トリガーへ分解するAgent。

    主なメソッド: run()
    制約: 曖昧なタスクを通さず、複数業務を1タスクにまとめない。

    Note:
        - actions が複数ある場合は原則タスクも複数にする
        - trigger は条件表現を含む action のみに付与する
        - 連絡/通知タスクは recipients を付与する
        - LLMが有効な場合のみ actions/roles の補助推定に利用する
    """

    def __init__(self) -> None:
        """PlannerAgentを初期化する。

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
            llm_actions:
                LLMが提案したアクション候補一覧。
            llm_role_hints:
                LLMが提案したロール推定一覧。
            llm_usage:
                LLM利用状況のメタ情報。
            role_hint_map:
                action 文字列ごとのロール推定マップ。
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
            - LLMは actions/roles の補助推定にのみ利用する
        """
        retry_issues = reader_out.get("retry_issues", [])
        is_retry = bool(retry_issues)
        actions = reader_out.get("actions") or []
        actions_raw = reader_out.get("actions_raw") or actions
        force_task_split = bool(reader_out.get("force_task_split"))
        avoid_non_business = bool(reader_out.get("avoid_non_business")) and is_retry
        entities_people = reader_out.get("entities_detail", {}).get("people") or []
        input_text = str(reader_out.get("input_text") or "")

        if avoid_non_business and actions_raw:
            actions = filter_business_actions(actions_raw)

        if force_task_split and len(actions) <= 1:
            actions = self._force_split_actions(
                action=actions[0] if actions else "",
                input_text=input_text,
            )

        llm_actions, llm_role_hints, llm_usage = self._maybe_refine_with_llm(
            input_text=input_text,
            actions=actions,
        )
        self._last_llm_usage = llm_usage
        if llm_actions:
            actions = self._merge_unique(actions, llm_actions)
        role_hint_map = {
            hint.get("action"): hint.get("role")
            for hint in llm_role_hints
            if hint.get("action") and hint.get("role")
        }

        tasks: List[Dict[str, Any]] = []
        role_inference: List[Dict[str, Any]] = []
        task_index = 1

        if actions:
            for action in actions:
                inferred_roles, matched_keywords = infer_roles_with_keywords(action)
                role_hint = role_hint_map.get(action)
                if role_hint:
                    inferred_roles = [role_hint]
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
                            "source": "llm" if role_hint else "rules",
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

    def _maybe_refine_with_llm(
        self,
        input_text: str,
        actions: List[str],
    ) -> Tuple[List[str], List[Dict[str, str]], Dict[str, Any]]:
        """LLMで actions/roles を補助推定する。

        Args:
            input_text: 入力となる業務文章
            actions: ルールベースのアクション候補一覧

        Returns:
            (llm_actions, llm_role_hints, llm_usage)

        Variables:
            provider:
                LLMプロバイダ名（既定は vertex）。
            model:
                使用するGeminiモデル名。
            llm_usage:
                LLM利用状況のメタ情報。
            prompt:
                LLMに渡すプロンプト。
            response:
                LLMの生成レスポンス。
            payload:
                JSONとして解釈した生成結果。
            raw_actions:
                LLMが返したアクション候補一覧。
            raw_role_hints:
                LLMが返したロール推定一覧。
            llm_actions:
                検証済みのアクション候補一覧。
            llm_role_hints:
                検証済みのロール推定一覧。

        Note:
            - LLM_ENABLED が true の場合のみ呼び出す
            - プロンプトや生応答をログに保存しない
            - 返却値は input_text に含まれる候補のみ採用する
        """
        provider = os.getenv("LLM_PROVIDER", "vertex").lower()
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        llm_usage: Dict[str, Any] = {
            "enabled": False,
            "used": False,
            "provider": provider,
            "model": model,
            "feature": "planner_roles",
            "prompt_version": LLM_PROMPT_VERSION,
            "error": None,
            "added_actions": 0,
            "role_hints": 0,
        }

        if not self._is_llm_enabled():
            return [], [], llm_usage

        llm_usage["enabled"] = True
        if provider != "vertex":
            llm_usage["error"] = "unsupported_provider"
            return [], [], llm_usage

        cleaned = (input_text or "").strip()
        if not cleaned:
            llm_usage["error"] = "empty_text"
            return [], [], llm_usage

        if not os.getenv("GCP_PROJECT_ID"):
            llm_usage["error"] = "missing_gcp_project"
            return [], [], llm_usage

        try:
            from .llm import llm_generate

            prompt = self._build_llm_prompt(cleaned, actions)
            response = llm_generate(prompt)
            payload = self._extract_json_object(response)
            if not payload:
                llm_usage["error"] = "invalid_response"
                return [], [], llm_usage

            raw_actions = payload.get("actions") or []
            raw_role_hints = payload.get("role_hints") or []

            llm_actions = self._filter_actions_in_text(
                raw_actions,
                input_text=cleaned,
                limit=20,
            )

            llm_role_hints = self._filter_role_hints(
                raw_role_hints,
                input_text=cleaned,
            )

            llm_usage["used"] = True
            llm_usage["added_actions"] = len(llm_actions)
            llm_usage["role_hints"] = len(llm_role_hints)
            return llm_actions, llm_role_hints, llm_usage
        except Exception as exc:
            llm_usage["error"] = type(exc).__name__
            return [], [], llm_usage

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
            - LLM_FEATURES がある場合は planner が含まれる時のみ有効
        """
        raw_value = os.getenv("LLM_ENABLED", "")
        normalized = raw_value.strip().lower()
        if normalized not in {"1", "true", "yes", "on"}:
            return False

        features_raw = os.getenv("LLM_FEATURES", "").strip().lower()
        if not features_raw:
            return True

        features = {item.strip() for item in features_raw.split(",") if item}
        return "planner" in features

    def _build_llm_prompt(self, input_text: str, actions: List[str]) -> str:
        """LLMに渡すプロンプトを生成する。

        Args:
            input_text: 入力となる業務文章
            actions: ルールベースのアクション候補一覧

        Returns:
            LLMに渡すプロンプト文字列

        Variables:
            actions_text:
                アクション候補の連結文字列。

        Note:
            - JSONのみを返すように指示する
            - action と role は input_text に含まれる表現を優先する
        """
        actions_text = ", ".join(actions) if actions else "なし"
        return (
            "あなたは業務文章からタスク分割とロール推定を補助するアシスタントです。\n"
            "以下の文章を読み、タスクに相当するアクションとロール候補を返してください。\n"
            "出力は必ず JSON のみとし、余計な説明は付けないでください。\n"
            "抽出語句は input_text に含まれる表現のみ使用してください。\n"
            "role は Applicant / Approver / Accounting / Operator のいずれか。\n"
            '出力形式: {"actions": ["..."], "role_hints": [{"action": "...", "role": "..."}]}\n'
            "input_text:\n"
            f"{input_text}\n"
            "参考 actions:\n"
            f"{actions_text}\n"
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

    def _filter_actions_in_text(
        self,
        actions: Any,
        input_text: str,
        limit: int,
    ) -> List[str]:
        """input_text に含まれるアクションのみを抽出する。

        Args:
            actions: 候補の一覧
            input_text: 判定対象の入力文
            limit: 最大件数

        Returns:
            input_text に含まれるアクション一覧

        Variables:
            results:
                抽出した候補一覧。
            item:
                判定対象の候補。
            candidate:
                正規化した候補文字列。

        Note:
            - 候補は input_text に含まれる場合のみ採用する
            - limit 件を超えた場合は打ち切る
        """
        results: List[str] = []
        if not isinstance(actions, list):
            return results
        for item in actions:
            candidate = str(item or "").strip()
            if not candidate:
                continue
            if candidate not in input_text:
                continue
            if candidate in results:
                continue
            results.append(candidate)
            if len(results) >= limit:
                break
        return results

    def _filter_role_hints(
        self,
        role_hints: Any,
        input_text: str,
    ) -> List[Dict[str, str]]:
        """LLMのロール推定結果を検証して抽出する。

        Args:
            role_hints: LLMが返したロール推定一覧
            input_text: 判定対象の入力文

        Returns:
            検証済みのロール推定一覧

        Variables:
            results:
                検証済みのロール推定一覧。
            hint:
                LLMが返した推定候補。
            action:
                推定対象のアクション文字列。
            role:
                推定ロール名。

        Note:
            - action は input_text に含まれる場合のみ採用する
            - role は定義済みの候補のみ採用する
        """
        results: List[Dict[str, str]] = []
        if not isinstance(role_hints, list):
            return results
        allowed_roles = {"Applicant", "Approver", "Accounting", "Operator"}
        for hint in role_hints:
            if not isinstance(hint, dict):
                continue
            action = str(hint.get("action") or "").strip()
            role = str(hint.get("role") or "").strip()
            if not action or not role:
                continue
            if action not in input_text:
                continue
            if role not in allowed_roles:
                continue
            results.append({"action": action, "role": role})
        return results

    def _merge_unique(self, base: List[str], extra: List[str]) -> List[str]:
        """重複を除去しつつ候補一覧を結合する。

        Args:
            base: 既存の候補一覧
            extra: 追加候補一覧

        Returns:
            結合後の候補一覧

        Variables:
            merged:
                結合後の候補一覧。

        Note:
            - base の順序を維持し、extra を末尾に追加する
        """
        merged: List[str] = []
        for item in base + extra:
            if item and item not in merged:
                merged.append(item)
        return merged

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
                recipients.append({"type": "person", "name": name, "surface": surface})
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
