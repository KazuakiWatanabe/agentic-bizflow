"""
冪等性管理の CRUD リポジトリを提供する。

本モジュールは processed_idempotency_keys テーブルに対する操作を提供する。
WorkloadRunner が step 実行前にチェックし、処理済みならスキップする。

入出力: Session と idempotency_key を受け取り、存在チェックまたは INSERT を行う。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - 二重実行防止のためのキー管理
    - 処理済みキーが存在すれば True を返す
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ProcessedIdempotencyKeyModel


class IdempotencyRepository:
    """冪等性管理の CRUD 操作を提供する。

    主要メソッド:
        is_processed: キーが処理済みか判定する
        mark_processed: キーを処理済みとして記録する

    Note:
        - commit は行わない
    """

    @staticmethod
    def is_processed(db: Session, idempotency_key: str) -> bool:
        """idempotency_key が処理済みか判定する。

        Args:
            db: SQLAlchemy セッション
            idempotency_key: チェック対象のキー

        Returns:
            処理済みなら True
        """
        existing = (
            db.query(ProcessedIdempotencyKeyModel)
            .filter_by(idempotency_key=idempotency_key)
            .first()
        )
        return existing is not None

    @staticmethod
    def mark_processed(
        db: Session,
        idempotency_key: str,
        step_id: str,
        plan_id: str,
    ) -> ProcessedIdempotencyKeyModel:
        """idempotency_key を処理済みとして記録する。

        Args:
            db: SQLAlchemy セッション
            idempotency_key: 記録するキー
            step_id: ステップ ID
            plan_id: plan ID

        Returns:
            ProcessedIdempotencyKeyModel インスタンス
        """
        record = ProcessedIdempotencyKeyModel(
            idempotency_key=idempotency_key,
            step_id=step_id,
            plan_id=plan_id,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.flush()
        return record
