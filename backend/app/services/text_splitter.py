"""
日本語の業務文章からアクション候補を分割抽出するプリプロセッサを提供する。

入出力: text(str) -> List[str] の候補配列を返す。
制約: ルールベースで安定抽出を優先し、条件節は削除しない。

Note:
    - splitter_version は "ja_v1" とする
    - 正規表現は最小限に留める
"""

from __future__ import annotations

import re
from typing import List

SPLITTER_VERSION = "ja_v1"  # 分割ルールのバージョン識別子
CONDITION_MARKERS = ["たら", "なら", "場合", "後", "次第"]  # 条件節を示す語尾候補


def split_actions(text: str) -> List[str]:
    """業務文章からアクション候補を抽出する。

    Args:
        text: 入力となる業務文章

    Returns:
        アクション候補の配列（重複除去・空除去・トリム済み）

    Variables:
        cleaned:
            前後空白と全角空白を正規化した文字列。
        fragments:
            区切り語で分割した断片の一覧。
        separators:
            分割に使用する区切り語の一覧。
        candidates:
            正規化後の候補一覧。
        normalized:
            断片の空白を整理した文字列。
        compact:
            空白を除去して長さ判定に使う文字列。

    Note:
        - text が空の場合は空配列を返す
        - 1〜2文字程度の断片は除外する
        - 「〜し」で終わる断片は「〜する」に軽く正規化する
        - 重複候補は順序を保って除去する
    """
    cleaned = (text or "").replace("\u3000", " ").strip()
    if not cleaned:
        return []
    cleaned = re.sub(r"\s+", " ", cleaned)

    separators = ["。", "、", "そして", "または", "および", "及び"]
    fragments: List[str] = [cleaned]
    for sep in separators:
        next_fragments: List[str] = []
        for fragment in fragments:
            if sep in fragment:
                next_fragments.extend(fragment.split(sep))
            else:
                next_fragments.append(fragment)
        fragments = next_fragments

    candidates: List[str] = []
    for fragment in fragments:
        normalized = re.sub(r"\s+", " ", fragment).strip()
        if not normalized:
            continue
        compact = normalized.replace(" ", "")
        if len(compact) <= 2:
            continue
        if normalized.endswith("し") and len(normalized) > 2:
            normalized = f"{normalized[:-1]}する"
        candidates.append(normalized)

    return _dedupe_keep_order(candidates)


def extract_trigger_phrase(action: str) -> str:
    """アクション文から条件節を抽出する。

    Args:
        action: アクション候補の文字列

    Returns:
        条件節が見つかればその文字列、無ければ空文字

    Variables:
        cleaned:
            前後空白を除去した文字列。
        marker_positions:
            条件節キーワードと出現位置の一覧。
        marker:
            先頭側にある条件節キーワード。
        start_index:
            条件節の開始位置（常に0想定）。
        end_index:
            条件節の終了位置（キーワード終端）。

    Note:
        - 条件節が無い場合は空文字を返す
        - 「後」「次第」は直後の「に」を含めて返す
    """
    cleaned = (action or "").strip()
    if not cleaned:
        return ""
    marker_positions = [
        (marker, cleaned.find(marker)) for marker in CONDITION_MARKERS
    ]
    marker_positions = [(marker, pos) for marker, pos in marker_positions if pos != -1]
    if not marker_positions:
        return ""

    marker, pos = min(marker_positions, key=lambda item: item[1])
    start_index = 0
    end_index = pos + len(marker)
    if marker in {"後", "次第"} and end_index < len(cleaned):
        if cleaned[end_index] == "に":
            end_index += 1
    return cleaned[start_index:end_index]


def _dedupe_keep_order(items: List[str]) -> List[str]:
    """重複を除去しつつ順序を保持した配列を返す。

    Args:
        items: 重複を含む候補一覧

    Returns:
        重複を取り除いた配列

    Variables:
        seen:
            既に出現した候補を保持する集合。
        deduped:
            重複除去後の候補一覧。

    Note:
        - 空文字は入力側で除去済みとする
    """
    seen = set()
    deduped: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
