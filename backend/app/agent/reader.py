"""
業務文章から登場人物/操作/条件/例外/前提を抽出するReaderAgentを提供する。

入出力:
    text(str) -> dict(
        entities / entities_detail / actions / actions_raw /
        actions_filtered_out / action_filter_version /
        action_filter_fallback / conditions / exceptions /
        assumptions / input_text / splitter_version
    )。
制約: 最終JSONを生成せず、欠落情報を黙って補完しない。

Note:
    - text が空の場合は空配列と仮の assumptions を返す
    - LLMが有効な場合のみ actions/conditions の補助抽出に利用する
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from app.services.entity_extractor import extract_entities_ja
from app.services.text_splitter import (
    ACTION_FILTER_VERSION,
    SPLITTER_VERSION,
    extract_trigger_phrase,
    filter_business_actions,
    split_actions,
)

LLM_PROMPT_VERSION = "reader_actions_v1"  # LLMプロンプトのバージョン識別子


class ReaderAgent:
    """入力文から要素を抽出するAgent。

    主なメソッド: run()
    制約: 最終出力を生成しない、推測で補完しない。

    Note:
        - 入力が空の場合は空の抽出結果を返す
        - LLMが有効な場合のみ actions/conditions の補助抽出に利用する
    """

    def __init__(self) -> None:
        """ReaderAgentを初期化する。

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

    def run(self, text: str) -> Dict[str, Any]:
        """業務文章を読み取り、要素を抽出する。

        Args:
            text: 入力となる業務文章

        Returns:
            抽出結果の辞書（entities/actions/conditions/exceptions/assumptions）

        Variables:
            cleaned:
                入力文の前後空白を除去した文字列。
            actions:
                フィルタ済みのアクション候補一覧。
            actions_raw:
                split_actions 直後のアクション候補一覧。
            actions_filtered_out:
                フィルタで除外された候補一覧。
            action_filter_version:
                フィルタのバージョン識別子。
            action_filter_fallback:
                フィルタ結果が空だったため raw に戻したかどうか。
            conditions:
                条件節として抽出したフレーズ一覧。
            llm_actions:
                LLMが提案したアクション候補一覧。
            llm_conditions:
                LLMが提案した条件節候補一覧。
            llm_usage:
                LLM利用状況のメタ情報。
            exceptions:
                例外候補の一覧（スタブ）。
            assumptions:
                前提条件の一覧（スタブ）。
            entities:
                抽出したエンティティ名の一覧。
            entity_names:
                抽出した人名エンティティ名の一覧。
            entities_detail:
                抽出したエンティティ詳細情報。
            input_text:
                分割前の入力文。
            splitter_version:
                使用した分割ルールのバージョン。

        Raises:
            None

        Note:
            - text が空の場合は空配列と仮の assumptions を返す
            - actions は split_actions の結果を業務フィルタで絞り込む
            - フィルタ結果が空の場合は raw_actions にフォールバックする
            - 人名は extract_entities_ja の結果を利用する
            - LLMは actions/conditions の補助抽出にのみ利用する
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return {
                "entities": [],
                "entities_detail": {
                    "people": [],
                    "orgs": [],
                    "amounts": [],
                    "dates": [],
                },
                "actions": [],
                "actions_raw": [],
                "actions_filtered_out": [],
                "action_filter_version": ACTION_FILTER_VERSION,
                "action_filter_fallback": False,
                "conditions": [],
                "exceptions": [],
                "assumptions": ["input is empty"],
                "input_text": "",
                "splitter_version": SPLITTER_VERSION,
            }

        entities_detail = extract_entities_ja(cleaned)
        people = entities_detail.get("people") or []
        entity_names: List[str] = []  # 人名エンティティ名の一覧
        for person in people:
            if person.get("name"):
                entity_names.append(person.get("name"))

        actions_raw = split_actions(cleaned)
        actions_filtered = filter_business_actions(actions_raw)
        actions_filtered_out = self._diff_actions(
            actions_raw,
            actions_filtered,
        )
        action_filter_fallback = False
        actions = actions_filtered
        if not actions and actions_raw:
            actions = actions_raw
            action_filter_fallback = True

        conditions = self._extract_conditions(actions)

        llm_actions, llm_conditions, llm_usage = (
            self._maybe_enhance_actions_with_llm(
                input_text=cleaned,
                actions=actions,
                conditions=conditions,
            )
        )
        self._last_llm_usage = llm_usage

        if llm_actions:
            actions = self._merge_unique(actions, llm_actions)
            if not llm_conditions:
                llm_conditions = self._extract_conditions(llm_actions)
        if llm_conditions:
            conditions = self._merge_unique(conditions, llm_conditions)

        exceptions = ["missing required data"]
        assumptions = ["input is complete"]

        return {
            "entities": entity_names or ["requester", "operator"],
            "entities_detail": entities_detail,
            "actions": actions,
            "actions_raw": actions_raw,
            "actions_filtered_out": actions_filtered_out,
            "action_filter_version": ACTION_FILTER_VERSION,
            "action_filter_fallback": action_filter_fallback,
            "conditions": conditions,
            "exceptions": exceptions,
            "assumptions": assumptions,
            "input_text": cleaned,
            "splitter_version": SPLITTER_VERSION,
        }

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

    def _maybe_enhance_actions_with_llm(
        self,
        input_text: str,
        actions: List[str],
        conditions: List[str],
    ) -> Tuple[List[str], List[str], Dict[str, Any]]:
        """LLMで actions/conditions を補助抽出する。

        Args:
            input_text: 入力となる業務文章
            actions: ルールベースのアクション候補一覧
            conditions: ルールベースの条件節候補一覧

        Returns:
            (llm_actions, llm_conditions, llm_usage)

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
            raw_conditions:
                LLMが返した条件節候補一覧。
            llm_actions:
                検証済みのアクション候補一覧。
            llm_conditions:
                検証済みの条件節候補一覧。

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
            "feature": "reader_actions",
            "prompt_version": LLM_PROMPT_VERSION,
            "error": None,
            "added_actions": 0,
            "added_conditions": 0,
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

            prompt = self._build_llm_prompt(cleaned, actions, conditions)
            response = llm_generate(prompt)
            payload = self._extract_json_object(response)
            if not payload:
                llm_usage["error"] = "invalid_response"
                return [], [], llm_usage

            raw_actions = payload.get("actions") or []
            raw_conditions = payload.get("conditions") or []

            llm_actions = self._filter_phrases_in_text(
                raw_actions,
                input_text=cleaned,
                limit=20,
            )
            filtered_actions = filter_business_actions(llm_actions)
            llm_actions = filtered_actions or llm_actions

            llm_conditions = self._filter_phrases_in_text(
                raw_conditions,
                input_text=cleaned,
                limit=10,
            )

            llm_usage["used"] = True
            llm_usage["added_actions"] = len(llm_actions)
            llm_usage["added_conditions"] = len(llm_conditions)
            return llm_actions, llm_conditions, llm_usage
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
            - LLM_FEATURES がある場合は reader が含まれる時のみ有効
        """
        raw_value = os.getenv("LLM_ENABLED", "")
        normalized = raw_value.strip().lower()
        if normalized not in {"1", "true", "yes", "on"}:
            return False

        features_raw = os.getenv("LLM_FEATURES", "").strip().lower()
        if not features_raw:
            return True

        features = {item.strip() for item in features_raw.split(",") if item}
        return "reader" in features

    def _build_llm_prompt(
        self,
        input_text: str,
        actions: List[str],
        conditions: List[str],
    ) -> str:
        """LLMに渡すプロンプトを生成する。

        Args:
            input_text: 入力となる業務文章
            actions: ルールベースのアクション候補一覧
            conditions: ルールベースの条件節候補一覧

        Returns:
            LLMに渡すプロンプト文字列

        Variables:
            actions_text:
                アクション候補の連結文字列。
            conditions_text:
                条件節候補の連結文字列。

        Note:
            - JSONのみを返すように指示する
            - input_text に含まれる語句のみ抽出するよう明示する
        """
        actions_text = ", ".join(actions) if actions else "なし"
        conditions_text = ", ".join(conditions) if conditions else "なし"
        return (
            "あなたは業務文章からアクションと条件節を抽出するアシスタントです。\n"
            "以下の文章を読み、アクションと条件節を抽出してください。\n"
            "出力は必ず JSON のみとし、余計な説明は付けないでください。\n"
            "抽出語句は input_text に含まれる表現のみ使用してください。\n"
            '出力形式: {"actions": ["..."], "conditions": ["..."]}\n'
            "input_text:\n"
            f"{input_text}\n"
            "参考 actions:\n"
            f"{actions_text}\n"
            "参考 conditions:\n"
            f"{conditions_text}\n"
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

    def _filter_phrases_in_text(
        self,
        phrases: Any,
        input_text: str,
        limit: int,
    ) -> List[str]:
        """input_text に含まれる候補のみを抽出する。

        Args:
            phrases: 候補の一覧
            input_text: 判定対象の入力文
            limit: 最大件数

        Returns:
            input_text に含まれる候補一覧

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
        if not isinstance(phrases, list):
            return results
        for item in phrases:
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

    def _extract_conditions(self, actions: List[str]) -> List[str]:
        """アクション候補から条件節を抽出する。

        Args:
            actions: split_actions で抽出したアクション候補一覧

        Returns:
            条件節として抽出したフレーズ一覧

        Variables:
            conditions:
                条件節フレーズの一覧。
            phrase:
                1件分の条件節フレーズ。

        Note:
            - 条件節が無い場合は空配列を返す
            - 抽出結果は重複を除去して順序を保持する
        """
        conditions: List[str] = []
        for action in actions:
            phrase = extract_trigger_phrase(action)
            if phrase:
                conditions.append(phrase)
        return list(dict.fromkeys(conditions))

    def _diff_actions(self, raw: List[str], filtered: List[str]) -> List[str]:
        """フィルタで除外された候補を抽出する。

        Args:
            raw: split_actions の結果一覧
            filtered: filter_business_actions の結果一覧

        Returns:
            フィルタで除外された候補一覧

        Variables:
            filtered_set:
                フィルタ後の候補集合。
            removed:
                除外された候補一覧。
            candidate:
                判定対象の候補文字列。

        Note:
            - 順序を保持して除外候補を返す
        """
        filtered_set = set(filtered)
        removed: List[str] = []
        for candidate in raw:
            if candidate not in filtered_set:
                removed.append(candidate)
        return removed
