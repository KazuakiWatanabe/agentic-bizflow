"""
既存 /api/convert エンドポイントの回帰テスト。

本モジュールは Phase 2.5 の新機能追加によって
既存の /api/convert が壊れていないことを確認する。

入出力: TestClient で /api/convert を呼び出す。
制約: 外部 LLM は使わない。

Note:
    - 回帰テストのため、最優先で実行する
    - 既存テスト（test_api.py）の補完として、追加のパターンを検証する
"""

from fastapi.testclient import TestClient

from app.main import app

# テストクライアント
client = TestClient(app)


def test_convert_正常系_最小入力で業務定義が返る() -> None:
    """最小の入力テキストで /api/convert が正常応答を返すことを確認する。

    Variables:
        response:
            /api/convert のレスポンス。
        payload:
            受信した JSON ボディ。
    """
    response = client.post("/api/convert", json={"text": "経費を承認する"})
    assert response.status_code == 200

    payload = response.json()
    assert "definition" in payload
    assert "agent_logs" in payload
    assert "meta" in payload


def test_convert_正常系_レスポンスにtasksとrolesが含まれる() -> None:
    """レスポンスの definition に tasks と roles が含まれることを確認する。

    Variables:
        response:
            /api/convert のレスポンス。
        definition:
            レスポンス内の業務定義 dict。
    """
    response = client.post(
        "/api/convert",
        json={"text": "申請者が申請書を提出し、上長が確認する。"},
    )
    assert response.status_code == 200

    definition = response.json()["definition"]
    assert "tasks" in definition
    assert "roles" in definition


def test_convert_異常系_空テキストで400が返る() -> None:
    """text が空の場合に 400 エラーが返ることを確認する。

    Variables:
        response:
            /api/convert のレスポンス。
    """
    response = client.post("/api/convert", json={"text": ""})
    assert response.status_code == 400


def test_convert_異常系_textなしで400が返る() -> None:
    """text フィールドがない場合に 400 エラーが返ることを確認する。

    Variables:
        response:
            /api/convert のレスポンス。
    """
    response = client.post("/api/convert", json={})
    assert response.status_code == 400


def test_health_エンドポイントが正常動作する() -> None:
    """/health が "ok" を返すことを確認する。

    Variables:
        response:
            /health のレスポンス。
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == "ok"
