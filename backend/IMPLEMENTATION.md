# 実装内容まとめ（backend-mvp）

## 目的

- FastAPI + Docker で外部から叩ける最小APIを提供する
- agentic-core（`backend/app/agent`）は原則変更せずに利用する

## 追加・更新した主な構成

### APIエントリポイント

- `backend/app/main.py`
  - FastAPIアプリ生成
  - `GET /health` を追加
  - `/api` ルータを include
  - CORS を開発用途で許可

### 変換API

- `backend/app/api/convert.py`
  - `POST /api/convert` を実装
  - 入力: `{ "text": "...", "context": {...} }`（context は任意）
  - `Orchestrator().convert(text)` を呼び出し
  - 出力: `{ definition, agent_logs, meta }`
  - エラー: 400 / 422 / 500 を整理して返す

### ルータパッケージ

- `backend/app/api/__init__.py`
  - APIルータのパッケージ化のみ

## Docker/環境変数

- `backend/Dockerfile`
  - `python:3.11-slim` ベース
  - `requirements.txt` をインストール
  - `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}` で起動

- `backend/.env.example`
  - `GEMINI_API_KEY=`
  - `CORS_ALLOW_ORIGINS=*`
  - `LOG_LEVEL=INFO`

## 依存関係

- `backend/requirements.txt`
  - `fastapi`
  - `uvicorn[standard]`
  - `python-dotenv`
  - `pydantic>=2`

## テスト（任意）

- `backend/tests/test_api.py`
  - `GET /health` と `POST /api/convert` の最小確認

## 動作確認コマンド（例）

```sh
cd backend
docker build -t agentic-bizflow-backend .
docker run --rm -p 8080:8080 -e PORT=8080 agentic-bizflow-backend
curl http://localhost:8080/health
curl -X POST http://localhost:8080/api/convert \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"経費を承認する\"}"
```
