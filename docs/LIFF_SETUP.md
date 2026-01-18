# LIFF 登録・設定手順

## 1) 目的
- Cloud Runで配信したフロントをLINE内で表示する。

## 2) 前提条件
- HTTPSが必須。
- Endpoint URLはフロントURLと同一、または配下であること。
- 設定例は `<frontend-url>` のようにプレースホルダで記載する。

## 3) LINE Developers Console 手順
1. Providerを作成または選択する。
2. LINE Login チャネルを作成する。
3. LIFFアプリを追加する。
4. Endpoint URL を `<frontend-url>` に設定する。
5. Scope を設定する。
   - IDトークンを使う場合は `openid` を付与する。
6. 保存し、LIFF ID を `<liff-id>` として控える。

## 4) 動作確認
- LINE内でLIFF URLを開き、画面が表示されることを確認する。
- ステータスに `IDトークン: あり` が表示されることを確認する。
- 変換を実行し、JSONレスポンスが表示されることを確認する。

## 5) よくあるエラーと対処
- `liff.init` 失敗:
  - LIFF ID と Endpoint URL を確認する。
  - HTTPSで配信されているか確認する。
- CORS エラー:
  - `CORS_ALLOW_ORIGINS` にフロントのオリジンを設定する。
  - デモ用途は `*` を許容する。
- IDトークンが取れない:
  - `openid` スコープが有効か確認する。
  - LINE内でログイン済みか確認する。

## 6) セキュリティ補足
- 署名検証（JWKS）や認可は未実装。
- 将来的に検証を追加する想定。
