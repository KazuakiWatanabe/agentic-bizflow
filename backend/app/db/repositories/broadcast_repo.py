"""
一斉配信関連の CRUD リポジトリを提供する。

本モジュールは broadcasts テーブルに対する操作を提供する。

入出力: Session と入力パラメータを受け取り、ORM モデルを返す。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - broadcast.schedule では status=scheduled で INSERT する
    - sending / sent への遷移は Phase 4 の責務
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db.models import BroadcastModel


class BroadcastRepository:
    """一斉配信の CRUD 操作を提供する。

    主要メソッド:
        create_broadcast: 配信予約を作成する

    Note:
        - commit は行わない
    """

    @staticmethod
    def create_broadcast(
        db: Session,
        title: str,
        message_content: str,
        execution_plan_id: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
    ) -> BroadcastModel:
        """配信予約を作成する。

        Args:
            db: SQLAlchemy セッション
            title: 配信タイトル
            message_content: メッセージ本文
            execution_plan_id: 生成元の plan ID
            scheduled_at: 予約配信日時

        Returns:
            BroadcastModel インスタンス

        Note:
            - status は 'scheduled' で作成する
        """
        record = BroadcastModel(
            id=str(uuid.uuid4()),
            title=title,
            message_content=message_content,
            status="scheduled",
            execution_plan_id=execution_plan_id,
            scheduled_at=scheduled_at or datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def preview(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """broadcast.schedule の dry-run プレビューを返す。

        Args:
            inputs: アクションの入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        message = inputs.get("message", "一斉配信")
        return {
            "preview": f"一斉配信を予約します: {message}",
            "estimated_target_count": 10,
        }
