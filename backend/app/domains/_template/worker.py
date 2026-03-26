"""
テンプレートワーカー関数。

本モジュールは新しいドメイン用の worker 関数テンプレートを提供する。
定期実行される処理のパターンを示す。

入出力: DB セッションと connector を受け取り、処理結果 dict を返す。
制約: Agent 層には依存しない。

Note:
    - worker 関数は Scheduler から呼び出される
    - 冪等性を担保するため IdempotencyRepository を使用する
"""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.connectors.base_connector import BaseConnector

logger = logging.getLogger(__name__)


def process_template_task(
    db: Session,
    connector: BaseConnector,
) -> Dict[str, Any]:
    """テンプレートのワーカー関数（プレースホルダ）。

    定期実行される処理のテンプレート。
    新しいドメインではこの関数をコピーしてロジックを実装する。

    Args:
        db: SQLAlchemy セッション
        connector: ドメイン用の connector

    Returns:
        処理結果 dict（processed_count, error_count を含む）

    Note:
        - 冪等性を担保するため IdempotencyRepository を使用すること
        - commit は worker 側で行う
    """
    # 処理件数カウンタ
    processed_count = 0
    # エラー件数カウンタ
    error_count = 0

    # --- 以下にワーカー処理を実装する ---
    # 1. DB から処理対象レコードを取得する
    # 2. 各レコードに対して connector.execute() を呼び出す
    # 3. 結果に応じてステータスを更新する
    # 4. db.commit() する

    logger.info(
        "テンプレートワーカー完了: processed=%d, errors=%d",
        processed_count,
        error_count,
    )
    return {
        "processed_count": processed_count,
        "error_count": error_count,
    }
