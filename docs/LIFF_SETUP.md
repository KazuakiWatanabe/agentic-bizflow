# LIFF 登録・設定手順

## 1) 目的
- Cloud Runで配信したフロントをLINE内で表示する。
- LIFF最小フロントの動作確認を行う。

## 2) 前提条件
- HTTPSが必須。
- Endpoint URLはフロントURLと同一、または配下であること。
- 設定例は `<frontend-url>` / `<backend-url>` / `<liff-id>` のようにプレースホルダで記載する。
- フロントは `config.js` で設定注入する（HTML/JSに直書きしない）。
- ログインは自動で行わない（必要に応じて手動ログインボタンを使用する）。

## 2.5) 必要な値（プレースホルダ）
- `<frontend-url>`: Cloud Run 等で公開したフロントURL（例: `https://<your-frontend>`）
- `<backend-url>`: `/api/convert` を提供するバックエンドURL（例: `https://<your-backend>`）
- `<liff-id>`: LINE Developers Console で発行される LIFF ID

## 3) LINE Developers Console 手順
1. Providerを作成または選択する。
2. LINE Login チャネルを作成する。
3. LIFFアプリを追加する（LINE Login チャネル内の LIFF タブ）。
4. Endpoint URL を `<frontend-url>` に設定する。
5. Scope を設定する。
   - IDトークンを使う場合は `openid` を付与する。
6. 保存し、LIFF ID を `<liff-id>` として控える。

## 3.5) フロントの環境変数設定（Cloud Run 例）
- フロントサービスに `LIFF_ID` と `BACKEND_BASE_URL` を設定する。
- 例（プレースホルダのみ）:

```sh
gcloud run services update <frontend-service> \
  --region=<region> \
  --set-env-vars "LIFF_ID=<liff-id>,BACKEND_BASE_URL=<backend-url>"
```

## 4) 動作確認
- LINE内でLIFF URLを開き、画面が表示されることを確認する。
- `設定` が「設定済み」になっていることを確認する。
- `IDトークン` が `scopeなし` / `あり` など、現在の状態に応じて表示されることを確認する。
- サンプル文章のまま変換を実行し、JSONレスポンスが表示されることを確認する。

## 5) よくあるエラーと対処
- `LIFF_ID is not set` / `BACKEND_BASE_URL is not set`:
  - `config.js` に値が注入されているか確認する。
- `LIFF init に失敗しました`:
  - Endpoint URL / HTTPS / LIFF ID を確認する。
- `通信に失敗しました`:
  - CORS / URL / ネットワークを確認する。
- `IDトークン: scopeなし`:
  - `openid` スコープが有効か、ログイン済みか確認する。

## 6) セキュリティ補足
- 署名検証（JWKS）や認可は未実装。
- トークンの生値は表示・保存しない。
