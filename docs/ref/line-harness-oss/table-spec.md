# テーブル仕様

## 共通仕様

- **ID**: すべて `TEXT PRIMARY KEY`。アプリケーションコードで `crypto.randomUUID()` を使用
- **タイムスタンプ**: `TEXT` 型、JST で記録 — `strftime('%Y-%m-%dT%H:%M:%f', 'now', '+9 hours')`
- **真偽値**: `INTEGER`（0 = false, 1 = true）
- **JSON**: `TEXT` 型で JSON 文字列を格納（metadata, conditions, actions 等）
- **外部キー**: `ON DELETE CASCADE` または `ON DELETE SET NULL` を適切に設定

---

## CRM コア

### friends（友だち）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| line_user_id | TEXT | UNIQUE NOT NULL | LINE ユーザー ID |
| display_name | TEXT | | LINE 表示名 |
| picture_url | TEXT | | プロフィール画像 URL |
| status_message | TEXT | | ステータスメッセージ |
| is_following | INTEGER | NOT NULL DEFAULT 1 | フォロー中か |
| user_id | TEXT | | 内部 UUID（クロスアカウント紐付け） |
| score | INTEGER | NOT NULL DEFAULT 0 | リードスコア合計 |
| created_at | TEXT | NOT NULL | 初回登録日時 (JST) |
| updated_at | TEXT | NOT NULL | 最終更新日時 (JST) |

**インデックス**: `line_user_id`, `user_id`

> **備考**: `metadata` カラム（JSON TEXT）がアプリコード上で使用されている。`preferred_hour`, `ref_code` 等を格納。`line_account_id` カラムでマルチアカウント紐付け。

### tags（タグ）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | UNIQUE NOT NULL | タグ名 |
| color | TEXT | NOT NULL DEFAULT '#3B82F6' | 表示色 (HEX) |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |

### friend_tags（友だち × タグ 中間テーブル）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| friend_id | TEXT | PK, FK → friends | 友だち ID |
| tag_id | TEXT | PK, FK → tags | タグ ID |
| assigned_at | TEXT | NOT NULL | 付与日時 (JST) |

**インデックス**: `tag_id`

---

## シナリオ（ステップ配信）

### scenarios（シナリオ定義）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | シナリオ名 |
| description | TEXT | | 説明 |
| trigger_type | TEXT | NOT NULL, CHECK | `friend_add` / `tag_added` / `manual` |
| trigger_tag_id | TEXT | FK → tags, ON DELETE SET NULL | tag_added 時のトリガータグ |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

### scenario_steps（シナリオステップ）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| scenario_id | TEXT | FK → scenarios | 所属シナリオ |
| step_order | INTEGER | NOT NULL, UNIQUE(scenario_id, step_order) | ステップ順序 |
| delay_minutes | INTEGER | NOT NULL DEFAULT 0 | 前ステップからの遅延 (分) |
| message_type | TEXT | NOT NULL, CHECK | `text` / `image` / `flex` |
| message_content | TEXT | NOT NULL | メッセージ本文 / JSON |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |

**インデックス**: `scenario_id`

> **備考**: アプリコードでは `condition_type` (`tag_exists`, `tag_not_exists`, `metadata_equals`, `metadata_not_equals`) と `condition_value`, `next_step_on_false` カラムが条件分岐に使用される。

### friend_scenarios（友だちシナリオ登録）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| friend_id | TEXT | FK → friends | 友だち ID |
| scenario_id | TEXT | FK → scenarios | シナリオ ID |
| current_step_order | INTEGER | NOT NULL DEFAULT 0 | 現在のステップ位置 |
| status | TEXT | NOT NULL, CHECK, DEFAULT 'active' | `active` / `paused` / `completed` |
| started_at | TEXT | NOT NULL | 登録日時 (JST) |
| next_delivery_at | TEXT | | 次回配信予定日時 |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

**インデックス**: `next_delivery_at`, `status`, `friend_id`

---

## 配信

### broadcasts（ブロードキャスト）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| title | TEXT | NOT NULL | 配信タイトル |
| message_type | TEXT | NOT NULL, CHECK | `text` / `image` / `flex` |
| message_content | TEXT | NOT NULL | メッセージ本文 / JSON |
| target_type | TEXT | NOT NULL, CHECK, DEFAULT 'all' | `all` / `tag` |
| target_tag_id | TEXT | FK → tags, ON DELETE SET NULL | タグ絞り込み時のタグ ID |
| status | TEXT | NOT NULL, CHECK, DEFAULT 'draft' | `draft` / `scheduled` / `sending` / `sent` |
| scheduled_at | TEXT | | 予約配信日時 |
| sent_at | TEXT | | 送信完了日時 |
| total_count | INTEGER | NOT NULL DEFAULT 0 | 対象者数 |
| success_count | INTEGER | NOT NULL DEFAULT 0 | 送信成功数 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |

**インデックス**: `status`

### messages_log（メッセージログ）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| friend_id | TEXT | FK → friends | 友だち ID |
| direction | TEXT | NOT NULL, CHECK | `incoming` / `outgoing` |
| message_type | TEXT | NOT NULL | メッセージ種別 |
| content | TEXT | NOT NULL | メッセージ内容 |
| broadcast_id | TEXT | FK → broadcasts, ON DELETE SET NULL | ブロードキャスト経由の場合 |
| scenario_step_id | TEXT | FK → scenario_steps, ON DELETE SET NULL | ステップ配信経由の場合 |
| created_at | TEXT | NOT NULL | 記録日時 (JST) |

**インデックス**: `friend_id`, `created_at`

### auto_replies（自動返信）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| keyword | TEXT | NOT NULL | キーワード |
| match_type | TEXT | NOT NULL, CHECK, DEFAULT 'exact' | `exact` / `contains` |
| response_type | TEXT | NOT NULL DEFAULT 'text' | 応答メッセージ種別 |
| response_content | TEXT | NOT NULL | 応答内容 |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |

### templates（テンプレート）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | テンプレート名 |
| category | TEXT | NOT NULL DEFAULT 'general' | カテゴリ |
| message_type | TEXT | NOT NULL, CHECK | `text` / `image` / `flex` / `carousel` |
| message_content | TEXT | NOT NULL | テンプレート本文 / JSON |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

**インデックス**: `category`

---

## リマインダ

### reminders（リマインダ定義）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | リマインダ名 |
| description | TEXT | | 説明 |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

### reminder_steps（リマインダステップ）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| reminder_id | TEXT | FK → reminders | リマインダ ID |
| offset_minutes | INTEGER | NOT NULL | 基準日からのオフセット（負=前、正=後） |
| message_type | TEXT | NOT NULL, CHECK | `text` / `image` / `flex` |
| message_content | TEXT | NOT NULL | メッセージ内容 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |

**インデックス**: `reminder_id`

### friend_reminders（友だちリマインダ登録）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| friend_id | TEXT | FK → friends | 友だち ID |
| reminder_id | TEXT | FK → reminders | リマインダ ID |
| target_date | TEXT | NOT NULL | 基準日（例: セミナー日） |
| status | TEXT | NOT NULL, CHECK, DEFAULT 'active' | `active` / `completed` / `cancelled` |
| created_at | TEXT | NOT NULL | 登録日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

**インデックス**: `status`, `friend_id`

### friend_reminder_deliveries（配信済み記録）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| friend_reminder_id | TEXT | FK → friend_reminders | 友だちリマインダ ID |
| reminder_step_id | TEXT | FK → reminder_steps | ステップ ID |
| delivered_at | TEXT | NOT NULL | 配信日時 (JST) |

**UNIQUE**: `(friend_reminder_id, reminder_step_id)`

---

## スコアリング

### scoring_rules（スコアリングルール）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | ルール名 |
| event_type | TEXT | NOT NULL | 対象イベント種別 |
| score_value | INTEGER | NOT NULL | 加算スコア値 |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

### friend_scores（スコア履歴）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| friend_id | TEXT | FK → friends | 友だち ID |
| scoring_rule_id | TEXT | FK → scoring_rules, ON DELETE SET NULL | ルール ID |
| score_change | INTEGER | NOT NULL | スコア変動値 |
| reason | TEXT | | 変動理由 |
| created_at | TEXT | NOT NULL | 記録日時 (JST) |

**インデックス**: `friend_id`, `created_at`

---

## 自動化

### automations（IF-THEN ルール）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | ルール名 |
| description | TEXT | | 説明 |
| event_type | TEXT | NOT NULL | トリガーイベント |
| conditions | TEXT | NOT NULL DEFAULT '{}' | 条件 (JSON) |
| actions | TEXT | NOT NULL DEFAULT '[]' | アクション配列 (JSON) |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| priority | INTEGER | NOT NULL DEFAULT 0 | 実行優先度 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

**インデックス**: `event_type`, `is_active`

**conditions JSON 例**:
```json
{ "score_threshold": 100, "tag_id": "uuid-xxx" }
```

**actions JSON 例**:
```json
[
  { "type": "add_tag", "params": { "tagId": "uuid-xxx" } },
  { "type": "send_message", "params": { "content": "Hello!", "messageType": "text" } }
]
```

**アクション種別**: `add_tag`, `remove_tag`, `start_scenario`, `send_message`, `send_webhook`, `switch_rich_menu`, `remove_rich_menu`, `set_metadata`

### automation_logs（自動化実行ログ）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| automation_id | TEXT | FK → automations | ルール ID |
| friend_id | TEXT | FK → friends, ON DELETE SET NULL | 対象友だち |
| event_data | TEXT | | イベントデータ (JSON) |
| actions_result | TEXT | | 実行結果 (JSON) |
| status | TEXT | NOT NULL, CHECK, DEFAULT 'success' | `success` / `partial` / `failed` |
| created_at | TEXT | NOT NULL | 実行日時 (JST) |

**インデックス**: `automation_id`

---

## チャット

### operators（オペレーター）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | オペレーター名 |
| email | TEXT | UNIQUE NOT NULL | メールアドレス |
| role | TEXT | NOT NULL, CHECK, DEFAULT 'operator' | `admin` / `operator` |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

### chats（チャットセッション）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| friend_id | TEXT | FK → friends | 友だち ID |
| operator_id | TEXT | FK → operators, ON DELETE SET NULL | 担当オペレーター |
| status | TEXT | NOT NULL, CHECK, DEFAULT 'unread' | `unread` / `in_progress` / `resolved` |
| notes | TEXT | | メモ |
| last_message_at | TEXT | | 最終メッセージ日時 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

**インデックス**: `friend_id`, `operator_id`, `status`

---

## 通知

### notification_rules（通知ルール）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | ルール名 |
| event_type | TEXT | NOT NULL | 対象イベント |
| conditions | TEXT | NOT NULL DEFAULT '{}' | 条件 (JSON) |
| channels | TEXT | NOT NULL DEFAULT '["webhook"]' | 通知チャネル (JSON 配列) |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

### notifications（通知レコード）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| rule_id | TEXT | FK → notification_rules, ON DELETE SET NULL | ルール ID |
| event_type | TEXT | NOT NULL | イベント種別 |
| title | TEXT | NOT NULL | 通知タイトル |
| body | TEXT | NOT NULL | 通知本文 |
| channel | TEXT | NOT NULL | 通知チャネル |
| status | TEXT | NOT NULL, CHECK, DEFAULT 'pending' | `pending` / `sent` / `failed` |
| metadata | TEXT | | メタデータ (JSON) |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |

**インデックス**: `status`, `created_at`

---

## Webhook IN/OUT

### incoming_webhooks（受信 Webhook）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | Webhook 名 |
| source_type | TEXT | NOT NULL DEFAULT 'custom' | ソース種別 |
| secret | TEXT | | 検証用シークレット |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

### outgoing_webhooks（送信 Webhook）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | Webhook 名 |
| url | TEXT | NOT NULL | 送信先 URL |
| event_types | TEXT | NOT NULL DEFAULT '[]' | 対象イベント (JSON 配列) |
| secret | TEXT | | HMAC 署名用シークレット |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

---

## 外部連携

### google_calendar_connections（Google Calendar 接続）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| calendar_id | TEXT | NOT NULL | Google Calendar ID |
| access_token | TEXT | | OAuth アクセストークン |
| refresh_token | TEXT | | OAuth リフレッシュトークン |
| api_key | TEXT | | API キー |
| auth_type | TEXT | NOT NULL DEFAULT 'api_key' | 認証方式 |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

### calendar_bookings（予約）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| connection_id | TEXT | FK → google_calendar_connections | カレンダー接続 ID |
| friend_id | TEXT | FK → friends, ON DELETE SET NULL | 予約した友だち |
| event_id | TEXT | | Google Calendar イベント ID |
| title | TEXT | NOT NULL | 予約タイトル |
| start_at | TEXT | NOT NULL | 開始日時 |
| end_at | TEXT | NOT NULL | 終了日時 |
| status | TEXT | NOT NULL, CHECK, DEFAULT 'confirmed' | `confirmed` / `cancelled` / `completed` |
| metadata | TEXT | | メタデータ (JSON) |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

**インデックス**: `friend_id`, `start_at`

### stripe_events（Stripe イベント）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| stripe_event_id | TEXT | UNIQUE NOT NULL | Stripe イベント ID |
| event_type | TEXT | NOT NULL | イベント種別 |
| friend_id | TEXT | FK → friends, ON DELETE SET NULL | 紐付け友だち |
| amount | REAL | | 金額 |
| currency | TEXT | | 通貨 |
| metadata | TEXT | | メタデータ (JSON) |
| processed_at | TEXT | NOT NULL | 処理日時 (JST) |

**インデックス**: `friend_id`, `event_type`

---

## CV・アフィリエイト

### conversion_points（コンバージョンポイント）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | CV ポイント名 |
| event_type | TEXT | NOT NULL | イベント種別 |
| value | REAL | | CV 値 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |

### conversion_events（CV イベント）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| conversion_point_id | TEXT | FK → conversion_points | CV ポイント ID |
| friend_id | TEXT | FK → friends | 友だち ID |
| user_id | TEXT | | 内部 UUID |
| affiliate_code | TEXT | | アフィリエイトコード |
| metadata | TEXT | | メタデータ (JSON) |
| created_at | TEXT | NOT NULL | 記録日時 (JST) |

**インデックス**: `conversion_point_id`, `friend_id`, `affiliate_code`

### affiliates（アフィリエイト）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| name | TEXT | NOT NULL | アフィリエイト名 |
| code | TEXT | UNIQUE NOT NULL | アフィリエイトコード |
| commission_rate | REAL | NOT NULL DEFAULT 0 | 報酬率 |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |

### affiliate_clicks（クリック記録）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| affiliate_id | TEXT | FK → affiliates | アフィリエイト ID |
| url | TEXT | | クリック URL |
| ip_address | TEXT | | IP アドレス |
| created_at | TEXT | NOT NULL | クリック日時 (JST) |

**インデックス**: `affiliate_id`

---

## アカウント管理

### admin_users（管理ユーザー）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| email | TEXT | UNIQUE NOT NULL | メールアドレス |
| password_hash | TEXT | NOT NULL | パスワードハッシュ |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |

### users（内部 UUID ユーザー）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| email | TEXT | | メールアドレス |
| phone | TEXT | | 電話番号 |
| external_id | TEXT | | 外部システム ID |
| display_name | TEXT | | 表示名 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

**インデックス**: `email`, `phone`, `external_id`

### line_accounts（LINE アカウント）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| channel_id | TEXT | UNIQUE NOT NULL | LINE チャネル ID |
| name | TEXT | NOT NULL | アカウント名 |
| channel_access_token | TEXT | NOT NULL | チャネルアクセストークン |
| channel_secret | TEXT | NOT NULL | チャネルシークレット |
| is_active | INTEGER | NOT NULL DEFAULT 1 | 有効/無効 |
| created_at | TEXT | NOT NULL | 作成日時 (JST) |
| updated_at | TEXT | NOT NULL | 更新日時 (JST) |

---

## BAN 検知・リカバリ

### account_health_logs（ヘルスログ）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| line_account_id | TEXT | NOT NULL | LINE アカウント ID |
| error_code | INTEGER | | HTTP エラーコード |
| error_count | INTEGER | NOT NULL DEFAULT 0 | エラー回数 |
| check_period | TEXT | NOT NULL | チェック期間 |
| risk_level | TEXT | NOT NULL, CHECK, DEFAULT 'normal' | `normal` / `warning` / `danger` |
| created_at | TEXT | NOT NULL | 記録日時 (JST) |

**インデックス**: `line_account_id`

### account_migrations（アカウント移行）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | TEXT | PK | UUID |
| from_account_id | TEXT | NOT NULL | 移行元アカウント ID |
| to_account_id | TEXT | NOT NULL | 移行先アカウント ID |
| status | TEXT | NOT NULL, CHECK, DEFAULT 'pending' | `pending` / `in_progress` / `completed` / `failed` |
| migrated_count | INTEGER | NOT NULL DEFAULT 0 | 移行済み件数 |
| total_count | INTEGER | NOT NULL DEFAULT 0 | 総件数 |
| created_at | TEXT | NOT NULL | 開始日時 (JST) |
| completed_at | TEXT | | 完了日時 |
