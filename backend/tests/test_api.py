"""
FastAPIエンドポイントの最小動作を確認する。

入出力: TestClientで /health と /api/convert を呼び出す。
制約: 外部LLMは使わず、スタブOrchestratorの結果を確認する。

Note:
    - /api/convert は text を必須とするため最小入力で検証する
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok() -> None:
    """/health が ok を返すことを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        client:
            FastAPIのテストクライアント。
        response:
            /health のレスポンス。

    Raises:
        AssertionError: レスポンスが期待値と異なる場合に発生
    """
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == "ok"


def test_convert_returns_definition() -> None:
    """/api/convert が業務定義を返すことを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        client:
            FastAPIのテストクライアント。
        response:
            /api/convert のレスポンス。
        payload:
            受信したJSONボディ。

    Raises:
        AssertionError: レスポンスが期待値と異なる場合に発生

    Note:
        - text が空の場合は 400 となるため、最小入力で成功を確認する
    """
    client = TestClient(app)
    response = client.post("/api/convert", json={"text": "経費を承認する"})

    assert response.status_code == 200
    payload = response.json()

    assert "definition" in payload
    assert "agent_logs" in payload
    assert "meta" in payload
