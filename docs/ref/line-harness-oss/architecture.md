# アーキテクチャ

## 全体構成

```
                          ┌─────────────────────┐
                          │   LINE Platform      │
                          │  (Messaging API)     │
                          └──────┬──────▲────────┘
                                 │      │
                          Webhook│      │pushMessage
                          (POST) │      │replyMessage
                                 │      │multicast
                                 ▼      │broadcast
┌──────────────────────────────────────────────────────────────┐
│                 Cloudflare Workers (Hono)                     │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │  Webhook     │  │  REST API    │  │  Cron Scheduler     │ │
│  │  Handler     │  │  (25 routes) │  │  (*/5 * * * *)      │ │
│  │              │  │              │  │                     │ │
│  │ ・署名検証    │  │ ・Bearer認証  │  │ ・ステップ配信       │ │
│  │ ・マルチ      │  │ ・CRUD全般   │  │ ・予約ブロードキャスト│ │
│  │  アカウント   │  │ ・セグメント  │  │ ・リマインダ配信     │ │
│  │  ルーティング │  │  配信        │  │ ・BAN検知           │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘ │
│         │                │                      │            │
│         ▼                ▼                      ▼            │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                   Event Bus                          │    │
│  │                                                      │    │
│  │  イベント発火時に並列実行:                              │    │
│  │  1. Outgoing Webhook 通知                            │    │
│  │  2. スコアリングルール適用                              │    │
│  │  3. 自動化ルール (IF-THEN) 実行                       │    │
│  │  4. 通知ルール処理                                    │    │
│  └──────────────────────────────────────────────────────┘    │
│                          │                                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                 Stealth Engine                        │    │
│  │                                                      │    │
│  │  ・配信ジッター (±5分)                                │    │
│  │  ・バッチ間ランダム遅延                                │    │
│  │  ・メッセージ微小変異 (zero-width chars)                │    │
│  │  ・配信時間帯制御 (9:00-23:00 JST)                    │    │
│  │  ・レートリミッター (1000 calls/min)                   │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
               ┌────────────────────┐
               │  Cloudflare D1     │
               │  (SQLite)          │
               │                    │
               │  42 テーブル        │
               │  JST タイムスタンプ  │
               │  TEXT UUID PK      │
               └────────────────────┘
                          ▲
          ┌───────────────┼───────────────┐
          │               │               │
┌─────────┴──┐  ┌────────┴───┐  ┌────────┴───┐
│ Next.js 15 │  │ LIFF App   │  │ SDK        │
│ 管理画面    │  │ (Vite)     │  │ (npm)      │
│ :3001      │  │ :3002      │  │            │
│            │  │            │  │            │
│ App Router │  │ フォーム    │  │ ESM + CJS  │
│ Tailwind 4 │  │ カレンダー  │  │ 41 tests   │
│ Static     │  │ 予約       │  │            │
│ Export     │  │            │  │            │
└────────────┘  └────────────┘  └────────────┘
```

## レイヤー構成

### 1. プレゼンテーション層

| アプリ | 技術 | 役割 |
|--------|------|------|
| **apps/web** | Next.js 15 (App Router) + Tailwind CSS v4 | 管理画面ダッシュボード。Static export でデプロイ |
| **apps/liff** | Vite + TypeScript | LINE 内ミニアプリ（フォーム・カレンダー予約） |
| **packages/sdk** | TypeScript (tsup) | プログラマティックアクセス用 SDK |

### 2. API / ビジネスロジック層

**apps/worker** — Cloudflare Workers + Hono

```
apps/worker/src/
├── index.ts              # エントリーポイント（ルートマウント + Cron ハンドラ）
├── middleware/
│   └── auth.ts           # Bearer トークン認証（/webhook, /docs 等はスキップ）
├── routes/               # 24 ルートファイル（リソースごとに 1 ファイル）
│   ├── webhook.ts        # LINE Webhook 受信・イベント処理
│   ├── friends.ts        # 友だち CRUD
│   ├── tags.ts           # タグ CRUD
│   ├── scenarios.ts      # シナリオ（ステップ配信）CRUD
│   ├── broadcasts.ts     # ブロードキャスト CRUD + 即時送信
│   ├── automations.ts    # IF-THEN 自動化ルール
│   ├── scoring.ts        # スコアリングルール
│   ├── chats.ts          # オペレーターチャット
│   ├── rich-menus.ts     # リッチメニュー管理
│   ├── tracked-links.ts  # トラッキングリンク
│   ├── forms.ts          # フォーム定義・回答
│   ├── reminders.ts      # リマインダ配信
│   ├── templates.ts      # メッセージテンプレート
│   ├── notifications.ts  # 通知ルール
│   ├── webhooks.ts       # Webhook IN/OUT 管理
│   ├── calendar.ts       # Google Calendar 連携
│   ├── stripe.ts         # Stripe 決済 Webhook
│   ├── health.ts         # アカウントヘルス
│   ├── line-accounts.ts  # マルチアカウント管理
│   ├── users.ts          # 内部 UUID ユーザー
│   ├── conversions.ts    # CV トラッキング
│   ├── affiliates.ts     # アフィリエイト
│   ├── liff.ts           # LIFF 関連エンドポイント
│   └── openapi.ts        # OpenAPI ドキュメント
└── services/             # バックグラウンド処理・ビジネスロジック
    ├── step-delivery.ts  # ステップ配信（テンプレート変数展開・条件分岐含む）
    ├── broadcast.ts      # ブロードキャスト送信（バッチ処理）
    ├── reminder-delivery.ts  # リマインダ配信
    ├── event-bus.ts      # イベントバス（Webhook・スコアリング・自動化・通知の統合）
    ├── segment-query.ts  # セグメントクエリビルダー (AND/OR 条件)
    ├── segment-send.ts   # セグメント配信実行
    ├── stealth.ts        # ステルス配信エンジン
    ├── ban-monitor.ts    # BAN 検知モニター
    └── google-calendar.ts # Google Calendar API 連携
```

### 3. データアクセス層

**packages/db** — D1 クエリヘルパー

```
packages/db/src/
├── index.ts          # 全モジュールの re-export
├── utils.ts          # jstNow(), toJstString() タイムゾーンユーティリティ
├── friends.ts        # friends テーブル CRUD
├── tags.ts           # tags, friend_tags CRUD
├── scenarios.ts      # scenarios, scenario_steps, friend_scenarios CRUD
├── broadcasts.ts     # broadcasts CRUD
├── automations.ts    # automations, automation_logs CRUD
├── scoring.ts        # scoring_rules, friend_scores CRUD
├── chats.ts          # chats, operators CRUD
├── templates.ts      # templates CRUD
├── reminders.ts      # reminders, reminder_steps, friend_reminders CRUD
├── notifications.ts  # notification_rules, notifications CRUD
├── webhooks.ts       # incoming/outgoing_webhooks CRUD
├── forms.ts          # forms, form_submissions CRUD
├── tracked-links.ts  # tracked_links, link_clicks CRUD
├── health.ts         # account_health_logs CRUD
├── line-accounts.ts  # line_accounts CRUD
├── users.ts          # users CRUD
├── conversions.ts    # conversion_points, conversion_events CRUD
├── affiliates.ts     # affiliates, affiliate_clicks CRUD
├── calendar.ts       # google_calendar_connections, calendar_bookings CRUD
├── stripe.ts         # stripe_events CRUD
└── entry-routes.ts   # 流入元追跡
```

### 4. 外部サービス連携

| サービス | 連携方法 | 用途 |
|----------|---------|------|
| **LINE Messaging API** | packages/line-sdk (LineClient) | メッセージ送信・プロフィール取得・リッチメニュー |
| **LINE Login** | OAuth + LIFF ID Token | UUID フェデレーション・ユーザー認証 |
| **Google Calendar** | API Key / OAuth | カレンダー予約 |
| **Stripe** | Webhook | 決済イベント連携 |
| **外部 Webhook** | HTTP POST + HMAC 署名 | イベント通知 |

## 認証フロー

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│ LINE Platform│     │  External Client  │     │  LIFF App    │
└──────┬───────┘     └────────┬─────────┘     └──────┬───────┘
       │                      │                       │
       │ POST /webhook        │ GET/POST /api/*       │ POST /api/liff/*
       │ X-Line-Signature     │ Authorization:        │ (認証不要)
       │                      │   Bearer <API_KEY>    │
       ▼                      ▼                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    Auth Middleware                            │
│                                                              │
│  ① /webhook → LINE署名検証（マルチアカウント対応）              │
│  ② /api/* → Bearer トークン (API_KEY) 照合                   │
│  ③ /api/liff/*, /auth/*, form submit → 認証スキップ           │
│  ④ /docs, /openapi.json → 認証スキップ                       │
│  ⑤ /t/*, /r/* → 認証スキップ（トラッキング・短縮リンク）       │
│  ⑥ Stripe webhook, incoming webhook receive → 認証スキップ   │
└──────────────────────────────────────────────────────────────┘
```

## マルチアカウント処理

```
LINE Platform
    │
    │ POST /webhook
    │ destination: "U..." (channel user ID)
    │ X-Line-Signature: "xxx"
    ▼
┌──────────────────────────────┐
│  Webhook Handler             │
│                              │
│  1. body.destination を取得   │
│  2. DB の line_accounts を    │
│     全件取得                  │
│  3. 各アカウントの secret で  │
│     署名検証 → 一致する       │
│     アカウントを特定          │
│  4. フォールバック:           │
│     環境変数のデフォルト      │
│     アカウント                │
└──────────────────────────────┘
```

## Cron スケジューラ

5 分間隔 (`*/5 * * * *`) で以下を全アクティブアカウントに対して実行:

```
Cron Trigger (every 5 min)
    │
    ├── processStepDeliveries()
    │   next_delivery_at ≤ now のエンロールメントを配信
    │   9:00-23:00 JST ウィンドウ外はスキップ
    │
    ├── processScheduledBroadcasts()
    │   status=scheduled, scheduled_at ≤ now のブロードキャストを送信
    │
    ├── processReminderDeliveries()
    │   target_date + offset_minutes ≤ now の未配信リマインダを送信
    │
    └── checkAccountHealth()
        各アカウントの LINE API ヘルスチェック
        403 → danger, 429 → warning
```

## イベントバス

システム内イベントが発生すると `fireEvent()` が並列で 4 つの処理を実行:

```
イベント発火 (friend_add, message_received, tag_added, etc.)
    │
    ├── fireOutgoingWebhooks()     送信 Webhook へ HTTP POST (HMAC 署名付き)
    ├── processScoring()           スコアリングルール適用 → friend.score 更新
    ├── processAutomations()       IF-THEN ルール評価 → アクション実行
    │   アクション種類:
    │   ├── add_tag / remove_tag
    │   ├── start_scenario
    │   ├── send_message (text/flex)
    │   ├── send_webhook
    │   ├── switch_rich_menu / remove_rich_menu
    │   └── set_metadata
    └── processNotifications()     通知ルール → notification レコード作成
```

## ステルス配信エンジン

LINE プラットフォームの BAN 検知を回避するための配信最適化:

| 機能 | 実装 |
|------|------|
| 配信ジッター | 予定時刻に ±5 分のランダム揺れ |
| バッチ間遅延 | 送信数に応じて 100ms〜5分 のスタガード遅延 |
| メッセージ変異 | バッチごとに zero-width 文字を挿入（視覚的に同一） |
| 配信ウィンドウ | 9:00-23:00 JST のみ配信。時間外は翌朝 9:00 に繰り延べ |
| レートリミット | 1000 calls/min の自主制限 |
| ユーザー別時間 | `preferred_hour` メタデータで個別配信開始時刻を設定可能 |
