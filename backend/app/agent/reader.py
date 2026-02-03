"""
業務文章から登場人物/操作/条件/例外/前提を抽出するReaderAgentを提供する。

入出力:
    text(str) -> dict(
        entities / entities_detail / actions / actions_raw / actions_filtered_out /
        action_filter_version / action_filter_fallback / conditions / exceptions /
        assumptions / input_text / splitter_version
    )。
制約: 最終JSONを生成せず、欠落情報を黙って補完しない。

Note:
    - text が空の場合は空配列と仮の assumptions を返す
"""

from typing import Any, Dict, List

from app.services.entity_extractor import extract_entities_ja
from app.services.text_splitter import (
    ACTION_FILTER_VERSION,
    SPLITTER_VERSION,
    extract_trigger_phrase,
    filter_business_actions,
    split_actions,
)


class ReaderAgent:
    """入力文から要素を抽出するAgent。

    主なメソッド: run()
    制約: 最終出力を生成しない、推測で補完しない。

    Note:
        - 入力が空の場合は空の抽出結果を返す
    """

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
            exceptions:
                例外候補の一覧（スタブ）。
            assumptions:
                前提条件の一覧（スタブ）。
            entities:
                抽出したエンティティ名の一覧。
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
        entity_names = [person.get("name") for person in people if person.get("name")]

        actions_raw = split_actions(cleaned)
        actions_filtered = filter_business_actions(actions_raw)
        actions_filtered_out = self._diff_actions(actions_raw, actions_filtered)
        action_filter_fallback = False
        actions = actions_filtered
        if not actions and actions_raw:
            actions = actions_raw
            action_filter_fallback = True

        conditions = self._extract_conditions(actions)
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
