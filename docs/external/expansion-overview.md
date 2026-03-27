# Agentic BizFlow 拡張性概要

## 現在のプロダクト

Agentic BizFlow は、自然文の日本語業務手順を実行可能な業務定義（JSON）に変換し、
LINE 公式アカウント運用を自動化する Agentic AI プラットフォームです。

現時点では以下の LINE 運用ワークロードに対応しています:

- **タグ付与** (line.tag.assign) — 対象者にタグを付与する
- **一斉配信** (line.broadcast.schedule) — LINE メッセージの一斉配信を予約する
- **シナリオ配信** (line.scenario.create / line.scenario.start) — ステップ配信シナリオの作成・開始
- **リマインダー** (line.reminder.create) — リマインダーの作成・配信

## 内部抽象化: 共通 Kind → ドメイン Kind の二層構造

Phase 7 で導入した Marketing Channel Abstraction により、
ワークロードの定義をチャネル非依存の共通語彙で記述できるようになりました。

### 二層構造の仕組み

```
共通 Kind (channel-agnostic)          ドメイン Kind (channel-specific)
──────────────────────────            ────────────────────────────────
audience.label.assign       ─── LINE ──→  line.tag.assign
                            ─── Email ──→  (未サポート)

campaign.schedule           ─── LINE ──→  line.broadcast.schedule
                            ─── Email ──→  email.broadcast.schedule

journey.create              ─── LINE ──→  line.scenario.create
                            ─── Email ──→  (未サポート)

journey.enroll              ─── LINE ──→  line.scenario.start
                            ─── Email ──→  (未サポート)

followup.create             ─── LINE ──→  line.reminder.create
                            ─── Email ──→  (未サポート)
```

### 解決の流れ

1. 業務定義が共通 kind（例: `campaign.schedule`）で記述される
2. `kind_resolver` が有効なドメイン設定と priority を参照する
3. 共通 kind をドメイン固有 kind（例: `line.broadcast.schedule`）に解決する
4. 解決後の kind に対応する connector が実行を担当する

## コンタクトモデル: チャネル非依存の連絡先管理

`contacts` テーブルがチャネルに依存しない連絡先を管理し、
`contact_channels` テーブルが各チャネル（LINE, Email 等）の外部 ID を紐付けます。

```
contacts                    contact_channels
────────                    ────────────────
id: UUID                    id: UUID
display_name: TEXT          contact_id: FK → contacts
metadata_json: TEXT         channel_type: TEXT (line, email, ...)
created_at                  external_id: TEXT
updated_at                  created_at
                            UNIQUE(channel_type, external_id)
```

これにより、1 人の連絡先に対して複数チャネルの ID を統合管理できます。

## ドメインモジュール構造

各チャネルは独立したドメインモジュールとして `app/domains/` 配下に配置されます:

```
app/domains/
├── __init__.py          # 自動検出・登録
├── common/              # 共通 kind（チャネル非依存）
│   ├── __init__.py      # register() — 共通 kind + resolution 登録
│   └── workload_kinds.py
├── line/                # LINE ドメイン
│   ├── __init__.py      # register() — LINE kind 登録
│   ├── workload_kinds.py
│   └── config.py
├── email/               # Email ドメイン
│   ├── __init__.py      # register() — Email kind 登録
│   ├── workload_kinds.py
│   ├── connector.py
│   └── worker.py
└── _template/           # 新規ドメインのテンプレート
    ├── __init__.py
    ├── workload_kinds.py
    ├── connector.py
    └── worker.py
```

## 拡張可能なサービス例

この抽象化により、以下のようなサービスへの拡張が可能です:

### 店舗アプリ連携
- `audience.label.assign` → 店舗アプリ内のタグ付与
- `campaign.schedule` → プッシュ通知の一斉配信

### 会員アプリ連携
- `journey.create` → 会員ランクアップシナリオ
- `followup.create` → ポイント失効リマインダー

### SMS 配信
- `campaign.schedule` → SMS 一斉配信
- `followup.create` → SMS リマインダー

## 新チャネル追加に必要な作業

新しいチャネル（例: `sms`）を追加するには、以下の 3 つを用意します:

### 1. ドメインモジュールの作成

```
app/domains/sms/
├── __init__.py          # register() — workload kind + connector 登録
├── workload_kinds.py    # SMS 固有の kind 定数
├── connector.py         # SMS API への接続ロジック
└── worker.py            # 非同期実行ワーカー（必要に応じて）
```

### 2. Workload Kind の登録

`__init__.py` の `register()` で SMS 固有の workload kind を登録する:

```python
workload_registry.register(
    kind="sms.broadcast.schedule",
    domain="sms",
    connector="sms",
    requires_approval=ApprovalRule.ALWAYS,
    keywords=["SMS", "ショートメッセージ"],
)
```

### 3. Resolution マッピングの更新

共通 kind の resolution に新ドメインを追加する:

```python
# common/__init__.py の register() に追加
workload_registry.register_resolution(
    "campaign.schedule",
    {"line": "line.broadcast.schedule", "email": "email.broadcast.schedule", "sms": "sms.broadcast.schedule"},
)
```

### 4. ドメイン設定の登録

`domain_configs` テーブルにレコードを追加し、`is_enabled=True` に設定する。

以上の手順で、既存のコードを変更することなく新チャネルを追加できます。
