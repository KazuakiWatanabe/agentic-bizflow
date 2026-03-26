"""
配信ウィンドウ制御のテスト。

本モジュールは app.workers.delivery_window の
enforce_delivery_window と is_within_delivery_window を検証する。

入出力: datetime を渡し、ウィンドウ内に調整された datetime を確認する。
制約: 外部 LLM は使わない。タイムゾーンは JST 基準。

Note:
    - 配信ウィンドウは 9:00-23:00 JST
    - ウィンドウ内の時刻はそのまま返す
    - 23:00-翌9:00 の時刻は翌朝 9:00 に繰り延べる
    - 0:00-9:00 の時刻は当日 9:00 に繰り延べる
"""

from datetime import datetime

from app.workers.delivery_window import (
    JST,
    enforce_delivery_window,
    is_within_delivery_window,
)


def test_within_window_returns_same_time() -> None:
    """12:00 JST（ウィンドウ内）の場合、同じ時刻が返ることを確認する。

    Variables:
        jst_noon: 12:00 JST の datetime
        result: enforce_delivery_window の結果
        result_jst: 結果を JST に変換した datetime

    Note:
        - 9:00-23:00 JST の範囲内なのでそのまま返される
    """
    # 12:00 JST を UTC に変換
    jst_noon = datetime(2026, 3, 26, 12, 0, 0, tzinfo=JST)
    result = enforce_delivery_window(jst_noon)
    # 同じ時刻が返る
    result_jst = result.astimezone(JST)
    assert result_jst.hour == 12
    assert result_jst.minute == 0


def test_late_night_returns_next_day_0900() -> None:
    """23:30 JST（ウィンドウ外）の場合、翌日 9:00 JST が返ることを確認する。

    Variables:
        jst_late: 23:30 JST の datetime
        result: enforce_delivery_window の結果
        result_jst: 結果を JST に変換した datetime

    Note:
        - 23:00 以降は翌日 9:00 JST に繰り延べられる
    """
    jst_late = datetime(2026, 3, 26, 23, 30, 0, tzinfo=JST)
    result = enforce_delivery_window(jst_late)
    result_jst = result.astimezone(JST)
    assert result_jst.hour == 9
    assert result_jst.minute == 0
    assert result_jst.day == 27  # 翌日


def test_early_morning_returns_same_day_0900() -> None:
    """03:00 JST（ウィンドウ外）の場合、当日 9:00 JST が返ることを確認する。

    Variables:
        jst_early: 03:00 JST の datetime
        result: enforce_delivery_window の結果
        result_jst: 結果を JST に変換した datetime

    Note:
        - 0:00-9:00 は当日 9:00 JST に繰り延べられる
    """
    jst_early = datetime(2026, 3, 26, 3, 0, 0, tzinfo=JST)
    result = enforce_delivery_window(jst_early)
    result_jst = result.astimezone(JST)
    assert result_jst.hour == 9
    assert result_jst.minute == 0
    assert result_jst.day == 26  # 同日


def test_is_within_window_true_for_1500_jst() -> None:
    """15:00 JST がウィンドウ内と判定されることを確認する。

    Variables:
        jst_afternoon: 15:00 JST の datetime
        result: is_within_delivery_window の結果

    Note:
        - 15:00 は 9:00-23:00 の範囲内
    """
    jst_afternoon = datetime(2026, 3, 26, 15, 0, 0, tzinfo=JST)
    result = is_within_delivery_window(jst_afternoon)
    assert result is True


def test_is_within_window_false_for_0200_jst() -> None:
    """02:00 JST がウィンドウ外と判定されることを確認する。

    Variables:
        jst_night: 02:00 JST の datetime
        result: is_within_delivery_window の結果

    Note:
        - 02:00 は 9:00-23:00 の範囲外
    """
    jst_night = datetime(2026, 3, 26, 2, 0, 0, tzinfo=JST)
    result = is_within_delivery_window(jst_night)
    assert result is False
