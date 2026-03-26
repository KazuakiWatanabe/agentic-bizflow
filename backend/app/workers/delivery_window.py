"""
配信ウィンドウ制御を提供する。

本モジュールは 9:00-23:00 JST の配信ウィンドウを管理する。
時間外の配信は翌朝 9:00 に繰り延べる。

入出力: datetime を受け取り、ウィンドウ内の datetime を返す。
制約: タイムゾーンは Asia/Tokyo を基準とする。

Note:
    - 9:00-23:00 JST 内の時刻はそのまま返す
    - 23:00-翌 9:00 の時刻は翌朝 9:00 に繰り延べる
    - 0:00-9:00 の時刻は当日 9:00 に繰り延べる
"""

from datetime import datetime, timedelta, timezone

# JST タイムゾーン（UTC+9）
JST = timezone(timedelta(hours=9))

# 配信ウィンドウの開始・終了時刻（時）
WINDOW_START_HOUR = 9
WINDOW_END_HOUR = 23


def is_within_delivery_window(now: datetime) -> bool:
    """現在時刻が配信ウィンドウ（9:00-23:00 JST）内かを判定する。

    Args:
        now: 判定対象の datetime（タイムゾーン付き推奨）

    Returns:
        ウィンドウ内なら True

    Note:
        - タイムゾーンなしの場合は UTC として扱う
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    jst_time = now.astimezone(JST)
    return WINDOW_START_HOUR <= jst_time.hour < WINDOW_END_HOUR


def enforce_delivery_window(target_time: datetime) -> datetime:
    """配信ウィンドウ（9:00-23:00 JST）を適用する。

    ウィンドウ内の時刻はそのまま返し、
    ウィンドウ外の時刻は次の 9:00 JST に繰り延べる。

    Args:
        target_time: 対象の datetime（タイムゾーン付き推奨）

    Returns:
        ウィンドウ内に調整された datetime

    Variables:
        jst_time: JST に変換した対象時刻

    Note:
        - 0:00-9:00 → 当日 9:00 JST
        - 23:00-24:00 → 翌日 9:00 JST
    """
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)
    jst_time = target_time.astimezone(JST)

    if WINDOW_START_HOUR <= jst_time.hour < WINDOW_END_HOUR:
        return target_time

    # 9:00 より前 → 当日 9:00
    if jst_time.hour < WINDOW_START_HOUR:
        adjusted = jst_time.replace(
            hour=WINDOW_START_HOUR, minute=0, second=0, microsecond=0
        )
        return adjusted.astimezone(timezone.utc)

    # 23:00 以降 → 翌日 9:00
    next_day = jst_time + timedelta(days=1)
    adjusted = next_day.replace(
        hour=WINDOW_START_HOUR, minute=0, second=0, microsecond=0
    )
    return adjusted.astimezone(timezone.utc)
