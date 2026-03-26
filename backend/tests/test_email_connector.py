"""
EmailConnector のユニットテスト。

本モジュールは Email ドメインの DB 書き込みコネクタ（EmailConnector）の
execute / dry_run / capabilities メソッドを検証する。

入出力: action 名と inputs → 結果 dict / プレビュー dict / ConnectorCapability。
制約: 外部 LLM は使わない。SMTP は使わない。db_session で DB 操作を検証する。

Note:
    - execute は DB にレコードを書き込む
    - dry_run は DB に書き込まずプレビューを返す
    - capabilities はサポートアクション一覧を返す
"""

from app.db.models import EmailBroadcastModel, EmailTemplateModel
from app.domains.email.connector import EmailConnector


def test_execute_broadcast_schedule_creates_record(db_session) -> None:
    """execute('email.broadcast.schedule') が email_broadcasts に書き込むことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト対象の EmailConnector
        result: execute の戻り値
        records: DB から取得した email_broadcasts レコード

    Note:
        - status=scheduled でレコードが作成される
        - result['status'] が 'success' であること
    """
    connector = EmailConnector(db=db_session)
    result = connector.execute(
        "email.broadcast.schedule",
        {
            "subject": "テスト配信",
            "body_html": "<p>テスト本文</p>",
            "from_address": "test@example.com",
        },
    )

    assert result["status"] == "success"
    assert "broadcast_id" in result

    # DB にレコードが書き込まれたことを確認
    records = db_session.query(EmailBroadcastModel).all()
    assert len(records) == 1
    assert records[0].subject == "テスト配信"
    assert records[0].status == "scheduled"


def test_execute_template_create_creates_record(db_session) -> None:
    """execute('email.template.create') が email_templates に書き込むことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト対象の EmailConnector
        result: execute の戻り値
        records: DB から取得した email_templates レコード

    Note:
        - result['status'] が 'success' であること
        - email_templates テーブルにレコードが 1 件作成される
    """
    connector = EmailConnector(db=db_session)
    result = connector.execute(
        "email.template.create",
        {
            "name": "テストテンプレート",
            "subject": "件名テスト",
            "body_html": "<p>テンプレ本文</p>",
        },
    )

    assert result["status"] == "success"
    assert "template_id" in result

    # DB にレコードが書き込まれたことを確認
    records = db_session.query(EmailTemplateModel).all()
    assert len(records) == 1
    assert records[0].name == "テストテンプレート"
    assert records[0].subject == "件名テスト"


def test_dry_run_returns_preview_without_db_writes(db_session) -> None:
    """dry_run が DB に書き込まずプレビューを返すことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト対象の EmailConnector
        preview: dry_run の戻り値
        broadcast_count: email_broadcasts テーブルのレコード数
        template_count: email_templates テーブルのレコード数

    Note:
        - dry_run 後に DB のレコード数が 0 であることを検証
    """
    connector = EmailConnector(db=db_session)

    # broadcast の dry_run
    preview = connector.dry_run(
        "email.broadcast.schedule",
        {"subject": "プレビュー配信"},
    )
    assert "preview" in preview
    assert "estimated_target_count" in preview

    # template の dry_run
    preview_template = connector.dry_run(
        "email.template.create",
        {"name": "プレビューテンプレート"},
    )
    assert "preview" in preview_template

    # DB に書き込みが発生していないことを確認
    broadcast_count = db_session.query(EmailBroadcastModel).count()
    template_count = db_session.query(EmailTemplateModel).count()
    assert broadcast_count == 0
    assert template_count == 0


def test_capabilities_returns_correct_actions(db_session) -> None:
    """capabilities が正しいアクション一覧を返すことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: テスト対象の EmailConnector
        caps: capabilities の戻り値

    Note:
        - connector 名が 'email' であること
        - supported_actions に email.broadcast.schedule, email.template.create が含まれる
    """
    connector = EmailConnector(db=db_session)
    caps = connector.capabilities()

    assert caps.connector == "email"
    assert "email.broadcast.schedule" in caps.supported_actions
    assert "email.template.create" in caps.supported_actions
    assert caps.supports_dry_run is True
