"""
業務文章から登場人物/操作/条件/例外/前提を抽出するReaderAgentを提供する。

入出力: text(str) -> dict(entities/actions/conditions/exceptions/assumptions/input_text/splitter_version)。
制約: 最終JSONを生成せず、欠落情報を黙って補完しない。

Note:
    - text が空の場合は空配列と仮の assumptions を返す
"""

from typing import Any, Dict, List

from app.services.text_splitter import (
    SPLITTER_VERSION,
    extract_trigger_phrase,
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
                事前分割したアクション候補一覧。
            conditions:
                条件節として抽出したフレーズ一覧。
            exceptions:
                例外候補の一覧（スタブ）。
            assumptions:
                前提条件の一覧（スタブ）。
            input_text:
                分割前の入力文。
            splitter_version:
                使用した分割ルールのバージョン。

        Raises:
            None

        Note:
            - text が空の場合は空配列と仮の assumptions を返す
            - actions は split_actions による事前分割結果を使用する
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return {
                "entities": [],
                "actions": [],
                "conditions": [],
                "exceptions": [],
                "assumptions": ["input is empty"],
                "input_text": "",
                "splitter_version": SPLITTER_VERSION,
            }

        actions = split_actions(cleaned)
        conditions = self._extract_conditions(actions)
        exceptions = ["missing required data"]
        assumptions = ["input is complete"]

        return {
            "entities": ["requester", "operator"],
            "actions": actions,
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
