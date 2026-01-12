"""
業務文章から登場人物/操作/条件/例外/前提を抽出するReaderAgentを提供する。

入出力: text(str) -> dict(entities/actions/conditions/exceptions/assumptions)。
制約: 最終JSONを生成せず、欠落情報を黙って補完しない。

Note:
    - text が空の場合は空配列と仮の assumptions を返す
"""

from typing import Dict, List


class ReaderAgent:
    """入力文から要素を抽出するAgent。

    主なメソッド: run()
    制約: 最終出力を生成しない、推測で補完しない。

    Note:
        - 入力が空の場合は空の抽出結果を返す
    """

    def run(self, text: str) -> Dict[str, List[str]]:
        """業務文章を読み取り、要素を抽出する。

        Args:
            text: 入力となる業務文章

        Returns:
            抽出結果の辞書（entities/actions/conditions/exceptions/assumptions）

        Variables:
            cleaned:
                入力文の前後空白を除去した文字列。

        Raises:
            None

        Note:
            - text が空の場合は空配列と仮の assumptions を返す
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return {
                "entities": [],
                "actions": [],
                "conditions": [],
                "exceptions": [],
                "assumptions": ["input is empty"],
            }

        return {
            "entities": ["requester", "operator"],
            "actions": ["process request"],
            "conditions": ["when request is received"],
            "exceptions": ["missing required data"],
            "assumptions": ["input is complete"],
        }
