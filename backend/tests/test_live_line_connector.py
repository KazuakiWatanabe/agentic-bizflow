"""
LiveLineConnector のテスト（mock API）。

本モジュールは app.connectors.live_line_connector.LiveLineConnector の
動作を検証する。LINE API は呼び出さず、mock で検証する。

入出力: LiveLineConnector のメソッドを呼び出して結果を検証する。
制約: 外部 LINE API は使わない。LINE_CHANNEL_ACCESS_TOKEN は空の前提。

Note:
    - LINE_CHANNEL_ACCESS_TOKEN が空の場合は mock 成功レスポンスを返す
    - dry_run は API 呼び出しなしでプレビューを返す
    - capabilities は正しいアクション一覧を返す
"""

from app.connectors.live_line_connector import LiveLineConnector


def test_no_token_returns_mock_success() -> None:
    """LINE_CHANNEL_ACCESS_TOKEN が空の場合に mock 成功レスポンスを返すことを確認する。

    Variables:
        connector: LiveLineConnector インスタンス（DB なし）
        result: execute の結果

    Note:
        - TOKEN が空の場合、LINE API を呼ばずに mock レスポンスを返す
    """
    connector = LiveLineConnector(db=None)
    result = connector.execute(
        "broadcast.send",
        {
            "broadcast_id": "test-001",
            "title": "テスト",
            "message_content": "テストメッセージ",
            "target_type": "all",
        },
    )
    assert result["status"] == "success"
    assert "message" in result


def test_dry_run_returns_preview_without_api_call() -> None:
    """dry_run が API 呼び出しなしでプレビューを返すことを確認する。

    Variables:
        connector: LiveLineConnector インスタンス（DB なし）
        result: dry_run の結果

    Note:
        - dry_run は DB や外部 API に書き込まない
    """
    connector = LiveLineConnector(db=None)
    result = connector.dry_run(
        "broadcast.send",
        {
            "broadcast_id": "test-001",
            "title": "テスト",
            "message_content": "テストメッセージ",
            "target_type": "all",
        },
    )
    assert "preview" in result
    assert "estimated_target_count" in result


def test_capabilities_returns_correct_actions() -> None:
    """capabilities が正しいアクション一覧を返すことを確認する。

    Variables:
        connector: LiveLineConnector インスタンス（DB なし）
        caps: capabilities の結果
        actions: サポートアクションのリスト

    Note:
        - broadcast.send, scenario.deliver, reminder.deliver が含まれる
    """
    connector = LiveLineConnector(db=None)
    caps = connector.capabilities()

    assert caps.connector == "line"
    actions = caps.supported_actions
    assert "broadcast.send" in actions
    assert "scenario.deliver" in actions
    assert "reminder.deliver" in actions
    assert caps.supports_dry_run is True
