# Agentic BizFlow ロードマップ

自然文変換器 → 実行計画器 → 状態を持つ実行基盤 → 安全な非同期運用基盤 → 複数業務ドメインの共通実行基盤

---

## 1. 現在地と進化の方向

### 1.1 現在の agentic-bizflow

自然文の業務手順を Reader → Planner → Validator → Generator の段階処理で BusinessDefinition JSON に変換する Agentic Architecture 実装。47 commits、Python / FastAPI / Pydantic / Vertex AI（Gemini 2.0 Flash）/ Cloud Run。

**できること:** 自然文を理解し、構造化された業務定義を作る
**できないこと:** 作った業務定義を実行する

### 1.2 目指す完成形

「LINE 配信ツール」でも「LLM チャットボット」でもない。

```
上位: 自然言語オーケストレーション（業務意図の理解・計画・承認・実行管理）
下位: 状態を持つ execution platform（業務オブジェクトの永続化・非同期実行・ログ）
```

利用者が「来週セミナー参加者に 3 日前と前日にリマインド送って」と言えば、内部ではリマインダ定義が作られ、対象者が登録され、Cron が配信タイミングで消化する。「軽いノリで指示できる」と「内部はちゃんと状態管理される」の両立が最終形。

### 1.3 line-harness-oss の位置づけ

line-harness-oss（github.com/Shudesu/line-harness-oss）は、Cloudflare Workers 上で scenarios / broadcasts / reminders / tags などの業務オブジェクトを D1 に保持し、Cron + Event Bus で非同期実行する構成を取っている。

これは「接続先」であると同時に、**agentic-bizflow が将来持つべき execution layer の参照モデル** である。

- 短期（Phase 2.5）: workload catalog の設計指針として参照する
- 中期（Phase 3）: ドメインモデルの参照実装として使う
- 長期（Phase 5）: LINE 以外のドメインへ拡張する際に、line-harness の構造を抽象化の土台にする

---

## 2. Phase 2.5 — 実行計画器

**期間:** 直近
**状態:** BusinessDefinition を作った後、「何を実行するか」を計画できるようにする

### 到達点

- BusinessDefinition → ExecutionPlan 変換
- dry-run（副作用なしプレビュー）
- 承認判定（危険操作のブロック）
- mock connector による限定実行
- 既存 Agent 層は変更しない

### Workload Catalog（5 種類）

line-harness-oss の API 粒度と ER 構造に合わせて定義。

| workload kind | 説明 | line-harness 対応先 | 承認要否 |
|---|---|---|---|
| `scenario.create` | シナリオ本体 + ステップ列の定義作成 | `scenarios` + `scenario_steps` | 不要 |
| `scenario.start` | 既存シナリオを特定友だちに開始 | `friend_scenarios` への enroll | 条件付き |
| `reminder.create` | リマインダ定義 + offset step の作成 | `reminders` + `reminder_steps` | 不要 |
| `broadcast.schedule` | 一斉配信の予約登録 | `broadcasts` (status=scheduled) | **常に必須** |
| `tag.assign` | ユーザーへのタグ付与 | `friend_tags` | 不要 |

### この phase でやること

- ExecutionPlan / ExecutionStep / ExecutionResult スキーマ
- ExecutionPlanner（BusinessDefinition → ExecutionPlan）
- WorkloadRunner（plan の step を connector に委譲して実行）
- Connector Adapter 抽象化 + mock connector
- 承認チェック
- `/api/plan`, `/api/dry-run`, `/api/execute` エンドポイント
- 回帰テスト（既存 `/api/convert` の保護）

### この phase でやらないこと

- 業務オブジェクトの永続化
- 本格的なジョブ基盤
- 本番 connector
- 実行履歴の DB 保存

### 設計詳細

→ `docs/phase2_5_roadmap.md`（設計・責務境界・API レスポンス例）
→ `task/phase2_5_tasks.md`（実装タスク）

---

## 3. Phase 3 — 状態を持つ実行基盤

**期間:** Phase 2.5 完了後
**状態:** 計画を「状態として保存」し、非同期で進行できるようにする

### 到達点

- workload ごとの永続化（DB にドメインオブジェクトを持つ）
- 実行状態の管理（planned → running → success / failed）
- 実行履歴の保存
- 友だち / 対象単位の enroll / register

### なぜ必要か

Phase 2.5 の ExecutionPlan はメモリ上の一時オブジェクトであり、実行が終われば消える。しかし実際の業務運用では「シナリオが今どこまで進んだか」「リマインダの 3 日前は配信済みで前日は未配信」「一斉配信は予約状態でまだ送信されていない」という状態管理が不可欠。

### 追加するドメインモデル

line-harness-oss の ER / テーブル仕様を参照モデルとする。以下は agentic-bizflow が自前で持つべき中核テーブル。

**シナリオ（ステップ配信）系:**

| テーブル | 役割 | line-harness 参照元 |
|---|---|---|
| `scenarios` | シナリオ定義（名前、トリガー種別、有効/無効） | scenarios |
| `scenario_steps` | ステップ列（順序、遅延分数、メッセージ、条件分岐） | scenario_steps |
| `friend_scenarios` | 友だちごとの enroll 状態（current_step, next_delivery_at, status） | friend_scenarios |

line-harness では `friend_scenarios.next_delivery_at ≤ now` を Cron が 5 分ごとに拾い、`step_order > current_step_order` の次ステップを配信する。この「宣言的に登録し、定期実行で消化する」構造を参考にする。

**配信系:**

| テーブル | 役割 | line-harness 参照元 |
|---|---|---|
| `broadcasts` | 一斉配信定義（status: draft/scheduled/sending/sent, scheduled_at） | broadcasts |
| `messages_log` | 送受信ログ（direction, broadcast_id, scenario_step_id） | messages_log |

line-harness では `status=scheduled, scheduled_at ≤ now` の broadcasts を Cron が拾って送信処理に進める。

**リマインダ系:**

| テーブル | 役割 | line-harness 参照元 |
|---|---|---|
| `reminders` | リマインダ定義 | reminders |
| `reminder_steps` | offset_minutes ごとのステップ | reminder_steps |
| `friend_reminders` | 友だちごとの登録（target_date, status） | friend_reminders |
| `friend_reminder_deliveries` | 配信済み記録（冪等性の担保） | friend_reminder_deliveries |

line-harness では `target_date + offset_minutes ≤ now` かつ未配信のステップを Cron が配信する。

**タグ系:**

| テーブル | 役割 | line-harness 参照元 |
|---|---|---|
| `tags` | タグ定義 | tags |
| `friend_tags` | 友だちとタグの中間テーブル | friend_tags |

タグはシナリオの trigger（`trigger_type=tag_added`）やセグメント条件にも使われるため、他 workload の前段としても機能する。

### Phase 3 のゴール

agentic-bizflow が「自然文 → 計画 → 状態登録」を一貫して持つこと。
この段階で、agentic-bizflow は「変換器」から「実行基盤」に変わる。

### この phase で入れなくてよいもの

- automations（IF-THEN 自動化ルール）
- notification_rules（通知ルール）
- scoring_rules（スコアリング）
- rich_menu / forms / calendar_bookings
- Event Bus 相当の並列イベント処理

これらは魅力的だが、まず 5 workload の状態管理を固めるのが先。

---

## 4. Phase 4 — 安全な非同期運用基盤

**期間:** Phase 3 完了後
**状態:** 保存した状態を安全にバックグラウンド実行する

### 到達点

- ジョブキュー / Cron / Worker による非同期実行
- 冪等性（idempotency_key による二重実行防止）
- 承認ワークフローの永続化
- 失敗再試行（retry policy）
- 実行ポリシー
- 監査ログ

### line-harness から学ぶ非同期実行パターン

line-harness の Cron Scheduler は 5 分間隔で以下を処理する:

```
processStepDeliveries()      — next_delivery_at ≤ now の friend_scenarios を配信
processScheduledBroadcasts() — status=scheduled, scheduled_at ≤ now の broadcasts を送信
processReminderDeliveries()  — target_date + offset_minutes ≤ now の未配信リマインダを送信
checkAccountHealth()         — LINE API のヘルスチェック
```

この「宣言的に状態を登録し、定期実行で消化する」パターンは、agentic-bizflow でもそのまま使える。ただし、Cloudflare Workers の Cron Triggers に依存するのではなく、Cloud Run + Cloud Tasks / Cloud Scheduler、または Cloud Run Jobs で同等の構成を取る。

### 配信最適化の扱い

line-harness のステルスエンジン（配信ジッター、バッチ間遅延、zero-width 文字、配信ウィンドウ制御）は技術的な工夫として理解できるが、プラットフォーム規約との距離感は慎重に見るべき。

agentic-bizflow では、配信最適化の詳細は connector 側の責務として隔離する。ExecutionPlanner / WorkloadRunner は「何をいつ誰に」を宣言するだけで、「どう送るか」の最適化は connector adapter の内部に閉じる。

### 追加する実装

- Scheduler / Worker 基盤（Cloud Tasks or Cloud Scheduler + Cloud Run Jobs）
- idempotency_key の検証と二重実行防止
- 承認状態の永続化（approval_state テーブル）
- retry policy（step 単位の再試行制御）
- execution_audit_log（実行監査ログ）
- 配信ウィンドウ制御（9:00-23:00 JST、line-harness 参照）

### Phase 4 のゴール

「軽く指示できる」と「安全に回る」を両立する層の完成。

---

## 5. Phase 5 — 複数業務ドメインの共通実行基盤

**期間:** Phase 4 完了後
**状態:** LINE 以外の業務ドメインにも同じオーケストレーション層で対応する

### 到達点

- LINE 以外の workload module
- 共通の approval / scheduling / execution model
- tenant 別 policy 設定
- cross-domain orchestration

### workload の拡張例

| workload kind | ドメイン | 説明 |
|---|---|---|
| `pos.campaign.create` | POS | 販促キャンペーン作成 |
| `crm.segment.update` | CRM | セグメント更新 |
| `odoo.customer.tag.assign` | ERP | 顧客タグ付与 |
| `email.broadcast.schedule` | メール配信 | 一斉メール予約 |
| `coupon.issue` | クーポン | クーポン発行 |
| `reservation.followup.start` | 予約 | 予約後フォローシナリオ開始 |

### なぜ可能か

agentic-bizflow は最初から「自然文を構造化し、業務定義に落とす」という汎用的な思想を持っている。README でも今後の拡張として ERP / 会計システム連携や社内業務自動化を挙げている。

line-harness は LINE CRM / 配信に強く寄っているが、agentic-bizflow はその上位概念として「自然文から業務実行へ落とす共通基盤」になれる余地がある。

### Phase 5 の構造

```
自然文入力
  ↓
Agent 層（Reader → Planner → Validator → Generator）
  ↓
BusinessDefinition
  ↓
ExecutionPlanner
  ↓
ExecutionPlan
  ↓
WorkloadRunner
  ↓
┌─────────────────────────────────────────────┐
│  Connector Adapters                         │
│                                             │
│  LINE connector  ← Phase 3-4 で完成        │
│  POS connector   ← Phase 5 で追加          │
│  CRM connector   ← Phase 5 で追加          │
│  Odoo connector  ← Phase 5 で追加          │
│  Email connector ← Phase 5 で追加          │
└─────────────────────────────────────────────┘
```

---

## 6. フェーズ間の進化の見え方

| Phase | agentic-bizflow は何か | 利用者から見える姿 |
|---|---|---|
| 現在 | 自然文変換器 | 自然文を入れると JSON が出る |
| 2.5 | 実行計画器 | JSON の先に「何をするか」のプランが見える |
| 3 | 状態を持つ実行基盤 | シナリオ / 配信 / リマインダが「登録」される |
| 4 | 安全な非同期運用基盤 | 登録したものがバックグラウンドで安全に実行される |
| 5 | 複数業務ドメインの共通基盤 | LINE 以外にも同じノリで指示できる |

---

## 7. 設計上の不変原則（全 Phase 共通）

これらはフェーズが変わっても崩さない。

### Agent 層と実行層を分離する

- Agent 層は業務定義 JSON の生成に集中する
- 外部 API 呼び出し、副作用を伴う処理は Agent 層に混ぜない
- 実行層を追加しても Agent 層のコードには変更を加えない

### 実行前に計画を可視化する

- 実行前に計画（ExecutionPlan）を生成し、人が確認可能な状態にする
- dry-run（副作用なしプレビュー）を常に可能にする
- 危険度の高い操作は承認なしに即実行させない

### LLM の出力を確定事実として扱わない

- Validator を通す
- Pydantic スキーマで構造検証する
- 生の LLM 応答を実行 payload やログにそのまま流さない

### 宣言的に登録し、定期実行で消化する

Phase 3 以降の設計原則。line-harness の Cron パターンに学ぶ。
- `scenario.start` = friend_scenarios に enroll し、Cron が next_delivery_at で配信
- `broadcast.schedule` = broadcasts に status=scheduled で登録し、Cron が scheduled_at で送信
- `reminder.create` = reminders + steps を登録し、Cron が target_date + offset で配信

「即時実行」ではなく「状態登録 + 定期消化」にすることで、承認・dry-run・監査・再試行との相性がよくなる。

---

## 8. line-harness-oss 調査資料の対応表

| 調査ファイル | 本ロードマップでの活用箇所 |
|---|---|
| `architecture.md` | Phase 3-4 の非同期実行パターン、Cron Scheduler 構成の参照 |
| `table-spec.md` | Phase 3 のドメインモデル設計の参照（テーブル定義・カラム・制約） |
| `er-diagram.md` | Phase 3 のテーブル間リレーション設計の参照 |
| `sequence-diagrams.md` | Phase 3-4 の実行フロー設計の参照（友だち追加→シナリオ開始、Cron 配信、ブロードキャスト送信、リマインダ配信） |

---

## 9. リスクと判断基準

### Phase 3 で line-harness のモデルをどこまで取り込むか

**取り込むべきもの:**
- scenarios / scenario_steps / friend_scenarios のエンロールメント構造
- broadcasts の status 状態遷移（draft → scheduled → sending → sent）
- reminders / reminder_steps / friend_reminders / friend_reminder_deliveries のカウントダウン構造
- tags / friend_tags のタグ操作

**慎重に見るべきもの:**
- ステルスエンジン（配信ジッター、zero-width 文字）→ connector 内部に隔離
- BAN 検知 → 運用ポリシーとして切り出す
- Event Bus の並列処理 → Phase 4 以降で必要に応じて導入

**Phase 3 では入れないもの:**
- automations（IF-THEN 自動化）
- scoring_rules（スコアリング）
- notification_rules（通知ルール）
- forms / rich_menus / calendar_bookings / stripe_events / affiliates

### Phase 5 に進むかどうかの判断基準

Phase 4 まで完成した時点で、以下が成立しているかを確認する:

- connector adapter の抽象化が十分か（新しい connector を足すときに WorkloadRunner を変更しなくてよいか）
- ExecutionPlan の workload kind が LINE 固有でなく、汎用的に拡張可能か
- 承認・スケジューリング・監査のモデルが connector に依存していないか

これらが成立していれば、Phase 5 は connector を足すだけで実現できる。
