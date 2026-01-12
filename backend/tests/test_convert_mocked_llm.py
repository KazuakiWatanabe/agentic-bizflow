"""
LLMをモックした決定論テストを提供する。

入出力: TestClientで /api/convert を呼び出す。
制約: 外部APIを呼ばず、モックで完結させる。

Note:
    - llm_generate をモックして外部依存を排除する
"""

from fastapi.testclient import TestClient

from app.main import app

# FastAPIのテストクライアント。
client = TestClient(app)


def test_convert_with_mocked_llm(monkeypatch) -> None:
    """/api/convert が 200 を返すことを確認する（LLMモック）。

    Args:
        monkeypatch: pytest の monkeypatch フィクスチャ

    Returns:
        None

    Variables:
        llm_module:
            llm_generate を提供するモジュール。
        response:
            /api/convert のレスポンス。
        payload:
            受信したJSONボディ。

    Raises:
        AssertionError: レスポンスが期待値と異なる場合に発生

    Note:
        - llm_generate は固定文字列を返すように差し替える
    """
    import app.agent.llm as llm_module

    monkeypatch.setattr(llm_module, "llm_generate", lambda prompt: "OK")

    response = client.post("/api/convert", json={"text": "経費を申請する"})
    payload = response.json()

    assert response.status_code == 200
    assert "definition" in payload
    assert "agent_logs" in payload
    assert "meta" in payload
