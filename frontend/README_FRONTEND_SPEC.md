# フロント仕様（LIFF最小構成）

## 目的
- LIFF上で動作する1画面UIを提供し、`/api/convert`へPOSTする。
- `definition` / `agent_logs` / `meta` をJSONで表示する。
- LIFFの実行状態（LINE内/OS/言語/IDトークン有無）を表示する。

## 画面仕様
- 業務文章入力（`textarea`）
- 変換ボタン
- 変換結果のJSON表示（3カラム）
- LIFF状態カード

## 設定注入
- `public/config.js` は起動時に `public/config.js.template` から生成する。
- `window.__CONFIG__` に以下を注入する。
  - `LIFF_ID`
  - `BACKEND_BASE_URL`
- HTML/JSへ直書きしない。

## 制約
- LIFFはHTTPS必須。
- Endpoint URLはフロントURLと同一、または配下であること。
- IDトークンが取得できる場合のみ `Authorization: Bearer <token>` を送信する。
- トークンはログ/保存しない。

## Cloud Run 実行
- 環境変数:
  - `LIFF_ID`
  - `BACKEND_BASE_URL`
  - `PORT`（未指定時は `8080`）
- Nginxは `$PORT` で待ち受ける。
