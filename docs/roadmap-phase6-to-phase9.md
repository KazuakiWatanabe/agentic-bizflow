# ロードマップ: LINE 運用デモから集客アプリ展開へ（Phase 6〜9）

> **前提:** Phase 2.5〜5（実行計画 / DB 永続化 / Scheduler / 冪等性 / 承認 / 監査 / Multi-domain）が実装済み
> **先行ロードマップ:** `docs/roadmap-phase2_5-to-phase5.md`
> **最上位ルール:** `AGENTS.md`

---

## 1. 議論の評価と方針決定

### 1.1 現在地

Phase 5 まで実装が完了し、agentic-bizflow は以下を備えている:

- 自然文 → BusinessDefinition → ExecutionPlan → dry-run / 承認 / 実行
- DB 永続化（20 テーブル、全 workload の状態管理）
- Scheduler / Worker による非同期消化（scenario step / broadcast / reminder）
- 冪等性（processed_idempotency_keys）、監査ログ（execution_audit_logs）
- 承認ワークフロー永続化（approval_requests）
- Workload Kind Registry による動的拡張
- Domain Module 構造（domains/line/ + domains/email/）
- Cross-domain ExecutionPlan（LINE + Email 混在）

**もはや「LLM で JSON を作るデモ」ではなく、実行基盤の原型ができている。**

### 1.2 次にやるべきことは「機能追加」ではない

Phase 5 までで基盤の骨格は揃った。次の論点は:

- ❌ Phase を足して機能を広げる
- ✅ **何を主戦場にするか** を決め、**製品として見せられる形** にする

### 1.3 決定した方針

```
外部への見せ方:
  LINE 運用を自然文から安全に回せる製品

内部設計の方針:
  類似の集客アプリへ差し替え可能な実行基盤
```

この二層構えにより:
- 最初のデモは具体的でわかりやすい（LINE 運用）
- 将来の展開余地も説明できる（集客チャネル共通基盤）
- 今の実装資産が無駄にならない

### 1.4 見せ方の順序

```
Step 1: LINE で見せる
  「自然文で、配信・タグ付け・シナリオ開始・リマインドまで回る」

Step 2: 安全性を見せる
  「承認・dry-run・Scheduler・冪等性・監査があるので業務利用に耐える」

Step 3: 拡張性を見せる
  「同じ plan に LINE + Email を混在できる」

Step 4: 展開先を見せる
  「店舗向け集客アプリにも広げられる」
```

---

## 2. Phase 概要

| Phase | 名称 | 目的 | 主なアウトプット |
|---|---|---|---|
| **6** | LINE Demo & Admin UI | LINE 運用の 1 本ストーリーを完成させ、管理画面で見せられる状態にする | デモシナリオ、管理 UI、live connector 接続 |
| **7** | Marketing Channel Abstraction | 内部モデルを集客チャネル共通の語彙に抽象化する | 共通語彙、workload kind 二層化、contact モデル |
| **8** | Channel Adapter & Expansion | 類似集客アプリへ展開可能なアダプタ構造を整備する | capability 定義、第 2 チャネル PoC adapter |
| **9** | Production Readiness | マルチテナント・認証・権限・ポリシー管理で製品化する | tenant / auth / RBAC / policy / 運用ダッシュボード |

---

## 3. Phase 6 — LINE Demo & Admin UI

**期間:** 直近 1〜2 ヶ月
**目的:** 外部に見せられる LINE 運用デモの完成

### 到達点

- 1 本の完成デモシナリオが動く（自然文入力 → plan → 承認 → scheduled 実行 → reminder 追従 → 履歴確認）
- 管理 UI で plan / approval / execution / scenario / broadcast / reminder を一覧・操作できる
- LINE live connector で 1 ユースケースだけ本番接続が通る
- 外部説明用の 1 ページ資料とデモ動画がある

### やること

- デモシナリオの固定（サンプルデータ + 操作手順）
- 管理 UI（plan / approval / execution / workload 一覧）
- LINE live connector の最小接続（1 系統のみ）
- README / 外部資料の整備

### やらないこと

- マルチテナント / 認証（→ Phase 9）
- 概念の抽象化（→ Phase 7）
- 新ドメインの追加（→ Phase 8）

---

## 4. Phase 7 — Marketing Channel Abstraction

**期間:** Phase 6 完了後 1〜2 ヶ月
**目的:** LINE 専用品の見た目を維持しつつ、内部を集客チャネル共通基盤に整理する

### 到達点

- 外向け語彙を LINE 用語から共通マーケティング語彙へ寄せる（API / UI / ドキュメント）
- workload kind を共通 kind（audience.label.assign 等）と domain kind（line.tag.assign 等）の二層にする
- 内部 contact モデル（contact_id + channel_account_id + channel_type）を導入し、target_id のチャネル依存を隔離する
- 類似アプリへの差し替え可能性を説明できる資料がある

### 用語の対応表

| 現在（LINE 中心） | Phase 7 以降（共通語彙） | 内部テーブル名 |
|---|---|---|
| tags | audience labels / segments | tags（変更なし） |
| broadcasts | campaign deliveries | broadcasts（変更なし） |
| scenarios | journeys / automations | scenarios（変更なし） |
| reminders | timed follow-ups | reminders（変更なし） |
| target_id | contact_id → channel_account_id | 新規 contacts テーブル |

**DB テーブル名は変えない。** 外向きの API レスポンスキー名・UI ラベル・ドキュメントの用語を変える。

### workload kind 二層化

```
共通 kind（ExecutionPlanner が使う）:
  audience.label.assign
  campaign.schedule
  journey.create
  journey.enroll
  followup.create

ドメイン kind（Connector が使う）:
  line.tag.assign
  line.broadcast.schedule
  line.scenario.create
  line.scenario.start
  line.reminder.create
  email.broadcast.schedule
```

ExecutionPlanner は共通 kind を生成し、WorkloadRunner が domain_configs の有効ドメインに基づいてドメイン kind に解決する。

---

## 5. Phase 8 — Channel Adapter & Expansion

**期間:** Phase 7 完了後
**目的:** 類似の集客アプリへ展開可能なアダプタ構造を整備する

### 到達点

- capability 定義（supports_campaign / supports_label / supports_journey / supports_followup）
- 同じ自然文でも利用可能なアクションだけに plan を自動調整できる
- 第 2 チャネル（店舗向け集客アプリ等）用の PoC adapter を 1 本実装
- 新チャネル追加手順が文書化されている

### capability 定義

```python
class ChannelCapability(BaseModel):
    supports_campaign: bool        # 一斉配信
    supports_label: bool           # タグ / セグメント
    supports_journey: bool         # ステップ配信 / シナリオ
    supports_followup: bool        # リマインダー
    supports_template: bool        # テンプレート管理
    max_batch_size: int | None     # バッチ送信上限
```

これにより、同じ自然文でも「この集客アプリでは journey は不可、campaign は可能」のように plan を自動調整できる。

---

## 6. Phase 9 — Production Readiness

**期間:** Phase 8 完了後
**目的:** 複数顧客に提供できる運用製品にする

### 到達点

- tenant_id の全主要テーブルへの導入
- 認証 / 権限（RBAC）
- 実行ポリシーの外出し（approval_rules / retry_policies / delivery_windows を設定テーブル化）
- 運用ダッシュボード（plan 生成成功率 / 実行成功率 / 承認待ち滞留 / worker 失敗率 / connector 別失敗率）
- Cloud Scheduler + Cloud Run Jobs への移行

---

## 7. 設計上の不変原則（全 Phase 共通）

Phase 2.5〜5 から引き継ぐ。

- Agent 層と実行層を分離する（Agent 層のコードは変更しない）
- 実行前に計画を可視化する（dry-run を常に可能にする）
- 承認なしに危険操作を即実行させない
- 宣言的に登録し、定期実行で消化する
- LLM の出力を確定事実として扱わない
- 生の LLM 応答をログや payload に流さない

---

## 8. 現在の DB 構成と Phase 6〜9 での変更見通し

### 現在のテーブル（20 テーブル）

| 分類 | テーブル | Phase |
|---|---|---|
| 実行管理 | execution_plans, execution_results, step_results | 3 |
| LINE ドメイン | tags, tag_assignments, scenarios, scenario_steps, scenario_enrollments, broadcasts, reminders, reminder_steps, reminder_enrollments, reminder_deliveries | 3 |
| 実行基盤 | approval_requests, processed_idempotency_keys, execution_audit_logs, worker_task_logs | 4 |
| ドメイン管理 | domain_configs | 5 |
| Email ドメイン | email_broadcasts, email_templates | 5 |

### Phase 6〜9 で追加が見込まれるテーブル

| Phase | テーブル候補 | 目的 |
|---|---|---|
| 7 | contacts, contact_channels | チャネル非依存の対象者管理 |
| 8 | channel_capabilities | チャネルごとの対応機能宣言 |
| 9 | tenants, tenant_users, roles, permissions, policy_sets, workload_policies | マルチテナント・権限・ポリシー |

**Phase 6 では既存テーブルへの変更なし。** UI とデモシナリオとライブ接続のみ。

---

## 9. リスクと判断基準

### Phase 6 に進む前に確認すべきこと

- 既存の全テスト（Phase 1〜5）が通過しているか
- demo-guide.md のフローが一気通貫で動作するか
- LINE_CONNECTOR_MODE=db で全 workload が正常に DB 書き込みされるか

### Phase 7 に進む前に確認すべきこと

- Phase 6 のデモが外部に見せられる品質か
- 共通語彙への寄せが既存 API の後方互換を壊さないか

### Phase 8 に進む前に確認すべきこと

- capability 定義が workload kind の自動調整に使えるか
- 新チャネルの adapter を WorkloadRunner の変更なしで追加できるか

### Phase 9 に進む前に確認すべきこと

- tenant_id 導入が既存の全テーブルに影響する範囲を事前に洗い出したか
- 認証基盤の選定（自前 / Firebase Auth / Auth0 等）が決まっているか
