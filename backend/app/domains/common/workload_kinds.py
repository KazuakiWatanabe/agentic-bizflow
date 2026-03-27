"""
共通ドメインの workload kind 定数を定義する。

本モジュールはチャネルに依存しない共通 workload kind 文字列を定数として提供する。
共通 kind は kind_resolver によって各ドメイン固有の kind に解決される。

入出力: 定数のみを公開する。
制約: ロジックは持たない。

Note:
    - 共通 kind は 'audience.label.assign' のようにドメインプレフィクスを持たない
    - 解決先はドメインごとに _resolutions マッピングで管理される
"""

# 共通 workload kind 一覧
AUDIENCE_LABEL_ASSIGN = "audience.label.assign"
CAMPAIGN_SCHEDULE = "campaign.schedule"
JOURNEY_CREATE = "journey.create"
JOURNEY_ENROLL = "journey.enroll"
FOLLOWUP_CREATE = "followup.create"

# 全共通 kind
COMMON_KINDS = [
    AUDIENCE_LABEL_ASSIGN,
    CAMPAIGN_SCHEDULE,
    JOURNEY_CREATE,
    JOURNEY_ENROLL,
    FOLLOWUP_CREATE,
]
