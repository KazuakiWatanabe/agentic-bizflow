"""
ドメイン設定の CRUD リポジトリを提供する。

本モジュールは domain_configs テーブルに対する操作を提供する。

入出力: Session と入力パラメータを受け取り、ORM モデルを返す。
制約: commit は行わない（呼び出し側の責務）。

Note:
    - domain は UNIQUE（1 ドメインにつき 1 レコード）
    - upsert は存在しなければ INSERT、存在すれば UPDATE する
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models import DomainConfigModel


class DomainConfigRepository:
    """ドメイン設定の CRUD 操作を提供する。

    主要メソッド:
        get: ドメイン名で設定を取得する
        list_enabled: 有効なドメイン設定一覧を取得する
        list_all: 全ドメイン設定一覧を取得する
        upsert: ドメイン設定を UPSERT する
        enable: ドメインを有効化する
        disable: ドメインを無効化する

    Note:
        - commit は行わない
    """

    @staticmethod
    def get(db: Session, domain: str) -> Optional[DomainConfigModel]:
        """ドメイン名で設定を取得する。

        Args:
            db: SQLAlchemy セッション
            domain: 検索対象のドメイン名

        Returns:
            DomainConfigModel または None
        """
        return db.query(DomainConfigModel).filter_by(domain=domain).first()

    @staticmethod
    def list_enabled(db: Session) -> List[DomainConfigModel]:
        """有効なドメイン設定一覧を取得する。

        Args:
            db: SQLAlchemy セッション

        Returns:
            有効な DomainConfigModel のリスト
        """
        return (
            db.query(DomainConfigModel)
            .filter_by(is_enabled=True)
            .order_by(DomainConfigModel.domain)
            .all()
        )

    @staticmethod
    def list_all(db: Session) -> List[DomainConfigModel]:
        """全ドメイン設定一覧を取得する。

        Args:
            db: SQLAlchemy セッション

        Returns:
            全 DomainConfigModel のリスト
        """
        return db.query(DomainConfigModel).order_by(DomainConfigModel.domain).all()

    @staticmethod
    def upsert(
        db: Session,
        domain: str,
        display_name: str,
        is_enabled: bool = False,
        config_json: Optional[Dict] = None,
    ) -> DomainConfigModel:
        """ドメイン設定を UPSERT する。

        存在しなければ INSERT、存在すれば UPDATE する。

        Args:
            db: SQLAlchemy セッション
            domain: ドメイン名
            display_name: 管理画面での表示名
            is_enabled: 有効/無効
            config_json: ドメイン固有設定（dict → JSON 文字列に変換）

        Returns:
            DomainConfigModel インスタンス

        Note:
            - config_json は dict を受け取り、JSON 文字列に変換して保存する
        """
        now = datetime.now(timezone.utc)
        # 設定 JSON のシリアライズ
        config_str = json.dumps(config_json or {}, ensure_ascii=False)

        existing = db.query(DomainConfigModel).filter_by(domain=domain).first()

        if existing:
            existing.display_name = display_name
            existing.is_enabled = is_enabled
            existing.config_json = config_str
            existing.updated_at = now
            db.flush()
            return existing

        record = DomainConfigModel(
            id=str(uuid.uuid4()),
            domain=domain,
            display_name=display_name,
            is_enabled=is_enabled,
            config_json=config_str,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def enable(db: Session, domain: str) -> Optional[DomainConfigModel]:
        """ドメインを有効化する。

        Args:
            db: SQLAlchemy セッション
            domain: 対象のドメイン名

        Returns:
            更新後の DomainConfigModel、見つからない場合は None
        """
        record = db.query(DomainConfigModel).filter_by(domain=domain).first()
        if record is None:
            return None
        record.is_enabled = True
        record.updated_at = datetime.now(timezone.utc)
        db.flush()
        return record

    @staticmethod
    def disable(db: Session, domain: str) -> Optional[DomainConfigModel]:
        """ドメインを無効化する。

        Args:
            db: SQLAlchemy セッション
            domain: 対象のドメイン名

        Returns:
            更新後の DomainConfigModel、見つからない場合は None
        """
        record = db.query(DomainConfigModel).filter_by(domain=domain).first()
        if record is None:
            return None
        record.is_enabled = False
        record.updated_at = datetime.now(timezone.utc)
        db.flush()
        return record
