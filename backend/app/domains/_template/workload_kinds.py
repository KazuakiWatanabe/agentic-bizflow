"""
テンプレートの workload kind 定数を定義する。

本モジュールは新しいドメイン用の workload kind 定数テンプレートを提供する。
ドメイン固有の kind 文字列を定数として管理する。

入出力: 定数のみを公開する。
制約: ロジックは持たない。

Note:
    - kind は '{domain}.{action}' 形式で定義する
    - 新しいドメインではこのファイルをコピーして定数を追加する
"""

# --- テンプレート: 以下を参考に kind 定数を定義する ---
# MYDOMAIN_ACTION_NAME = "mydomain.action.name"

# 全 kind のリスト（テンプレートでは空）
TEMPLATE_KINDS: list[str] = []
