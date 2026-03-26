"""
シナリオ関連の CRUD リポジトリを提供する。

本モジュールは scenarios / scenario_steps / scenario_enrollments テーブルに
対する操作を提供する。

入出力: Session と入力パラメータを受け取り、ORM モデルを返す。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - scenario.create ではシナリオとステップを同時に作成する
    - scenario.start では対象者を active 状態で enroll する
    - step 進行は Phase 4 の責務
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import (
    ScenarioEnrollmentModel,
    ScenarioModel,
    ScenarioStepModel,
)


class ScenarioRepository:
    """シナリオ関連の CRUD 操作を提供する。

    主要メソッド:
        create_scenario: シナリオを作成する
        create_steps: シナリオステップを作成する
        enroll: 対象者をシナリオに登録する

    Note:
        - commit は行わない
    """

    @staticmethod
    def create_scenario(
        db: Session,
        name: str,
        description: Optional[str] = None,
        execution_plan_id: Optional[str] = None,
    ) -> ScenarioModel:
        """シナリオを作成する。

        Args:
            db: SQLAlchemy セッション
            name: シナリオ名
            description: 説明
            execution_plan_id: 生成元の plan ID

        Returns:
            ScenarioModel インスタンス
        """
        now = datetime.now(timezone.utc)
        record = ScenarioModel(
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
        scenario_id: str,
        steps: List[str],
    ) -> List[ScenarioStepModel]:
        """シナリオステップを作成する。

        Args:
            db: SQLAlchemy セッション
            scenario_id: シナリオ ID
            steps: メッセージテキストのリスト

        Returns:
            ScenarioStepModel のリスト

        Note:
            - step_order は 1 始まりで自動付与する
        """
        records: List[ScenarioStepModel] = []
        now = datetime.now(timezone.utc)
        for i, content in enumerate(steps, start=1):
            record = ScenarioStepModel(
                id=str(uuid.uuid4()),
                scenario_id=scenario_id,
                step_order=i,
                message_content=content,
                created_at=now,
            )
            db.add(record)
            records.append(record)
        db.flush()
        return records

    @staticmethod
    def enroll(
        db: Session,
        scenario_id: str,
        target_id: str,
    ) -> ScenarioEnrollmentModel:
        """対象者をシナリオに登録する。

        Args:
            db: SQLAlchemy セッション
            scenario_id: シナリオ ID
            target_id: 対象者の外部 ID

        Returns:
            ScenarioEnrollmentModel インスタンス

        Note:
            - status は 'active' で作成する
        """
        now = datetime.now(timezone.utc)
        record = ScenarioEnrollmentModel(
            id=str(uuid.uuid4()),
            scenario_id=scenario_id,
            target_id=target_id,
            status="active",
            started_at=now,
            updated_at=now,
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def preview_create(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """scenario.create の dry-run プレビューを返す。

        Args:
            inputs: アクションの入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        name = inputs.get("scenario_name", "シナリオ")
        steps = inputs.get("steps", [])
        return {
            "preview": f"シナリオ '{name}' を作成します（{len(steps)} ステップ）",
            "estimated_target_count": 0,
        }

    @staticmethod
    def preview_start(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """scenario.start の dry-run プレビューを返す。

        Args:
            inputs: アクションの入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        name = inputs.get("scenario_name", "シナリオ")
        return {
            "preview": f"シナリオ '{name}' の配信を開始します",
            "estimated_target_count": 1,
        }
