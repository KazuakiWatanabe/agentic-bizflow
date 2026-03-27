"""
マーケティング API エンドポイントを提供する。

本モジュールは共通 workload kind 一覧と連絡先管理の API を提供する。
Marketing Channel Abstraction の外部インターフェースとして、
チャネル非依存の業務管理を実現する。

入出力: GET/POST リクエスト → 共通 kind 情報 / 連絡先情報
制約: 読み取り + 作成のみ。既存テーブルの更新は行わない。

Note:
    - /api/marketing/kinds: 共通 kind 一覧と解決可能ドメイン情報
    - /api/marketing/contacts: 連絡先の CRUD
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.connectors.workload_kind_registry import workload_kind_registry
from app.db.models import ContactModel
from app.db.repositories.contact_repo import ContactRepository
from app.db.session import get_db
from app.schemas.contact import (
    ContactChannel,
    ContactCreateRequest,
    ContactItem,
    ContactListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# レスポンスモデル
# ============================================================


class CommonKindItem(BaseModel):
    """共通 kind の表示用モデル。

    Variables:
        kind: 共通 workload kind 識別子
        description: 人間向け説明
        requires_approval: 承認ルール
        keywords: キーワードリスト
        resolvable_domains: 解決可能なドメイン名のリスト
    """

    model_config = ConfigDict(extra="forbid")

    kind: str
    description: str
    requires_approval: str
    keywords: List[str]
    resolvable_domains: List[str]


class CommonKindListResponse(BaseModel):
    """共通 kind 一覧レスポンス。

    Variables:
        kinds: 共通 kind のリスト
    """

    model_config = ConfigDict(extra="forbid")

    kinds: List[CommonKindItem]


# ============================================================
# エンドポイント: 共通 kind
# ============================================================


@router.get("/marketing/kinds", response_model=CommonKindListResponse)
def list_common_kinds() -> CommonKindListResponse:
    """共通 workload kind 一覧と解決可能ドメインを取得する。

    Returns:
        CommonKindListResponse: 共通 kind 一覧

    Variables:
        common_kinds: domain="common" の workload kind リスト
        items: レスポンス用の CommonKindItem リスト
        resolution: 各 kind の resolution マッピング
        resolvable: 解決先が None でないドメインのリスト

    Note:
        - domain="common" の kind のみ返す
        - resolvable_domains は解決先が None でないドメインを列挙する
    """
    # domain="common" の kind を取得
    common_kinds = workload_kind_registry.list_by_domain("common")
    items: List[CommonKindItem] = []

    for k in common_kinds:
        # resolution マッピングから解決可能ドメインを抽出
        resolution = workload_kind_registry.get_resolution(k.kind)
        resolvable: List[str] = []
        if resolution:
            resolvable = [
                domain for domain, target in resolution.items() if target is not None
            ]

        items.append(
            CommonKindItem(
                kind=k.kind,
                description=k.description,
                requires_approval=k.requires_approval.value,
                keywords=k.keywords,
                resolvable_domains=resolvable,
            )
        )

    return CommonKindListResponse(kinds=items)


# ============================================================
# エンドポイント: 連絡先
# ============================================================


@router.get("/marketing/contacts", response_model=ContactListResponse)
def list_contacts(
    skip: int = Query(0, ge=0, description="オフセット"),
    limit: int = Query(50, ge=1, le=200, description="取得件数上限"),
    db: Session = Depends(get_db),
) -> ContactListResponse:
    """連絡先一覧を取得する（ページネーション付き）。

    Args:
        skip: オフセット
        limit: 取得件数上限
        db: DB セッション（DI）

    Returns:
        ContactListResponse: 連絡先一覧

    Variables:
        total: 連絡先の総件数
        contacts: 取得した連絡先リスト
        items: レスポンス用の ContactItem リスト
    """
    # 総件数
    total = db.query(func.count(ContactModel.id)).scalar() or 0

    # 連絡先一覧
    contacts = ContactRepository.list_contacts(db, skip=skip, limit=limit)
    items: List[ContactItem] = []

    for c in contacts:
        channels = [
            ContactChannel(
                channel_type=ch.channel_type,
                external_id=ch.external_id,
            )
            for ch in c.channels
        ]
        items.append(
            ContactItem(
                id=c.id,
                display_name=c.display_name,
                channels=channels,
            )
        )

    return ContactListResponse(contacts=items, total=total)


@router.get("/marketing/contacts/{contact_id}", response_model=ContactItem)
def get_contact(
    contact_id: str,
    db: Session = Depends(get_db),
) -> ContactItem:
    """連絡先詳細を取得する。

    Args:
        contact_id: 連絡先 ID
        db: DB セッション（DI）

    Returns:
        ContactItem: 連絡先詳細

    Raises:
        HTTPException: 見つからない場合は 404
    """
    contact = ContactRepository.get_contact(db, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")

    channels = [
        ContactChannel(
            channel_type=ch.channel_type,
            external_id=ch.external_id,
        )
        for ch in contact.channels
    ]

    return ContactItem(
        id=contact.id,
        display_name=contact.display_name,
        channels=channels,
    )


@router.post("/marketing/contacts", response_model=ContactItem, status_code=201)
def create_contact(
    request: ContactCreateRequest,
    db: Session = Depends(get_db),
) -> ContactItem:
    """連絡先を作成する。

    Args:
        request: 連絡先作成リクエスト
        db: DB セッション（DI）

    Returns:
        ContactItem: 作成された連絡先

    Variables:
        channel_dicts: チャネル情報の dict リスト
        contact: 作成された ContactModel

    Note:
        - channels が指定されている場合、同時にチャネルも作成する
    """
    # チャネル情報を dict リストに変換
    channel_dicts = [
        {"channel_type": ch.channel_type, "external_id": ch.external_id}
        for ch in request.channels
    ]

    contact = ContactRepository.create_contact(
        db,
        display_name=request.display_name,
        channels=channel_dicts if channel_dicts else None,
    )
    db.commit()

    # リレーションをリフレッシュ
    db.refresh(contact)

    channels = [
        ContactChannel(
            channel_type=ch.channel_type,
            external_id=ch.external_id,
        )
        for ch in contact.channels
    ]

    return ContactItem(
        id=contact.id,
        display_name=contact.display_name,
        channels=channels,
    )
