# Agentic BizFlow — テーブル仕様書

> 本ドキュメントは全 22 テーブルのカラム定義・制約・インデックスを一覧化したものです。

---

## 実行管理テーブル（Phase 3）

### execution_plans

実行計画の永続化。status は `created → approved → executing → completed / failed` と遷移する。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | plan_id（UUID） |
| source_definition_id | TEXT | NOT NULL | | 元の BusinessDefinition の識別子 |
| source_definition_json | TEXT | NOT NULL | | BusinessDefinition の JSON |
| plan_json | TEXT | NOT NULL | | ExecutionPlan 全体の JSON |
| requires_approval | BOOLEAN | NOT NULL | FALSE | 承認要否 |
| risk_level | TEXT | NOT NULL | 'low' | low / medium / high |
| summary | TEXT | | | 実行計画の要約 |
| status | TEXT | NOT NULL | 'created' | created / approved / executing / completed / failed |
| created_at | DATETIME | NOT NULL | | 作成日時（UTC） |
| updated_at | DATETIME | NOT NULL | | 更新日時（UTC） |

---

### execution_results

実行結果の永続化。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | execution_id（UUID） |
| plan_id | TEXT | FK → execution_plans, NOT NULL | | 実行した plan |
| status | TEXT | NOT NULL | | success / partial_success / failed / blocked |
| started_at | DATETIME | NOT NULL | | 実行開始日時 |
| finished_at | DATETIME | | | 実行完了日時 |
| errors_json | TEXT | NOT NULL | '[]' | エラー一覧（JSON） |
| warnings_json | TEXT | NOT NULL | '[]' | 警告一覧（JSON） |

---

### step_results

ステップごとの実行結果。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| execution_id | TEXT | FK → execution_results, NOT NULL | | 所属する execution |
| step_id | TEXT | NOT NULL | | ExecutionStep の step_id |
| sequence | INTEGER | NOT NULL | | ステップ順序 |
| kind | TEXT | NOT NULL | | workload kind |
| connector | TEXT | NOT NULL | | connector 名 |
| status | TEXT | NOT NULL | | success / failed / blocked / skipped |
| error_code | TEXT | | | エラーコード |
| message | TEXT | | | 結果メッセージ |
| created_at | DATETIME | NOT NULL | | 記録日時 |

---

## LINE ドメインテーブル（Phase 3）

### tags

タグの管理。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| name | TEXT | UNIQUE, NOT NULL | | タグ名 |
| created_at | DATETIME | NOT NULL | | 作成日時 |

---

### tag_assignments

対象者へのタグ付与。複合主キー。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| target_id | TEXT | PK | | 対象者の外部 ID |
| tag_id | TEXT | PK, FK → tags | | タグ ID |
| assigned_at | DATETIME | NOT NULL | | 付与日時 |

---

### scenarios

ステップ配信シナリオ。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| name | TEXT | NOT NULL | | シナリオ名 |
| description | TEXT | | | 説明 |
| trigger_type | TEXT | NOT NULL | 'manual' | manual / tag_added |
| trigger_tag_id | TEXT | FK → tags | | タグトリガー時のタグ ID |
| is_active | BOOLEAN | NOT NULL | TRUE | 有効/無効 |
| execution_plan_id | TEXT | FK → execution_plans | | 生成元の plan |
| created_at | DATETIME | NOT NULL | | 作成日時 |
| updated_at | DATETIME | NOT NULL | | 更新日時 |

---

### scenario_steps

シナリオ内の配信ステップ。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| scenario_id | TEXT | FK → scenarios, NOT NULL | | 所属シナリオ |
| step_order | INTEGER | NOT NULL | | ステップ順序 |
| delay_minutes | INTEGER | NOT NULL | 0 | 前ステップからの遅延（分） |
| message_type | TEXT | NOT NULL | 'text' | text / image / flex |
| message_content | TEXT | NOT NULL | | メッセージ本文 |
| created_at | DATETIME | NOT NULL | | 作成日時 |

**UNIQUE 制約:** `(scenario_id, step_order)` — `uq_scenario_step_order`

---

### scenario_enrollments

対象者のシナリオ登録。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| scenario_id | TEXT | FK → scenarios, NOT NULL | | シナリオ |
| target_id | TEXT | NOT NULL | | 対象者の外部 ID |
| current_step_order | INTEGER | NOT NULL | 0 | 現在のステップ位置 |
| status | TEXT | NOT NULL | 'active' | active / paused / completed / failed |
| next_delivery_at | DATETIME | | | 次回配信予定日時 |
| retry_count | INTEGER | NOT NULL | 0 | 現在ステップの失敗回数 |
| max_retries | INTEGER | NOT NULL | 3 | 最大再試行回数 |
| started_at | DATETIME | NOT NULL | | 開始日時 |
| updated_at | DATETIME | NOT NULL | | 更新日時 |

**インデックス:** `ix_scenario_enrollments_next_delivery_at`, `ix_scenario_enrollments_status`

---

### broadcasts

LINE 一斉配信。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| title | TEXT | NOT NULL | | 配信タイトル |
| message_type | TEXT | NOT NULL | 'text' | text / image / flex |
| message_content | TEXT | NOT NULL | | メッセージ本文 |
| target_type | TEXT | NOT NULL | 'all' | all / tag / segment |
| target_tag_id | TEXT | FK → tags | | タグ絞り込み時 |
| status | TEXT | NOT NULL | 'draft' | draft / scheduled / sending / sent / failed |
| scheduled_at | DATETIME | | | 予約配信日時 |
| sent_at | DATETIME | | | 送信完了日時 |
| total_count | INTEGER | NOT NULL | 0 | 対象者数 |
| success_count | INTEGER | NOT NULL | 0 | 送信成功数 |
| execution_plan_id | TEXT | FK → execution_plans | | 生成元の plan |
| created_at | DATETIME | NOT NULL | | 作成日時 |

**インデックス:** `ix_broadcasts_status`, `ix_broadcasts_scheduled_at`

---

### reminders

リマインダー。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| name | TEXT | NOT NULL | | リマインダ名 |
| description | TEXT | | | 説明 |
| is_active | BOOLEAN | NOT NULL | TRUE | 有効/無効 |
| execution_plan_id | TEXT | FK → execution_plans | | 生成元の plan |
| created_at | DATETIME | NOT NULL | | 作成日時 |
| updated_at | DATETIME | NOT NULL | | 更新日時 |

---

### reminder_steps

リマインダーの配信ステップ。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| reminder_id | TEXT | FK → reminders, NOT NULL | | 所属リマインダ |
| offset_minutes | INTEGER | NOT NULL | | 基準日からのオフセット（分） |
| message_type | TEXT | NOT NULL | 'text' | text / image / flex |
| message_content | TEXT | NOT NULL | | メッセージ本文 |
| created_at | DATETIME | NOT NULL | | 作成日時 |

**インデックス:** `ix_reminder_steps_reminder_id`

---

### reminder_enrollments

対象者のリマインダー登録。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| reminder_id | TEXT | FK → reminders, NOT NULL | | リマインダ |
| target_id | TEXT | NOT NULL | | 対象者の外部 ID |
| target_date | DATETIME | NOT NULL | | 基準日 |
| status | TEXT | NOT NULL | 'active' | active / completed / cancelled |
| created_at | DATETIME | NOT NULL | | 作成日時 |
| updated_at | DATETIME | NOT NULL | | 更新日時 |

**インデックス:** `ix_reminder_enrollments_status`, `ix_reminder_enrollments_target_date`

---

### reminder_deliveries

リマインダー配信記録。冪等性担保用。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| enrollment_id | TEXT | FK → reminder_enrollments, NOT NULL | | 登録 ID |
| reminder_step_id | TEXT | FK → reminder_steps, NOT NULL | | ステップ ID |
| delivered_at | DATETIME | NOT NULL | | 配信日時 |

**UNIQUE 制約:** `(enrollment_id, reminder_step_id)` — `uq_reminder_delivery`

---

## 実行基盤テーブル（Phase 4）

### approval_requests

承認リクエスト。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| plan_id | TEXT | FK → execution_plans, UNIQUE, NOT NULL | | 対象 plan |
| status | TEXT | NOT NULL | 'pending' | pending / approved / rejected |
| requested_at | DATETIME | NOT NULL | | リクエスト日時 |
| decided_at | DATETIME | | | 承認/却下日時 |
| decided_by | TEXT | | | 承認者 |
| reason | TEXT | | | 承認/却下理由 |

---

### processed_idempotency_keys

冪等性管理。二重実行防止。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| idempotency_key | TEXT | PK | | ExecutionStep の idempotency_key |
| step_id | TEXT | NOT NULL | | ステップ ID |
| plan_id | TEXT | NOT NULL | | plan ID |
| processed_at | DATETIME | NOT NULL | | 処理日時 |

---

### execution_audit_logs

監査ログ。全操作の証跡。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| execution_id | TEXT | | | 関連する execution |
| plan_id | TEXT | | | 関連する plan |
| action | TEXT | NOT NULL | | 操作種別 |
| detail_json | TEXT | NOT NULL | '{}' | 操作詳細（JSON） |
| created_at | DATETIME | NOT NULL | | 記録日時 |

**インデックス:** `ix_audit_logs_execution_id`, `ix_audit_logs_plan_id`, `ix_audit_logs_action`, `ix_audit_logs_created_at`

**action の値:** `plan_created` / `execution_started` / `step_executed` / `step_failed` / `step_skipped` / `step_retried` / `approval_requested` / `approval_decided`

---

### worker_task_logs

定期処理ログ。Scheduler の実行記録。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| task_name | TEXT | NOT NULL | | 処理名 |
| started_at | DATETIME | NOT NULL | | 開始日時 |
| finished_at | DATETIME | | | 終了日時 |
| processed_count | INTEGER | NOT NULL | 0 | 処理件数 |
| error_count | INTEGER | NOT NULL | 0 | エラー件数 |
| status | TEXT | NOT NULL | 'running' | running / completed / failed |

---

## ドメイン管理テーブル（Phase 5）

### domain_configs

ドメインの接続情報・有効/無効管理。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| domain | TEXT | UNIQUE, NOT NULL | | ドメイン名（line / email 等） |
| display_name | TEXT | NOT NULL | | 表示名 |
| is_enabled | BOOLEAN | NOT NULL | FALSE | 有効/無効 |
| config_json | TEXT | NOT NULL | '{}' | ドメイン固有設定（JSON） |
| priority | INTEGER | NOT NULL | 0 | 解決優先度（小さいほど高優先） |
| created_at | DATETIME | NOT NULL | | 作成日時 |
| updated_at | DATETIME | NOT NULL | | 更新日時 |

---

## Email ドメインテーブル（Phase 5）

### email_broadcasts

メール一斉配信。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| subject | TEXT | NOT NULL | | 件名 |
| body_html | TEXT | NOT NULL | | 本文（HTML） |
| body_text | TEXT | | | 本文（プレーンテキスト） |
| from_address | TEXT | NOT NULL | | 送信元アドレス |
| target_type | TEXT | NOT NULL | 'all' | all / segment |
| status | TEXT | NOT NULL | 'draft' | draft / scheduled / sending / sent / failed |
| scheduled_at | DATETIME | | | 予約配信日時 |
| sent_at | DATETIME | | | 送信完了日時 |
| total_count | INTEGER | NOT NULL | 0 | 対象者数 |
| success_count | INTEGER | NOT NULL | 0 | 送信成功数 |
| execution_plan_id | TEXT | FK → execution_plans | | 生成元の plan |
| created_at | DATETIME | NOT NULL | | 作成日時 |

**インデックス:** `ix_email_broadcasts_status`, `ix_email_broadcasts_scheduled_at`

---

### email_templates

メールテンプレート。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| name | TEXT | NOT NULL | | テンプレート名 |
| subject | TEXT | NOT NULL | | 件名テンプレート |
| body_html | TEXT | NOT NULL | | 本文テンプレート（HTML） |
| body_text | TEXT | | | プレーンテキスト |
| created_at | DATETIME | NOT NULL | | 作成日時 |
| updated_at | DATETIME | NOT NULL | | 更新日時 |

---

## 連絡先管理テーブル（Phase 7）

### contacts

チャネル横断の統一連絡先。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | contact_id（UUID） |
| display_name | TEXT | | | 表示名 |
| metadata_json | TEXT | NOT NULL | '{}' | 任意のメタデータ（JSON） |
| created_at | DATETIME | NOT NULL | | 作成日時 |
| updated_at | DATETIME | NOT NULL | | 更新日時 |

---

### contact_channels

チャネル別の外部 ID。1 つの contact に複数チャネルを紐付ける。

| カラム | 型 | 制約 | デフォルト | 説明 |
|---|---|---|---|---|
| id | TEXT | PK | | UUID |
| contact_id | TEXT | FK → contacts, NOT NULL | | 所属する contact |
| channel_type | TEXT | NOT NULL | | チャネル種別（line / email 等） |
| external_id | TEXT | NOT NULL | | チャネル上の外部 ID |
| created_at | DATETIME | NOT NULL | | 作成日時 |

**UNIQUE 制約:** `(channel_type, external_id)` — `uq_contact_channel`

**インデックス:** `ix_contact_channels_contact_id`
