"""
日本語分割プリプロセッサの挙動を検証する。

入出力: split_actions(text) -> actions を評価する。
制約: ルールベース分割のため厳密な日本語解析は期待しない。

Note:
    - 条件節は削除せず候補として残す
"""

from app.services.text_splitter import split_actions


def test_split_actions_complex_sentence() -> None:
    """複合文が複数候補に分割されることを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        text:
            入力となる業務文章。
        actions:
            分割されたアクション候補一覧。

    Raises:
        AssertionError: 期待する候補が得られない場合に発生
    """
    text = "経費を申請し、承認されたら精算し、通知する"
    actions = split_actions(text)

    assert len(actions) >= 3
    assert "経費を申請する" in actions
    assert "承認されたら精算する" in actions
    assert "通知する" in actions


def test_split_actions_single_action() -> None:
    """単文は1件の候補になることを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        text:
            入力となる業務文章。
        actions:
            分割されたアクション候補一覧。

    Raises:
        AssertionError: 期待する候補が得られない場合に発生
    """
    text = "発注する"
    actions = split_actions(text)

    assert actions == ["発注する"]


def test_split_actions_loose_for_no_separator() -> None:
    """区切りが曖昧な文でも候補が空にならないことを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        text:
            入力となる業務文章。
        actions:
            分割されたアクション候補一覧。

    Raises:
        AssertionError: 候補が空の場合に発生

    Note:
        - 区切り語が無い場合は1件以上であれば許容する
    """
    text = "Aを確認してBを更新する"
    actions = split_actions(text)

    assert len(actions) >= 1


def test_split_actions_with_conditions_and_punctuation() -> None:
    """条件節や句点を含む文が適切に分割されることを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        text:
            入力となる業務文章。
        actions:
            分割されたアクション候補一覧。

    Raises:
        AssertionError: 期待する候補が得られない場合に発生
    """
    text = "申請し、承認後に精算する。完了を通知する"
    actions = split_actions(text)

    assert len(actions) >= 3
    assert "申請する" in actions
    assert "承認後に精算する" in actions
    assert "完了を通知する" in actions
