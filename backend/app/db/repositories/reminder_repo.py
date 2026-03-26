"""
リマインダー関連の CRUD リポジトリを提供する。

本モジュールは reminders / reminder_steps テーブルに対する操作を提供する。

入出力: Session と入力パラメータを受け取り、ORM モデルを返す。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - reminder.create ではリマインダーとステップを同時に作成する
    - enrollment / delivery は Phase 4 の責務
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import ReminderModel, ReminderStepModel


class ReminderRepository:
    """リマインダー関連の CRUD 操作を提供する。

    主要メソッド:
        create_reminder: リマインダーを作成する
        create_steps: リマインダーステップを作成する

    Note:
        - commit は行わない
    """

    @staticmethod
    def create_reminder(
        db: Session,
        name: str,
        description: Optional[str] = None,
        execution_plan_id: Optional[str] = None,
    ) -> ReminderModel:
        """リマインダーを作成する。

        Args:
            db: SQLAlchemy セッション
            name: リマインダ名
            description: 説明
            execution_plan_id: 生成元の plan ID

        Returns:
            ReminderModel インスタンス
        """
        now = datetime.now(timezone.utc)
        record = ReminderModel(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            execution_plan_id=execution_plan_id,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def create_steps(
        db: Session,
        reminder_id: str,
        steps: List[str],
    ) -> List[ReminderStepModel]:
        """リマインダーステップを作成する。

        Args:
            db: SQLAlchemy セッション
            reminder_id: リマインダ ID
            steps: メッセージテキストのリスト

        Returns:
            ReminderStepModel のリスト

        Note:
            - offset_minutes はステップ順 × 60 でデフォルト設定する
        """
        records: List[ReminderStepModel] = []
        now = datetime.now(timezone.utc)
        for i, content in enumerate(steps):
            record = ReminderStepModel(
                id=str(uuid.uuid4()),
                reminder_id=reminder_id,
                offset_minutes=i * 60,
                message_content=content,
                created_at=now,
            )
            db.add(record)
            records.append(record)
        db.flush()
        return records

    @staticmethod
    def preview(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """reminder.create の dry-run プレビューを返す。

        Args:
            inputs: アクションの入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        name = inputs.get("reminder_name", "リマインダー")
        steps = inputs.get("steps", [])
        return {
            "preview": f"リマインダー '{name}' を作成します（{len(steps)} ステップ）",
            "estimated_target_count": 0,
        }
