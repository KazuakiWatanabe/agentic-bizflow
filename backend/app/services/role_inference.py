"""
アクション文から担当ロールを推定するルールを提供する。

入出力: action(str) -> role(str) の推定結果を返す。
制約: ルールベースで推定し、未知の場合は Applicant を返す。

Note:
    - 推定根拠（一致キーワード）を返す補助関数も提供する
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

ROLE_KEYWORDS = {
    "Applicant": ["申請", "申込み", "提出", "起票", "入力", "登録"],
    "Approver": ["承認", "決裁", "レビュー", "差戻し"],
    "Accounting": ["精算", "支払", "請求", "立替", "経費処理", "入金", "仕訳"],
}
CONTACT_KEYWORDS = ["連絡", "通知", "共有", "送付", "伝えて", "知らせて"]
ROLE_PRIORITY = ["Approver", "Accounting", "Applicant"]
ROLE_RESPONSIBILITIES = {
    "Applicant": ["Submit requests", "Communicate results"],
    "Approver": ["Approve or reject requests"],
    "Accounting": ["Process reimbursements and accounting entries"],
}


def infer_role_for_action(action: str) -> str:
    """アクション文から担当ロールを推定する。

    Args:
        action: アクション候補文字列

    Returns:
        推定されたロール名

    Variables:
        roles:
            推定されたロール候補一覧。

    Note:
        - roles が空の場合は Applicant を返す
    """
    roles, _ = infer_roles_with_keywords(action)
    return roles[0] if roles else "Applicant"


def infer_roles_with_keywords(action: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """アクション文からロール候補と一致キーワードを返す。

    Args:
        action: アクション候補文字列

    Returns:
        (roles, matched_keywords) のタプル

    Variables:
        cleaned:
            前後空白を除去した文字列。
        matched:
            ロール別の一致キーワード一覧。
        roles:
            推定ロールの一覧。
        contact_matches:
            連絡/通知系の一致キーワード一覧。
        has_contact:
            連絡/通知系のキーワードが含まれるかどうか。

    Note:
        - 役割キーワードが無い場合は Applicant を返す
        - 連絡/通知のみの場合は Applicant とみなす
    """
    cleaned = (action or "").strip()
    matched: Dict[str, List[str]] = {}
    for role, keywords in ROLE_KEYWORDS.items():
        matched[role] = [kw for kw in keywords if kw in cleaned]

    roles = [role for role in ROLE_PRIORITY if matched.get(role)]
    contact_matches = [kw for kw in CONTACT_KEYWORDS if kw in cleaned]
    has_contact = bool(contact_matches)

    if not roles and has_contact:
        roles = ["Applicant"]
        matched["Applicant"] = list({*matched.get("Applicant", []), *contact_matches})

    if not roles:
        roles = ["Applicant"]

    return roles, matched


def build_role_definitions(roles: List[str]) -> List[Dict[str, Any]]:
    """ロール定義の辞書一覧を生成する。

    Args:
        roles: ロール名の一覧

    Returns:
        RoleDefinition 互換の辞書一覧

    Variables:
        unique_roles:
            重複を除去したロール名一覧。
        definitions:
            ロール定義の辞書一覧。
        role:
            生成対象のロール名。

    Note:
        - 未知のロールは responsibilities を既定値で補完する
    """
    unique_roles = list(dict.fromkeys(roles))
    definitions: List[Dict[str, Any]] = []
    for role in unique_roles:
        responsibilities = ROLE_RESPONSIBILITIES.get(role, ["Handle requests"])
        definitions.append({"name": role, "responsibilities": responsibilities})
    return definitions


def _contains_any(text: str, keywords: List[str]) -> bool:
    """文字列にキーワードが含まれるかを判定する。

    Args:
        text: 判定対象の文字列
        keywords: キーワード一覧

    Returns:
        1件でも含まれる場合は True

    Variables:
        keyword:
            判定対象のキーワード。

    Note:
        - 大小文字の正規化は行わない
    """
    for keyword in keywords:
        if keyword and keyword in text:
            return True
    return False
