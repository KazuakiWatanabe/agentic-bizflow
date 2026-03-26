# Phase 5: Multi-Domain Execution Platform — 実装タスク

> **設計の参照先:** `docs/phase5/phase5_design.md`
> **全体ロードマップ:** `docs/roadmap-phase2_5-to-phase5.md`
> **最上位ルール:** `AGENTS.md`
> **実務ガイド:** `CLAUDE.md`

---

## 前提

- Phase 4 が完了していること（Scheduler / Worker / 冪等性 / 承認永続化 / 監査ログ / LINE connector が動作する）
- `backend/app/agent/` 配下のファイルは変更禁止
- 既存の全 API（Phase 1 / 2.5 / 3 / 4）が壊れていないことをテストで常に保証する
- AGENTS.md §6（日本語 docstring ①〜⑤）を全ファイルで満たすこと
- テスト完了時は `tests/evidence/` にエビデンスを保存すること

---

## 着手前チェック（必須）

Phase 4 完了時点で以下 3 条件が成立しているか確認する。成立していなければ Phase 4 の補修を先に行う。

- [ ] 新しい connector を足すときに WorkloadRunner を変更しなくてよい
- [ ] ExecutionPlan の workload kind が LINE 固有でなく拡張可能である
- [ ] 承認・スケジューリング・監査のモデルが connector に依存していない

---

## Task 1: Workload Kind Registry の実装

**作業:** workload kind を動的に登録・検索できる Registry を実装する。

**追加するファイル:**
- `backend/app/schemas/workload_kind.py` — WorkloadKindDefinition, ApprovalRule
- `backend/app/connectors/workload_kind_registry.py` — WorkloadKindRegistry クラス

> 設計は `docs/phase5/phase5_design.md` §3 を参照。

**実装内容:**
- `register(kind, domain, connector, requires_approval, description, keywords)`
- `get(kind) -> WorkloadKindDefinition`
- `list_by_domain(domain) -> list`
- `list_all() -> list`
- `is_valid(kind) -> bool`
- `register_alias(old_kind, new_kind)` — 後方互換用

**テスト:** `backend/tests/test_workload_kind_registry.py`

**完了条件:**
- kind の登録・取得・一覧が動作する
- ドメイン別のフィルタが動作する
- 存在しない kind で適切なエラーが返る
- エイリアス登録と解決が動作する

---

## Task 2: 後方互換の確保

**作業:** 旧 workload kind（`tag.assign` 等）を新形式（`line.tag.assign` 等）のエイリアスとして動作させる。

> 設計は `docs/phase5/phase5_design.md` §11 を参照。

**変更するファイル:**
- `backend/app/schemas/execution_plan.py` — ExecutionStep の kind を Literal から str に変更（Registry で検証）
- `backend/app/execution/execution_planner.py` — Registry 参照に切替

**実装内容:**
- LINE ドメインの初期化時に 5 つのエイリアスを登録
- ExecutionPlanner が kind を生成する際に Registry の is_valid() で検証
- DB 保存済みの旧形式 plan_json を取得時にエイリアス解決

**テスト:** `backend/tests/test_backward_compat.py`

**完了条件:**
- 旧形式 `tag.assign` で作成した plan が引き続き動作する
- 新形式 `line.tag.assign` でも同じ動作をする
- Phase 2.5 / 3 / 4 の既存テストが壊れていない

---

## Task 3: Domain Module 構造の構築

**作業:** `backend/app/domains/` ディレクトリを作成し、LINE 固有コードを移動する。

> 設計は `docs/phase5/phase5_design.md` §2.2, §2.3 を参照。

**追加するファイル:**
- `backend/app/domains/__init__.py` — ドメイン自動検出（`register()` を持つモジュールを探索）
- `backend/app/domains/line/__init__.py` — LINE ドメインの register()
- `backend/app/domains/line/workload_kinds.py` — LINE の 5 kind を定義
- `backend/app/domains/line/config.py` — LINE 設定スキーマ

**移動するファイル:**

| 移動元 | 移動先 |
|---|---|
| `connectors/live_line_connector.py` | `domains/line/connector.py` |
| `connectors/db_line_connector.py` | `domains/line/db_connector.py` |
| `workers/step_delivery.py` | `domains/line/worker.py` に統合 |
| `workers/broadcast_delivery.py` | `domains/line/worker.py` に統合 |
| `workers/reminder_delivery.py` | `domains/line/worker.py` に統合 |

**移動後に残すもの:**
- `connectors/base_connector.py` — フレームワーク（変更なし）
- `connectors/registry.py` — Connector Registry + Workload Kind Registry
- `connectors/mock_line_connector.py` — テスト用（維持）
- `workers/scheduler.py` — Scheduler フレームワーク
- `workers/delivery_window.py` — 共通ユーティリティ

**完了条件:**
- `domains/line/` に LINE 固有コードが集約されている
- アプリ起動時に LINE ドメインが自動登録される
- 既存の全機能（Scheduler / connector / API）が移動後も動作する
- `connectors/` と `workers/` にはフレームワークのみ残っている

---

## Task 4: ドメイン追加テンプレートの作成

**作業:** 新ドメイン追加時のひな形を作成する。

**追加するファイル:**
- `backend/app/domains/_template/__init__.py`
- `backend/app/domains/_template/connector.py`
- `backend/app/domains/_template/workload_kinds.py`
- `backend/app/domains/_template/worker.py`
- `backend/app/domains/_template/config.py`

各ファイルに「ここを変更する」コメントと最小限の実装例を含める。

**完了条件:**
- テンプレートをコピーして新ドメインディレクトリを作成し、register() を実装すればアプリに認識される

---

## Task 5: Domain 設定テーブルの追加

**作業:** ドメインの接続情報・有効/無効を管理するテーブルを追加する。

**追加するテーブル:**
- `domain_configs`

> カラム定義は `docs/phase5/phase5_design.md` §6.1 を参照。

**追加するファイル:**
- `backend/app/db/models.py` に追記
- `backend/app/db/repositories/domain_config_repo.py`
- `backend/app/db/migrations/versions/005_phase5_domain_config.py`
- `backend/app/schemas/domain_config.py`

**実装内容:**
- domain_configs の CRUD
- config_json 内の `_env` サフィックスキーを環境変数で解決するロジック
- LINE ドメインの初期設定レコードを seed する

**完了条件:**
- ドメイン設定が DB に保存・取得できる
- `_env` サフィックスの秘密値が環境変数から解決される
- 無効化されたドメインの connector が Registry に登録されない

---

## Task 6: ドメイン管理 API の追加

**作業:** ドメインの照会・設定変更 API を追加する。

**追加するファイル:**
- `backend/app/api/routes_domains.py`

**エンドポイント:**

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `GET /api/domains` | GET | 有効なドメイン一覧 |
| `GET /api/domains/{domain}` | GET | ドメイン詳細（workload kind 一覧含む） |
| `PUT /api/domains/{domain}/config` | PUT | 設定更新 |
| `POST /api/domains/{domain}/enable` | POST | 有効化 |
| `POST /api/domains/{domain}/disable` | POST | 無効化 |
| `GET /api/workload-kinds` | GET | 全 workload kind 一覧 |

**テスト:** `backend/tests/test_domain_config.py`

**完了条件:**
- ドメイン一覧が返る
- workload kind 一覧が返る
- enable / disable が動作し、connector Registry に反映される
- OpenAPI ドキュメントに反映される

---

## Task 7: Email ドメインの実装

**作業:** 最初の追加ドメインとして Email を実装する。

> 設計は `docs/phase5/phase5_design.md` §7 を参照。

**追加するファイル:**
- `backend/app/domains/email/__init__.py` — register()
- `backend/app/domains/email/connector.py` — EmailConnector
- `backend/app/domains/email/workload_kinds.py` — email.broadcast.schedule, email.template.create
- `backend/app/domains/email/worker.py` — process_scheduled_email_broadcasts()
- `backend/app/domains/email/config.py` — SMTP 設定スキーマ

**追加するテーブル:**
- `email_broadcasts`
- `email_templates`

> カラム定義は `docs/phase5/phase5_design.md` §7.3 を参照。

**追加するファイル:**
- `backend/app/db/models.py` に追記
- `backend/app/db/repositories/email_broadcast_repo.py`
- `backend/app/db/migrations/versions/006_phase5_email_tables.py`

**EmailConnector の実装:**
- `execute("email.broadcast.schedule", inputs)` → SMTP 送信 + DB 書き込み
- `execute("email.template.create", inputs)` → email_templates に INSERT
- `dry_run()` → SMTP に接続せず、プレビューを返す
- テスト時は SMTP をモック

**Scheduler 統合:**
- `domains/email/worker.py` の `process_scheduled_email_broadcasts()` を Scheduler に登録
- Email ドメインが enabled の場合のみ Worker が動作する

**テスト:**
- `backend/tests/test_email_connector.py`（SMTP モック）
- `backend/tests/test_email_worker.py`

**完了条件:**
- `email.broadcast.schedule` で email_broadcasts が status=scheduled で作成される
- Scheduler が scheduled → sending → sent に遷移させる
- `email.template.create` で email_templates にレコードが作成される
- dry_run で SMTP 送信されない
- Email ドメインの有効/無効が domain_configs で切り替わる

---

## Task 8: Cross-domain ExecutionPlan の検証

**作業:** 1 つの ExecutionPlan に LINE と Email の step が混在するケースを検証する。

**追加するファイル:**
- `backend/tests/test_cross_domain_plan.py`

**テストシナリオ:**

```
入力: 「VIPタグをつけて、LINE で明日10時にセール告知して、メールでも同じ内容を配信して」

期待する ExecutionPlan:
  step 1: line.tag.assign
  step 2: line.broadcast.schedule
  step 3: email.broadcast.schedule

期待する実行結果:
  step 1: success（tags + tag_assignments に書き込み）
  step 2: success（broadcasts に status=scheduled で書き込み）
  step 3: success（email_broadcasts に status=scheduled で書き込み）
```

**検証項目:**
- ExecutionPlanner が複数ドメインの kind を正しく判定する
- WorkloadRunner が step ごとに正しい connector を呼ぶ
- 1 つの step が失敗しても他ドメインの step に影響しない
- 承認判定がドメイン横断で正しく動作する（broadcast 系は両方とも要承認）
- 監査ログに connector ごとの実行記録が残る

**完了条件:**
- cross-domain plan の作成・dry-run・execute が一気通貫で動作する

---

## Task 9: Scheduler のドメイン動的登録

**作業:** Scheduler が有効なドメインの Worker を自動的に登録するように変更する。

**変更するファイル:**
- `backend/app/workers/scheduler.py`

**実装内容:**
- 起動時に `domain_configs` から enabled なドメインを取得
- 各ドメインの `worker.py` から定期処理関数を取得し、Scheduler に登録
- ドメインが disabled なら Worker を登録しない

**完了条件:**
- LINE ドメインの Worker が引き続き動作する
- Email ドメインを enable すると Worker が自動登録される
- Email ドメインを disable すると Worker が停止する
- 既存の Scheduler 動作に影響しない

---

## Task 10: テストの追加と回帰確認

**10.1 回帰テスト（最優先）**

| テストファイル | 内容 |
|---|---|
| `test_existing_convert.py` | Phase 1 回帰（維持） |
| `test_existing_phase25.py` | Phase 2.5 回帰（維持） |
| `test_existing_phase3.py` | Phase 3 回帰（維持） |
| `test_existing_phase4.py` | Phase 4 回帰（**新規**） |

**10.2 新規テスト一覧**

| テストファイル | 対象 |
|---|---|
| `test_workload_kind_registry.py` | Registry の登録・検索・エイリアス |
| `test_backward_compat.py` | 旧 workload kind の後方互換 |
| `test_domain_config.py` | ドメイン設定 CRUD・API |
| `test_email_connector.py` | Email connector（SMTP モック） |
| `test_email_worker.py` | Email Worker |
| `test_cross_domain_plan.py` | LINE + Email 混在 plan |

> テストの記述ルールは `docs/test-instruction-template.md` に従うこと。

**完了条件:**
- 全テストが通る
- 回帰テスト（Phase 1 / 2.5 / 3 / 4）が通る
- `tests/evidence/` にエビデンスが保存されている

---

## Task 11: フロントエンド / デモ導線の更新

**作業:**
- ドメイン選択 UI を追加（LINE / Email を切替）
- cross-domain plan のデモ（LINE + Email 同時配信）
- ドメイン管理画面（有効/無効切替）

**完了条件:**
- 「自然文 → LINE + Email 混在の plan → dry-run → 実行 → 履歴確認」がデモできる

---

## Task 12: README / docs の更新

**作業:**
- README.md に Phase 5 の説明を追加
- アーキテクチャ図を更新（Domain Module 構造を含める）
- `docs/README_architecture.md` に Phase 5 の設計補足
- 新ドメイン追加手順のドキュメントを作成

**完了条件:**
- README に Phase 5 の説明がある
- アーキテクチャ図に Domain Module 構造が含まれている
- 新ドメイン追加手順が文書化されている

---

## 実装順序

```
 0. 着手前チェック（Phase 4 完了条件の確認）
 1. Workload Kind Registry（Task 1）
 2. 後方互換の確保（Task 2）
 3. Domain Module 構造の構築 + LINE 移動（Task 3）
 4. ドメイン追加テンプレート（Task 4）
 5. Domain 設定テーブル（Task 5）
 6. ドメイン管理 API（Task 6）
 7. Email ドメインの実装（Task 7）
 8. Cross-domain ExecutionPlan の検証（Task 8）
 9. Scheduler のドメイン動的登録（Task 9）
10. テスト追加と回帰確認（Task 10）
11. デモ導線更新（Task 11）
12. README / docs 更新（Task 12）
```

---

## 検証手順（Phase 5 完了時に実行）

```bash
# 1. マイグレーション
cd backend && alembic upgrade head

# 2. 全フェーズの回帰テスト
cd backend && pytest tests/test_existing_convert.py tests/test_existing_phase25.py tests/test_existing_phase3.py tests/test_existing_phase4.py -v

# 3. 後方互換テスト
cd backend && pytest tests/test_backward_compat.py -v

# 4. Phase 5 新規テスト
cd backend && pytest tests/test_workload_kind_registry.py tests/test_cross_domain_plan.py tests/test_email_connector.py tests/test_email_worker.py tests/test_domain_config.py -v

# 5. E2E: LINE + Email cross-domain plan の作成・承認・実行・Scheduler 消化・履歴確認

# 6. エビデンス保存
cd backend && pytest tests/ -v > tests/evidence/phase5_test_result.txt
```

---

## 絶対に避けるべきこと

1. Agent 層のコードを変更する
2. Phase 2.5 / 3 / 4 の既存 API の振る舞いを壊す
3. 旧 workload kind（`tag.assign` 等）を無効にする（後方互換必須）
4. WorkloadRunner に connector 固有のロジックを追加する
5. BaseConnector のインターフェースを変更する
6. SMTP の秘密値を config_json に直接格納する（`_env` サフィックスで環境変数参照）
7. 全ドメインの connector を一度に実装する（Phase 5 では Email のみ）
8. ドメイン固有のテーブルを共通テーブルに混ぜる（email_broadcasts と broadcasts は別テーブル）
9. Alembic マイグレーションなしのテーブル変更
