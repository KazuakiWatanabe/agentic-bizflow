"""
日本語文から簡易エンティティ（人名など）を抽出する。

入出力: text(str) -> dict(people/orgs/amounts/dates) を返す。
制約: ルールベースで抽出し、精度は過度に追求しない。

Note:
    - 人名は「◯◯さん」のみを対象とする
    - 重複は順序を保って除去する
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

PERSON_PATTERN = re.compile(r"([一-龠々〆ヵヶぁ-んァ-ン]{1,10})さん")


def extract_entities_ja(text: str) -> Dict[str, Any]:
    """日本語文から簡易エンティティを抽出する。

    Args:
        text: 入力となる業務文章

    Returns:
        エンティティ情報の辞書

    Variables:
        cleaned:
            入力文の前後空白を除去した文字列。
        people:
            抽出した人名エンティティの一覧。
        seen_names:
            重複判定に使う人名の集合。
        match:
            正規表現の一致結果。
        name:
            抽出した人名。
        surface:
            原文の表記（〜さん）。

    Note:
        - 人名以外のエンティティは空配列で返す
        - text が空の場合は空配列を返す
    """
    cleaned = (text or "").strip()
    people: List[Dict[str, str]] = []
    seen_names = set()

    if cleaned:
        for match in PERSON_PATTERN.finditer(cleaned):
            name = match.group(1)
            surface = match.group(0)
            if name in seen_names:
                continue
            seen_names.add(name)
            people.append({"name": name, "surface": surface, "type": "person"})

    return {
        "people": people,
        "orgs": [],
        "amounts": [],
        "dates": [],
    }
