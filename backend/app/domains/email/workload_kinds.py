"""
Email ドメインの workload kind 定数を定義する。

本モジュールは Email 固有の workload kind 文字列を定数として提供する。

入出力: 定数のみを公開する。
制約: ロジックは持たない。
"""

# Email workload kind 一覧
EMAIL_BROADCAST_SCHEDULE = "email.broadcast.schedule"
EMAIL_TEMPLATE_CREATE = "email.template.create"

# 全 Email kind
EMAIL_KINDS = [
    EMAIL_BROADCAST_SCHEDULE,
    EMAIL_TEMPLATE_CREATE,
]
