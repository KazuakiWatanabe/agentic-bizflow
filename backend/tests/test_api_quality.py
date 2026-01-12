"""
API入力バリデーションの最小回帰テストを提供する。

入出力: TestClientで /health と /api/convert を呼び出す。
制約: 外部APIに依存せず、固定入力で検証する。

Note:
    - text 未指定や空文字の挙動は現行API仕様に従う
"""

from fastapi.testclient import TestClient

from app.main import app

# FastAPIのテストクライアント。
client = TestClient(app)


def test_health_ok() -> None:
    """/health が 200 を返すことを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        response:
            /health のレスポンス。

    Raises:
        AssertionError: レスポンスが期待値と異なる場合に発生
    """
    response = client.get("/health")

    assert response.status_code == 200


def test_convert_missing_text_400_or_422() -> None:
    """text 未指定時のステータスを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        response:
            /api/convert のレスポンス。

    Raises:
        AssertionError: 期待するステータスでない場合に発生

    Note:
        - 現行実装では 400 が返るため 400/422 を許容する
    """
    response = client.post("/api/convert", json={})

    assert response.status_code in (400, 422)


def test_convert_extra_field_422() -> None:
    """余計なフィールドで 422 になることを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        response:
            /api/convert のレスポンス。

    Raises:
        AssertionError: 422 以外が返る場合に発生
    """
    response = client.post("/api/convert", json={"text": "ok", "extra": 1})

    assert response.status_code == 422


def test_convert_empty_text_400_or_422() -> None:
    """text が空文字の時のステータスを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        response:
            /api/convert のレスポンス。

    Raises:
        AssertionError: 期待するステータスでない場合に発生

    Note:
        - 現行実装では 400 が返るため 400/422 を許容する
    """
    response = client.post("/api/convert", json={"text": ""})

    assert response.status_code in (400, 422)
