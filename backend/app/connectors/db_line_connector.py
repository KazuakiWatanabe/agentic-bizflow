"""
DB 書き込み LINE Connector を提供する。

本モジュールは 5 種類の workload kind に対応し、
実行時に DB にドメインレコードを書き込む connector を提供する。
Phase 2.5 の MockLineConnector を置き換える本番用 connector。

入出力: execute / dry_run で action 名と inputs を受け取り、結果 dict を返す。
制約: 外部 LINE API は呼び出さない。DB 書き込みのみ。

Note:
    - execute() は DB にレコードを書き込む（commit は呼び出し側の責務）
    - dry_run() は DB に書き込まず、プレビュー情報を返す
    - 将来の本番 LINE API 連携は Phase 4 以降の責務
"""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.connectors.base_connector import BaseConnector
from app.db.repositories.broadcast_repo import BroadcastRepository
from app.db.repositories.reminder_repo import ReminderRepository
from app.db.repositories.scenario_repo import ScenarioRepository
from app.db.repositories.tag_repo import TagRepository
from app.schemas.connector_capability import ConnectorCapability

logger = logging.getLogger(__name__)

# --- サポートするアクション一覧 ---
SUPPORTED_ACTIONS = [
    "tag.assign",
    "broadcast.schedule",
    "scenario.create",
    "scenario.start",
    "reminder.create",
]


class DBLineConnector(BaseConnector):
    """DB 書き込み LINE Connector。

    5 種類の workload kind に対応し、execute 時に DB にレコードを書き込む。
    dry_run 時は書き込みを行わず、プレビュー情報を返す。

    主要メソッド:
        execute: DB にレコードを書き込む
        dry_run: プレビュー情報を返す（DB 書き込みなし）
        capabilities: サポートするアクション一覧を返す

    Variables:
        _db: SQLAlchemy セッション

    Note:
        - commit は呼び出し側（route handler）の責務
        - execute 内では flush のみ行う
    """

    def __init__(self, db: Session) -> None:
        """DBLineConnector を初期化する。

        Args:
            db: SQLAlchemy セッション
        """
        # DB セッション
        self._db = db

    def execute(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """workload ステップを本実行し、DB にレコードを書き込む。

        Args:
            action: 実行するアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            実行結果を含む dict（status, message, created_records 等）

        Note:
            - サポート外のアクションは status="failed" を返す
            - commit は行わない（呼び出し側の責務）
        """
        dispatch = {
            "tag.assign": self._execute_tag_assign,
            "broadcast.schedule": self._execute_broadcast_schedule,
            "scenario.create": self._execute_scenario_create,
            "scenario.start": self._execute_scenario_start,
            "reminder.create": self._execute_reminder_create,
        }
        handler = dispatch.get(action)
        if handler is None:
            return {
                "status": "failed",
                "error_code": "UNSUPPORTED_ACTION",
                "message": f"サポートされていないアクション: {action}",
            }
        return handler(inputs)

    def dry_run(self, action: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """副作用なしで実行プレビューを返す。

        Args:
            action: プレビュー対象のアクション名
            inputs: アクションに渡す入力パラメータ

        Returns:
            プレビュー情報を含む dict

        Note:
            - DB への書き込みは一切行わない
        """
        preview_dispatch = {
            "tag.assign": TagRepository.preview,
            "broadcast.schedule": BroadcastRepository.preview,
            "scenario.create": ScenarioRepository.preview_create,
            "scenario.start": ScenarioRepository.preview_start,
            "reminder.create": ReminderRepository.preview,
        }
        handler = preview_dispatch.get(action)
        if handler is None:
            return {
                "preview": f"{action} を実行します",
                "estimated_target_count": 0,
            }
        return handler(inputs)

    def capabilities(self) -> ConnectorCapability:
        """DB LINE Connector のサポートアクション一覧を返す。

        Returns:
            ConnectorCapability モデル
        """
        return ConnectorCapability(
            connector="line",
            supported_actions=SUPPORTED_ACTIONS,
            supports_dry_run=True,
            supports_rollback=False,
            supports_schedule=True,
        )

    def _execute_tag_assign(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """tag.assign を実行し、tags + tag_assignments に書き込む。

        Args:
            inputs: tag_name, target を含む入力パラメータ

        Returns:
            実行結果 dict

        Variables:
            tag_name: 付与するタグ名
            target_id: 対象者 ID

        Note:
            - タグが存在しない場合は新規作成する（UPSERT）
        """
        tag_name = inputs.get("tag_name", "")
        target_id = inputs.get("target", "default_target")

        tag = TagRepository.upsert_tag(self._db, name=tag_name)
        TagRepository.assign_tag(self._db, tag_id=tag.id, target_id=target_id)

        logger.info("tag.assign 実行: tag=%s, target=%s", tag_name, target_id)
        return {
            "status": "success",
            "message": f"タグ '{tag_name}' を付与しました",
            "created_records": {"tags": 1, "tag_assignments": 1},
        }

    def _execute_broadcast_schedule(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """broadcast.schedule を実行し、broadcasts に書き込む。

        Args:
            inputs: message を含む入力パラメータ

        Returns:
            実行結果 dict

        Note:
            - status=scheduled で INSERT する
        """
        message = inputs.get("message", "一斉配信")

        BroadcastRepository.create_broadcast(
            db=self._db,
            title=message,
            message_content=message,
        )

        logger.info("broadcast.schedule 実行: message=%s", message)
        return {
            "status": "success",
            "message": "配信を予約しました",
            "created_records": {"broadcasts": 1},
        }

    def _execute_scenario_create(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """scenario.create を実行し、scenarios + scenario_steps に書き込む。

        Args:
            inputs: scenario_name, steps を含む入力パラメータ

        Returns:
            実行結果 dict
        """
        name = inputs.get("scenario_name", "シナリオ")
        steps = inputs.get("steps", [])

        scenario = ScenarioRepository.create_scenario(
            db=self._db,
            name=name,
        )
        created_steps = ScenarioRepository.create_steps(
            db=self._db,
            scenario_id=scenario.id,
            steps=steps,
        )

        logger.info(
            "scenario.create 実行: name=%s, steps=%d",
            name,
            len(created_steps),
        )
        return {
            "status": "success",
            "message": "シナリオを作成しました",
            "created_records": {
                "scenarios": 1,
                "scenario_steps": len(created_steps),
            },
        }

    def _execute_scenario_start(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """scenario.start を実行し、scenario_enrollments に書き込む。

        Args:
            inputs: scenario_name, target を含む入力パラメータ

        Returns:
            実行結果 dict

        Note:
            - scenario_name から既存シナリオを検索する
            - 見つからない場合はエラーとする
        """
        name = inputs.get("scenario_name", "")
        target_id = inputs.get("target", "default_target")

        from app.db.models import ScenarioModel

        scenario = self._db.query(ScenarioModel).filter_by(name=name).first()
        if scenario is None:
            return {
                "status": "failed",
                "error_code": "SCENARIO_NOT_FOUND",
                "message": f"シナリオ '{name}' が見つかりません",
            }

        ScenarioRepository.enroll(
            db=self._db,
            scenario_id=scenario.id,
            target_id=target_id,
        )

        logger.info(
            "scenario.start 実行: scenario=%s, target=%s",
            name,
            target_id,
        )
        return {
            "status": "success",
            "message": "シナリオ配信を開始しました",
            "created_records": {"scenario_enrollments": 1},
        }

    def _execute_reminder_create(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """reminder.create を実行し、reminders + reminder_steps に書き込む。

        Args:
            inputs: reminder_name, steps を含む入力パラメータ

        Returns:
            実行結果 dict
        """
        name = inputs.get("reminder_name", "リマインダー")
        steps = inputs.get("steps", [])

        reminder = ReminderRepository.create_reminder(
            db=self._db,
            name=name,
        )
        created_steps = ReminderRepository.create_steps(
            db=self._db,
            reminder_id=reminder.id,
            steps=steps,
        )

        logger.info(
            "reminder.create 実行: name=%s, steps=%d",
            name,
            len(created_steps),
        )
        return {
            "status": "success",
            "message": "リマインダーを作成しました",
            "created_records": {
                "reminders": 1,
                "reminder_steps": len(created_steps),
            },
        }
