# フロント仕様（LIFF最小構成）

## 目的
- LIFF上で動作する1画面UIを提供し、`/api/convert` へ POST する。
- `definition` / `agent_logs` / `meta` をJSONで表示する。
- LIFFの実行状態（LINE内/OS/言語/コンテキスト/ログイン/IDトークン可否）を表示する。

## 画面仕様
- 1画面構成（入力 → 実行 → 結果表示）。
- 初期サンプル文章を入力欄にセットする。
- 実行状態はテキストで表示（待機 / 処理中 / 成功 / 失敗 / 設定不足 / 入力不足）。
- エラーメッセージは次のアクションが分かる内容にする。
- `definition` と `meta` を優先表示し、`agent_logs` は折りたたみ表示とする。
- JSONは整形（pretty print）して表示する。
- コンテキストは `type / viewType` を簡易表示する（ユーザー識別子は表示しない）。
- meta には `actions` / `actions_raw` / `actions_filtered_out` / `action_filter_version` /
  `action_filter_fallback` / `entities` / `role_inference` / `splitter_version` /
  `compound_detected` / `validator_issues` を含める。

## 設定注入
- `public/config.js` は起動時に `public/config.js.template` から生成する。
- `window.__CONFIG__` に以下を注入する。
  - `LIFF_ID`
  - `BACKEND_BASE_URL`
- HTML/JS へ直書きしない。
- `config.js` は `no-store` で配信する（Nginx設定）。
- 設定が空の場合は「LIFF_ID is not set」「BACKEND_BASE_URL is not set」を表示し、実行を停止する。

## 通信仕様
- `POST /api/convert`
- `BACKEND_BASE_URL` の末尾スラッシュは除去して使用する。
- fetch 失敗時は CORS / URL / ネットワークを疑う旨を表示する。

## LIFF動作
- `liff.init` 失敗時は Endpoint URL / HTTPS / LIFF_ID を確認する旨を表示する。
- ログインは自動で行わず、必要時のみ手動ログインボタンを提供する。
- `openid` スコープがある場合のみ `liff.getIDToken()` を取得し、`Authorization: Bearer` に付与する。
- トークン生値は画面表示・保存・ログ出力をしない。

## 制約
- LIFFはHTTPS必須。
- Endpoint URLはフロントURLと同一、または配下であること。
- 署名検証（JWKS）や認可は未実装。

## Cloud Run 実行
- 環境変数:
  - `LIFF_ID`
  - `BACKEND_BASE_URL`
  - `PORT`（未指定時は `8080`）
- Nginxは `$PORT` で待ち受ける。
