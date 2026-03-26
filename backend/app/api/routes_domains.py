"""
ドメイン管理エンドポイントを提供する。

本モジュールはドメインの一覧・詳細・設定更新・有効化・無効化と、
workload kind 一覧の API を提供する。

入出力: GET/PUT/POST リクエスト → ドメイン情報 / workload kind 情報
制約: Workload Kind Registry のシングルトンを参照する。

Note:
    - ドメイン設定は domain_configs テーブルで管理する
    - workload kind は Workload Kind Registry から動的に取得する
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.connectors.workload_kind_registry import workload_kind_registry
from app.db.repositories.domain_config_repo import DomainConfigRepository
from app.db.session import get_db
from app.schemas.domain_config import (
    DomainConfigUpdateRequest,
    DomainDetailResponse,
    DomainInfo,
    DomainListResponse,
    WorkloadKindItem,
    WorkloadKindListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/domains", response_model=DomainListResponse)
def list_domains(
    db: Session = Depends(get_db),
) -> DomainListResponse:
    """有効なドメイン一覧を取得する。

    Args:
        db: DB セッション（DI）

    Returns:
        DomainListResponse: 有効なドメイン一覧
    """
    records = DomainConfigRepository.list_enabled(db)
    domains = []
    for r in records:
        # Registry からこのドメインの workload kind を取得
        kinds = workload_kind_registry.list_by_domain(r.domain)
        # kind 名のリスト
        kind_names = [k.kind for k in kinds]
        domains.append(
            DomainInfo(
                domain=r.domain,
                display_name=r.display_name,
                is_enabled=r.is_enabled,
                workload_kinds=kind_names,
            )
        )
    return DomainListResponse(domains=domains)


@router.get("/domains/{domain}", response_model=DomainDetailResponse)
def get_domain(
    domain: str,
    db: Session = Depends(get_db),
) -> DomainDetailResponse:
    """ドメイン詳細を取得する。

    Args:
        domain: 取得対象のドメイン名
        db: DB セッション（DI）

    Returns:
        DomainDetailResponse: ドメイン詳細

    Raises:
        HTTPException: 見つからない場合は 404
    """
    record = DomainConfigRepository.get(db, domain)
    if record is None:
        raise HTTPException(status_code=404, detail="domain not found")

    # 設定 JSON のパース
    try:
        config = json.loads(record.config_json)
    except (json.JSONDecodeError, TypeError):
        config = {}

    # Registry からこのドメインの workload kind を取得
    kinds = workload_kind_registry.list_by_domain(domain)
    kind_details = [
        {
            "kind": k.kind,
            "domain": k.domain,
            "connector": k.connector,
            "description": k.description,
            "requires_approval": k.requires_approval.value,
        }
        for k in kinds
    ]

    return DomainDetailResponse(
        domain=record.domain,
        display_name=record.display_name,
        is_enabled=record.is_enabled,
        config=config,
        workload_kinds=kind_details,
    )


@router.put("/domains/{domain}/config", response_model=DomainDetailResponse)
def update_domain_config(
    domain: str,
    request: DomainConfigUpdateRequest,
    db: Session = Depends(get_db),
) -> DomainDetailResponse:
    """ドメイン設定を更新する。

    Args:
        domain: 更新対象のドメイン名
        request: 更新する設定
        db: DB セッション（DI）

    Returns:
        DomainDetailResponse: 更新後のドメイン詳細

    Raises:
        HTTPException: 見つからない場合は 404
    """
    record = DomainConfigRepository.get(db, domain)
    if record is None:
        raise HTTPException(status_code=404, detail="domain not found")

    # 設定 JSON を更新
    config_str = json.dumps(request.config, ensure_ascii=False)
    record.config_json = config_str
    db.flush()
    db.commit()

    # 更新後の詳細を返す
    return get_domain(domain, db)


@router.post("/domains/{domain}/enable", response_model=DomainDetailResponse)
def enable_domain(
    domain: str,
    db: Session = Depends(get_db),
) -> DomainDetailResponse:
    """ドメインを有効化する。

    Args:
        domain: 有効化対象のドメイン名
        db: DB セッション（DI）

    Returns:
        DomainDetailResponse: 更新後のドメイン詳細

    Raises:
        HTTPException: 見つからない場合は 404
    """
    result = DomainConfigRepository.enable(db, domain)
    if result is None:
        raise HTTPException(status_code=404, detail="domain not found")
    db.commit()

    return get_domain(domain, db)


@router.post("/domains/{domain}/disable", response_model=DomainDetailResponse)
def disable_domain(
    domain: str,
    db: Session = Depends(get_db),
) -> DomainDetailResponse:
    """ドメインを無効化する。

    Args:
        domain: 無効化対象のドメイン名
        db: DB セッション（DI）

    Returns:
        DomainDetailResponse: 更新後のドメイン詳細

    Raises:
        HTTPException: 見つからない場合は 404
    """
    result = DomainConfigRepository.disable(db, domain)
    if result is None:
        raise HTTPException(status_code=404, detail="domain not found")
    db.commit()

    return get_domain(domain, db)


@router.get("/workload-kinds", response_model=WorkloadKindListResponse)
def list_workload_kinds() -> WorkloadKindListResponse:
    """全 workload kind 一覧を取得する。

    Returns:
        WorkloadKindListResponse: workload kind 一覧
    """
    all_kinds = workload_kind_registry.list_all()
    items = [
        WorkloadKindItem(
            kind=k.kind,
            domain=k.domain,
            connector=k.connector,
            description=k.description,
            requires_approval=k.requires_approval.value,
        )
        for k in all_kinds
    ]
    return WorkloadKindListResponse(kinds=items)
