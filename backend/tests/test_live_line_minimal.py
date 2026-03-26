"""
LiveLineConnector の LINE API 呼び出しテスト（最小構成）。

本モジュールは LiveLineConnector の tag.assign アクションが
LINE API を呼び出す動作を検証する。httpx をモックして検証する。

入出力: LiveLineConnector のメソッドを呼び出し、httpx の呼び出しを検証する。
制約: 外部 LINE API は使わない。httpx.Client.post をモック化する。

Note:
    - tag.assign で LINE API が呼ばれることを確認する
    - tag.assign 以外のアクションは DB connector にフォールバックすることを確認する
    - dry_run では LINE API が呼ばれないことを確認する
"""

from unittest.mock import MagicMock, patch

from app.connectors.live_line_connector import LiveLineConnector


def test_tag_assign_calls_line_api(db_session) -> None:
    """tag.assign 実行時に LINE API が呼び出されることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: LiveLineConnector インスタンス
        mock_response: モック化された httpx レスポンス
        result: execute の結果
        call_args: httpx.Client.post の呼び出し引数

    Note:
        - LINE_CHANNEL_ACCESS_TOKEN が設定されている場合のみ LINE API を呼ぶ
        - httpx.Client.post をモック化して呼び出し URL を検証する
    """
    connector = LiveLineConnector(db=db_session)

    # httpx.Client.post をモック化
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch(
        "app.connectors.live_line_connector.LINE_CHANNEL_ACCESS_TOKEN",
        "test-token-123",
    ), patch("httpx.Client") as mock_client_class:
        # Client() のコンテキストマネージャをモック化
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        result = connector.execute(
            "tag.assign",
            {"tag_name": "VIP", "target": "user_001"},
        )

    # DB 書き込みが成功していること
    assert result["status"] == "success"

    # LINE API が呼び出されたこと
    mock_client_instance.post.assert_called_once()
    call_args = mock_client_instance.post.call_args

    # URL にタグ付与エンドポイントが含まれていること
    assert "richmenu/tag/assign" in call_args[1].get("url", call_args[0][0])


def test_non_tag_assign_falls_back_to_db_connector(db_session) -> None:
    """tag.assign 以外のアクションが DB connector にフォールバックすることを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: LiveLineConnector インスタンス
        result: execute の結果

    Note:
        - broadcast.schedule は DBLineConnector に委譲される
        - LINE API は呼び出されない
    """
    connector = LiveLineConnector(db=db_session)

    with patch("httpx.Client") as mock_client_class:
        result = connector.execute(
            "broadcast.schedule",
            {"message": "テスト配信"},
        )

        # httpx.Client が呼ばれていないこと
        mock_client_class.assert_not_called()

    # DB 書き込みが成功していること
    assert result["status"] == "success"


def test_dry_run_does_not_call_line_api(db_session) -> None:
    """dry_run 時に LINE API が呼ばれないことを確認する。

    Args:
        db_session: テスト用 DB セッション

    Variables:
        connector: LiveLineConnector インスタンス
        result: dry_run の結果

    Note:
        - dry_run は DBLineConnector の dry_run に委譲される
        - LINE API は一切呼び出されない
    """
    connector = LiveLineConnector(db=db_session)

    with patch("httpx.Client") as mock_client_class:
        result = connector.dry_run(
            "tag.assign",
            {"tag_name": "VIP", "target": "user_001"},
        )

        # httpx.Client が呼ばれていないこと
        mock_client_class.assert_not_called()

    # プレビュー情報が返ること
    assert "preview" in result or "estimated_target_count" in result
