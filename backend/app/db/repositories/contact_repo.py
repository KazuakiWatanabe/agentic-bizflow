"""
連絡先の CRUD リポジトリを提供する。

本モジュールは contacts / contact_channels テーブルに対する操作を提供する。
チャネル非依存の連絡先管理を実現する。

入出力: Session と入力パラメータを受け取り、ORM モデルを返す。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - contact_id は UUID v4 の文字列型
    - (channel_type, external_id) は UNIQUE 制約により一意
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import ContactChannelModel, ContactModel


class ContactRepository:
    """連絡先の CRUD 操作を提供する。

    主要メソッド:
        create_contact: 連絡先を作成する
        get_contact: 連絡先を取得する
        find_by_external_id: 外部 ID で連絡先を検索する
        add_channel: チャネルを追加する
        resolve_external_id: チャネル種別の外部 ID を取得する
        list_contacts: 連絡先一覧を取得する

    Note:
        - commit は行わない
    """

    @staticmethod
    def create_contact(
        db: Session,
        display_name: Optional[str] = None,
        channels: Optional[List[Dict[str, str]]] = None,
    ) -> ContactModel:
        """連絡先を作成する。

        Args:
            db: SQLAlchemy セッション
            display_name: 表示名
            channels: チャネル情報のリスト。各要素は
                      {"channel_type": str, "external_id": str} の dict。

        Returns:
            作成された ContactModel インスタンス

        Note:
            - channels が指定されている場合、同時にチャネルも作成する
        """
        now = datetime.now(timezone.utc)
        # 連絡先の作成
        contact = ContactModel(
            id=str(uuid.uuid4()),
            display_name=display_name,
            metadata_json="{}",
            created_at=now,
            updated_at=now,
        )
        db.add(contact)
        db.flush()

        # チャネルの同時作成
        if channels:
            for ch in channels:
                channel = ContactChannelModel(
                    id=str(uuid.uuid4()),
                    contact_id=contact.id,
                    channel_type=ch["channel_type"],
                    external_id=ch["external_id"],
                    created_at=now,
                )
                db.add(channel)
            db.flush()

        return contact

    @staticmethod
    def get_contact(db: Session, contact_id: str) -> Optional[ContactModel]:
        """連絡先を ID で取得する。

        Args:
            db: SQLAlchemy セッション
            contact_id: 連絡先 ID

        Returns:
            ContactModel または None
        """
        return db.query(ContactModel).filter_by(id=contact_id).first()

    @staticmethod
    def find_by_external_id(
        db: Session,
        channel_type: str,
        external_id: str,
    ) -> Optional[ContactModel]:
        """外部 ID で連絡先を検索する。

        Args:
            db: SQLAlchemy セッション
            channel_type: チャネル種別（例: line, email）
            external_id: チャネル側の外部 ID

        Returns:
            ContactModel または None

        Note:
            - (channel_type, external_id) の UNIQUE 制約により最大 1 件
        """
        channel = (
            db.query(ContactChannelModel)
            .filter_by(channel_type=channel_type, external_id=external_id)
            .first()
        )
        if channel is None:
            return None
        return db.query(ContactModel).filter_by(id=channel.contact_id).first()

    @staticmethod
    def add_channel(
        db: Session,
        contact_id: str,
        channel_type: str,
        external_id: str,
    ) -> ContactChannelModel:
        """連絡先にチャネルを追加する。

        Args:
            db: SQLAlchemy セッション
            contact_id: 連絡先 ID
            channel_type: チャネル種別
            external_id: チャネル側の外部 ID

        Returns:
            作成された ContactChannelModel インスタンス
        """
        now = datetime.now(timezone.utc)
        channel = ContactChannelModel(
            id=str(uuid.uuid4()),
            contact_id=contact_id,
            channel_type=channel_type,
            external_id=external_id,
            created_at=now,
        )
        db.add(channel)
        db.flush()
        return channel

    @staticmethod
    def resolve_external_id(
        db: Session,
        contact_id: str,
        channel_type: str,
    ) -> Optional[str]:
        """連絡先のチャネル別外部 ID を取得する。

        Args:
            db: SQLAlchemy セッション
            contact_id: 連絡先 ID
            channel_type: チャネル種別

        Returns:
            外部 ID 文字列、見つからない場合は None
        """
        channel = (
            db.query(ContactChannelModel)
            .filter_by(contact_id=contact_id, channel_type=channel_type)
            .first()
        )
        if channel is None:
            return None
        return channel.external_id

    @staticmethod
    def list_contacts(
        db: Session,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ContactModel]:
        """連絡先一覧を取得する。

        Args:
            db: SQLAlchemy セッション
            skip: オフセット
            limit: 取得件数上限

        Returns:
            ContactModel のリスト

        Note:
            - created_at の降順で取得する
        """
        return (
            db.query(ContactModel)
            .order_by(ContactModel.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
