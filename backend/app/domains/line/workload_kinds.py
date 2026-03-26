"""
LINE ドメインの workload kind 定数を定義する。

本モジュールは LINE 固有の workload kind 文字列を定数として提供する。

入出力: 定数のみを公開する。
制約: ロジックは持たない。
"""

# LINE workload kind 一覧
LINE_TAG_ASSIGN = "line.tag.assign"
LINE_BROADCAST_SCHEDULE = "line.broadcast.schedule"
LINE_SCENARIO_CREATE = "line.scenario.create"
LINE_SCENARIO_START = "line.scenario.start"
LINE_REMINDER_CREATE = "line.reminder.create"

# 全 LINE kind
LINE_KINDS = [
    LINE_TAG_ASSIGN,
    LINE_BROADCAST_SCHEDULE,
    LINE_SCENARIO_CREATE,
    LINE_SCENARIO_START,
    LINE_REMINDER_CREATE,
]
