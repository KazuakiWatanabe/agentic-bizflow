"""
テンプレートドメインモジュール。

本モジュールは新しいドメインを追加する際のテンプレートを提供する。
register() 関数のスタブを定義し、workload kind の登録方法を示す。

入出力: register() で workload kind を登録する（テンプレートでは何も登録しない）。
制約: Agent 層には依存しない。

Note:
    - 新しいドメインを作成する際は、このディレクトリをコピーして開始する
    - _template は register_all_domains() による自動検出の対象外
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(
    connector_registry: Any = None,
    workload_registry: Any = None,
    db: Any = None,
) -> None:
    """テンプレートドメインを登録する（スタブ）。

    新しいドメインを追加する際は、この関数を起点にして
    workload_registry.register() で kind を登録する。

    Args:
        connector_registry: Connector Registry（dict）
        workload_registry: Workload Kind Registry
        db: DB セッション

    Note:
        - テンプレートのため実際には何も登録しない
        - 以下のコメントを参考に kind を登録すること
    """
    if workload_registry is None:
        return

    # --- kind 登録の例 ---
    # from app.schemas.workload_kind import ApprovalRule
    #
    # workload_registry.register(
    #     kind="mydomain.action.name",
    #     domain="mydomain",
    #     connector="mydomain",
    #     requires_approval=ApprovalRule.NONE,
    #     description="アクションの説明",
    #     keywords=["キーワード1", "キーワード2"],
    # )

    logger.info("テンプレートドメイン: 登録スタブ（何も登録しない）")
