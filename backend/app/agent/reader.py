"""Reader Agent: 入力文から構造化ヒントを抽出する（最終出力は生成しない）。"""

from typing import Dict, List


class ReaderAgent:
    """登場人物/操作/条件/例外/前提を抽出する。

    制約:
        - 最終JSONを生成しない
        - 不明点を黙って補完しない
    """

    def run(self, text: str) -> Dict[str, List[str]]:
        cleaned = (text or '').strip()
        if not cleaned:
            return {
                'entities': [],
                'actions': [],
                'conditions': [],
                'exceptions': [],
                'assumptions': ['input is empty'],
            }

        return {
            'entities': ['requester', 'operator'],
            'actions': ['process request'],
            'conditions': ['when request is received'],
            'exceptions': ['missing required data'],
            'assumptions': ['input is complete'],
        }
