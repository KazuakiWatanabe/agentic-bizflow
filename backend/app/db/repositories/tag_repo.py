"""
タグ関連の CRUD リポジトリを提供する。

本モジュールは tags / tag_assignments テーブルに対する操作を提供する。

入出力: Session と入力パラメータを受け取り、ORM モデルを返す。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - tag.assign では既存タグの UPSERT（存在確認後に INSERT）を行う
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.db.models import TagAssignmentModel, TagModel


class TagRepository:
    """タグ関連の CRUD 操作を提供する。

    主要メソッド:
        upsert_tag: タグ名で UPSERT する
        assign_tag: 対象者にタグを付与する

    Note:
        - commit は行わない
    """

    @staticmethod
    def upsert_tag(db: Session, name: str) -> TagModel:
        """タグ名で既存タグを検索し、なければ新規作成する。

        Args:
            db: SQLAlchemy セッション
            name: タグ名

        Returns:
            TagModel インスタンス

        Note:
            - 既存タグがあればそれを返す
        """
        tag = db.query(TagModel).filter_by(name=name).first()
        if tag:
            return tag
        tag = TagModel(
            id=str(uuid.uuid4()),
            name=name,
            created_at=datetime.now(timezone.utc),
        )
        db.add(tag)
        db.flush()
        return tag

    @staticmethod
    def assign_tag(db: Session, tag_id: str, target_id: str) -> TagAssignmentModel:
        """対象者にタグを付与する。

        Args:
            db: SQLAlchemy セッション
            tag_id: タグ ID
            target_id: 対象者の外部 ID

        Returns:
            TagAssignmentModel インスタンス

        Note:
            - 既に付与済みの場合は既存レコードを返す
        """
        existing = (
            db.query(TagAssignmentModel)
            .filter_by(target_id=target_id, tag_id=tag_id)
            .first()
        )
        if existing:
            return existing
        assignment = TagAssignmentModel(
            target_id=target_id,
            tag_id=tag_id,
            assigned_at=datetime.now(timezone.utc),
        )
        db.add(assignment)
        db.flush()
        return assignment

    @staticmethod
    def preview(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """tag.assign の dry-run プレビューを返す。

        Args:
            inputs: アクションの入力パラメータ

        Returns:
            プレビュー情報の dict
        """
        tag_name = inputs.get("tag_name", "")
        target = inputs.get("target", "対象者")
        return {
            "preview": f"タグ '{tag_name}' を {target} に付与します",
            "estimated_target_count": 1,
        }
