"""
ContactRepository のユニットテスト。

本モジュールは contacts / contact_channels テーブルの CRUD 操作と
UNIQUE 制約を検証する。

入出力: db_session フィクスチャで in-memory SQLite に対して操作する。
制約: 外部 LLM は使わない。

Note:
    - conftest.py の db_session / _override_get_db フィクスチャを使用する
    - 各テスト後に rollback でデータを初期化する
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.repositories.contact_repo import ContactRepository


def test_create_contact_with_channels(db_session) -> None:
    """create_contact でチャネル付きの連絡先が作成されることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        channels: 作成するチャネル情報のリスト
        contact: 作成された ContactModel

    Note:
        - channels を同時に指定して一括作成する
    """
    channels = [
        {"channel_type": "line", "external_id": "U_LINE_001"},
        {"channel_type": "email", "external_id": "user@example.com"},
    ]
    contact = ContactRepository.create_contact(
        db_session,
        display_name="テストユーザー",
        channels=channels,
    )

    assert contact is not None
    assert contact.display_name == "テストユーザー"
    assert len(contact.channels) == 2

    # チャネル種別の検証
    channel_types = {ch.channel_type for ch in contact.channels}
    assert "line" in channel_types
    assert "email" in channel_types


def test_get_contact_returns_contact_with_channels(db_session) -> None:
    """get_contact が連絡先とチャネルを含めて返すことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        created: create_contact の戻り値
        fetched: get_contact の戻り値

    Note:
        - create_contact で作成した連絡先を get_contact で取得する
    """
    created = ContactRepository.create_contact(
        db_session,
        display_name="取得テスト",
        channels=[{"channel_type": "line", "external_id": "U_LINE_002"}],
    )

    fetched = ContactRepository.get_contact(db_session, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.display_name == "取得テスト"
    assert len(fetched.channels) == 1
    assert fetched.channels[0].channel_type == "line"


def test_find_by_external_id_works(db_session) -> None:
    """find_by_external_id で外部 ID から連絡先を検索できることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        created: create_contact の戻り値
        found: find_by_external_id の戻り値

    Note:
        - (channel_type, external_id) の組み合わせで検索する
    """
    created = ContactRepository.create_contact(
        db_session,
        display_name="検索テスト",
        channels=[{"channel_type": "line", "external_id": "U_LINE_003"}],
    )

    found = ContactRepository.find_by_external_id(
        db_session, channel_type="line", external_id="U_LINE_003"
    )
    assert found is not None
    assert found.id == created.id
    assert found.display_name == "検索テスト"


def test_resolve_external_id_returns_correct_id(db_session) -> None:
    """resolve_external_id が正しい external_id を返すことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        contact: 作成された連絡先
        line_id: line チャネルの external_id
        email_id: email チャネルの external_id

    Note:
        - チャネル種別ごとに正しい external_id を返す
    """
    contact = ContactRepository.create_contact(
        db_session,
        display_name="resolve テスト",
        channels=[
            {"channel_type": "line", "external_id": "U_LINE_004"},
            {"channel_type": "email", "external_id": "resolve@example.com"},
        ],
    )

    line_id = ContactRepository.resolve_external_id(db_session, contact.id, "line")
    assert line_id == "U_LINE_004"

    email_id = ContactRepository.resolve_external_id(db_session, contact.id, "email")
    assert email_id == "resolve@example.com"


def test_unique_constraint_channel_type_external_id(db_session) -> None:
    """(channel_type, external_id) の UNIQUE 制約が機能することを確認する。

    Args:
        db_session: テスト用 DB セッション

    Note:
        - 同一の (channel_type, external_id) で 2 つ目を作成すると IntegrityError
    """
    ContactRepository.create_contact(
        db_session,
        display_name="ユーザーA",
        channels=[{"channel_type": "line", "external_id": "U_DUPLICATE"}],
    )

    with pytest.raises(IntegrityError):
        ContactRepository.create_contact(
            db_session,
            display_name="ユーザーB",
            channels=[{"channel_type": "line", "external_id": "U_DUPLICATE"}],
        )
