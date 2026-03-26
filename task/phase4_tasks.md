# Phase 4: Async Execution Engine — 実装タスク

> **設計の参照先:** `docs/phase4/phase4_design.md`
> **全体ロードマップ:** `docs/roadmap-phase2_5-to-phase5.md`
> **最上位ルール:** `AGENTS.md`
> **実務ガイド:** `CLAUDE.md`

---

## 前提

- Phase 3 が完了していること（DB 永続化・ドメインテーブル・実行履歴照会が動作する）
- `backend/app/agent/` 配下のファイルは変更禁止
- 既存の全 API（Phase 1 / 2.5 / 3）が壊れていないことをテストで常に保証する
- AGENTS.md §6（日本語 docstring ①〜⑤）を全ファイルで満たすこと
- テスト完了時は `tests/evidence/` にエビデンスを保存すること
- テスト DB は Phase 3 で構築した in-memory SQLite + StaticPool + conftest.py を継続使用する

---

## Task 1: Phase 4 テーブルのマイグレーション

**作業:** Phase 4 で追加する 4 テーブルの ORM モデルとマイグレーションを作成する。

**追加するテーブル:**
- `approval_requests` — 承認リクエストの永続化
- `processed_idempotency_keys` — 冪等性管理
- `execution_audit_logs` — 監査ログ
- `worker_task_logs` — 定期処理ログ

> カラム定義は `docs/phase4/phase4_design.md` §3 を参照。

**追加するファイル:**
- `backend/app/db/models.py` に追記
- `backend/app/db/migrations/versions/003_phase4_tables.py`

**完了条件:**
- `alembic upgrade head` で 4 テーブルが追加作成される
- `alembic downgrade -1` で Phase 4 テーブルのみ削除される（Phase 3 テーブルは残る）
- ORM から CRUD 操作ができる

---

## Task 2: scenario_enrollments への retry カラム追加

**作業:** Phase 3 で作成した `scenario_enrollments` テーブルに retry 関連カラムを追加する。

**追加するカラム:**
- `retry_count` INTEGER NOT NULL DEFAULT 0
- `max_retries` INTEGER NOT NULL DEFAULT 3

**追加するファイル:**
- `backend/app/db/migrations/versions/004_retry_columns.py`

> 既存レコードは retry_count=0, max_retries=3 で初期化。

**完了条件:**
- マイグレーション正逆が動作する
- 既存の scenario_enrollments レコードに影響しない

---

## Task 3: 冪等性チェックの実装

**作業:** WorkloadRunner の step 実行に冪等性チェックを組み込む。

**追加するファイル:**
- `backend/app/db/repositories/idempotency_repo.py`

**変更するファイル:**
- `backend/app/execution/workload_runner.py` — step 実行前に `processed_idempotency_keys` をチェック

> 設計は `docs/phase4/phase4_design.md` §5 を参照。

**実装内容:**
- step 実行前に idempotency_key で検索 → 存在すれば skip
- step 実行成功後に idempotency_key を INSERT
- トランザクション内で実行（key INSERT と step 実行結果保存を原子的に）

**テスト:** `backend/tests/test_idempotency.py`

**完了条件:**
- 同一 idempotency_key で 2 回実行しても 2 回目は skipped になる
- 1 回目の実行結果は正常に保存される
- 既存の execute フロー（Phase 2.5 / 3）が壊れていない

---

## Task 4: 監査ログの実装

**作業:** 全操作の証跡を `execution_audit_logs` テーブルに記録する。

**追加するファイル:**
- `backend/app/db/repositories/audit_repo.py`

**変更するファイル:**
- `backend/app/execution/execution_planner.py` — plan 作成時にログ
- `backend/app/execution/workload_runner.py` — step 実行時にログ

**記録するアクション:**

| action | タイミング |
|---|---|
| `plan_created` | ExecutionPlan 生成時 |
| `execution_started` | WorkloadRunner.run() 開始時 |
| `step_executed` | step 実行成功時 |
| `step_failed` | step 実行失敗時 |
| `step_skipped` | 冪等性チェックでスキップ時 |
| `step_retried` | retry 実行時 |
| `approval_requested` | 承認リクエスト作成時 |
| `approval_decided` | 承認/却下時 |

**完了条件:**
- 主要な操作で audit_log が記録される
- `detail_json` に操作の要約が含まれる（生の LLM 応答は含めない）

---

## Task 5: 承認ワークフローの永続化

**作業:** Phase 2.5 の「API パラメータ approved=true」方式を、DB 永続化方式に拡張する。

**追加するファイル:**
- `backend/app/schemas/approval.py` — Pydantic スキーマ
- `backend/app/db/repositories/approval_repo.py`
- `backend/app/api/routes_approval.py`

**変更するファイル:**
- `backend/app/execution/approval.py` — DB 参照に対応
- `backend/app/api/routes_execute.py` — approval_requests.status を確認してから実行

> 設計は `docs/phase4/phase4_design.md` §7 を参照。

**API:**

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `GET /api/approvals` | GET | 一覧（?status=pending でフィルタ） |
| `GET /api/approvals/{id}` | GET | 詳細 |
| `POST /api/approvals/{id}/approve` | POST | 承認 |
| `POST /api/approvals/{id}/reject` | POST | 却下 |

**フロー:**
- `POST /api/plan` で requires_approval=true → approval_requests に pending で INSERT
- `POST /api/execute` → approval_requests.status == 'approved' でなければ blocked
- `POST /api/approvals/{id}/approve` → status を approved に更新

**テスト:** `backend/tests/test_approval_workflow.py`

**完了条件:**
- approval_requests が DB に永続化される
- approve/reject API が動作する
- 未承認の plan で execute を呼ぶと blocked が返る
- 承認済みの plan で execute が成功する
- dry-run は承認状態に関わらず実行可能

---

## Task 6: 配信ウィンドウ制御の実装

**作業:** 9:00–23:00 JST の配信ウィンドウ制御を実装する。

**追加するファイル:**
- `backend/app/workers/delivery_window.py`

> 設計は `docs/phase4/phase4_design.md` §8 を参照。

**実装内容:**
- `enforce_delivery_window(target_time) -> datetime` — ウィンドウ外なら翌朝 9:00 に繰り延べ
- `is_within_delivery_window(now) -> bool` — 現在時刻がウィンドウ内か判定

**テスト:** `backend/tests/test_delivery_window.py`

**完了条件:**
- 9:00–23:00 JST 内の時刻はそのまま返る
- 23:00–翌 9:00 の時刻は翌朝 9:00 に繰り延べられる
- タイムゾーン処理が正しい（UTC ↔ JST）

---

## Task 7: Worker — process_step_deliveries()

**作業:** scenario_enrollments の due な step を配信する定期処理を実装する。

**追加するファイル:**
- `backend/app/workers/step_delivery.py`

> 設計は `docs/phase4/phase4_design.md` §4.1 を参照。

**処理フロー:**
1. `scenario_enrollments` WHERE `status='active'` AND `next_delivery_at ≤ now` を取得
2. 配信ウィンドウチェック
3. 各 enrollment の次ステップを取得
4. 冪等性チェック → connector.execute()
5. 成功 → current_step_order 進行 + next_delivery_at 再計算
6. 最終ステップなら completed
7. 失敗 → retry_count++、上限超過なら failed
8. 監査ログ記録

**テスト:** `backend/tests/test_step_delivery.py`

**完了条件:**
- due な enrollment の step が配信される
- step 進行後に next_delivery_at が正しく再計算される
- 最終ステップ後に completed になる
- 失敗時に retry_count がインクリメントされる
- max_retries 超過で failed になる
- 配信ウィンドウ外ではスキップされる

---

## Task 8: Worker — process_scheduled_broadcasts()

**作業:** scheduled な broadcasts を送信する定期処理を実装する。

**追加するファイル:**
- `backend/app/workers/broadcast_delivery.py`

> 設計は `docs/phase4/phase4_design.md` §4.2 を参照。

**処理フロー:**
1. `broadcasts` WHERE `status='scheduled'` AND `scheduled_at ≤ now` を取得
2. status を 'sending' に更新
3. 冪等性チェック → connector.execute()
4. 成功 → status='sent', sent_at=now
5. 失敗 → status='failed'
6. 監査ログ記録

**テスト:** `backend/tests/test_broadcast_delivery.py`

**完了条件:**
- scheduled → sending → sent の遷移が動作する
- scheduled_at が未来の broadcasts は処理されない
- 失敗時に status='failed' になる

---

## Task 9: Worker — process_reminder_deliveries()

**作業:** reminder_enrollments の未配信ステップを配信する定期処理を実装する。

**追加するファイル:**
- `backend/app/workers/reminder_delivery.py`

> 設計は `docs/phase4/phase4_design.md` §4.3 を参照。

**処理フロー:**
1. `reminder_enrollments` WHERE `status='active'` を取得
2. 各 enrollment の reminder_steps を取得
3. `target_date + offset_minutes ≤ now` かつ `reminder_deliveries` に未記録のステップを抽出
4. 冪等性チェック → connector.execute()
5. 成功 → reminder_deliveries に INSERT
6. 全ステップ配信済み → enrollment.status='completed'
7. 監査ログ記録

**テスト:** `backend/tests/test_reminder_delivery.py`

**完了条件:**
- due な reminder_step が配信される
- reminder_deliveries に配信記録が作成される
- 同じ step の二重配信が UNIQUE 制約で防止される
- 全ステップ完了後に enrollment が completed になる

---

## Task 10: Scheduler の統合

**作業:** 3 つの Worker を定期実行する Scheduler を構成する。

**追加するファイル:**
- `backend/app/workers/__init__.py`
- `backend/app/workers/scheduler.py`

**実装内容:**
- APScheduler を使い、5 分間隔で 3 つの処理を実行
- 各処理の開始/終了/件数/エラーを `worker_task_logs` に記録
- FastAPI の lifespan event で Scheduler を起動/停止

**切替可能な構成:**
- 環境変数 `SCHEDULER_ENABLED=true/false` で有効/無効を切替
- 将来 Cloud Scheduler + Cloud Run Jobs に移行する際は、`workers/` 内のモジュールをそのまま Job のエントリポイントから呼ぶ

**完了条件:**
- アプリ起動後、5 分間隔で 3 処理が実行される
- `SCHEDULER_ENABLED=false` のとき Scheduler が起動しない
- worker_task_logs に実行記録が残る
- 1 処理の失敗が他の処理に影響しない

---

## Task 11: Connector Registry と LINE Connector の枠組み

**作業:** connector の切替メカニズムと LINE connector の枠組みを実装する。

**追加するファイル:**
- `backend/app/connectors/registry.py`
- `backend/app/connectors/live_line_connector.py`

> 設計は `docs/phase4/phase4_design.md` §9 を参照。

**Connector Registry:**
- 環境変数 `LINE_CONNECTOR_MODE` = `mock` / `db` / `live` で切替
- WorkloadRunner は registry 経由で connector を取得（Phase 2.5 の dict を registry.py に移動）

**LiveLineConnector:**
- `execute()`: LINE Messaging API 呼び出し + DB 書き込み
- `dry_run()`: API 呼ばず、DB 書き込まず、プレビュー返却
- `capabilities()`: 対応 action リスト
- LINE SDK のラッパーとして実装（httpx で LINE API を呼ぶ）

**テスト:** `backend/tests/test_live_line_connector.py`（LINE API は mock）

**完了条件:**
- `LINE_CONNECTOR_MODE` で mock / db / live が切り替わる
- live connector が mock された LINE API に対して正しいリクエストを送る
- デフォルトは `db` モード（Phase 3 の connector）

---

## Task 12: テストの追加と回帰確認

**12.1 回帰テスト（最優先）**

| テストファイル | 内容 |
|---|---|
| `test_existing_convert.py` | Phase 1 回帰（維持） |
| `test_existing_phase25.py` | Phase 2.5 回帰（維持） |
| `test_existing_phase3.py` | Phase 3 回帰（**新規**） |

**12.2 新規テスト一覧**

| テストファイル | 対象 |
|---|---|
| `test_idempotency.py` | 二重実行防止 |
| `test_approval_workflow.py` | 承認 CRUD + execute 連携 |
| `test_delivery_window.py` | 配信ウィンドウ計算 |
| `test_step_delivery.py` | scenario step 配信 Worker |
| `test_broadcast_delivery.py` | broadcast 配信 Worker |
| `test_reminder_delivery.py` | reminder 配信 Worker |
| `test_live_line_connector.py` | LINE connector（mock API） |

> テストの記述ルールは `docs/test-instruction-template.md` に従うこと。

**完了条件:**
- 全テストが通る
- 回帰テスト（Phase 1 / 2.5 / 3）が通る
- `tests/evidence/` にエビデンスが保存されている

---

## Task 13: フロントエンド / デモ導線の更新

**作業:**
- 承認待ち一覧画面を追加（GET /api/approvals?status=pending）
- 承認/却下ボタン
- 実行履歴に「Scheduler により実行」の表示を追加
- broadcasts / scenario_enrollments の状態遷移が確認できるビュー

**完了条件:**
- 「plan → 承認待ち → 承認 → Scheduler が実行 → 結果確認」の流れがデモできる

---

## Task 14: README / docs の更新

**作業:**
- README.md に Phase 4 の説明を追加
- アーキテクチャ図を更新（Scheduler / Worker 層を含める）
- `docs/README_architecture.md` に Phase 4 の設計補足

**完了条件:**
- README に Phase 4 の説明がある
- アーキテクチャ図に Scheduler / Worker 層が含まれている

---

## 実装順序

```
 1. Phase 4 テーブルのマイグレーション（Task 1）
 2. retry カラム追加（Task 2）
 3. 冪等性チェック（Task 3）
 4. 監査ログ（Task 4）
 5. 承認ワークフロー永続化（Task 5）
 6. 配信ウィンドウ制御（Task 6）
 7. Worker — step delivery（Task 7）
 8. Worker — broadcast delivery（Task 8）
 9. Worker — reminder delivery（Task 9）
10. Scheduler 統合（Task 10）
11. Connector Registry + LINE Connector（Task 11）
12. テスト追加と回帰確認（Task 12）
13. デモ導線更新（Task 13）
14. README / docs 更新（Task 14）
```

---

## 検証手順（Phase 4 完了時に実行）

```bash
# 1. マイグレーション
cd backend && alembic upgrade head

# 2. 既存テスト全件 PASS
cd backend && pytest tests/test_existing_convert.py tests/test_existing_phase25.py tests/test_existing_phase3.py -v

# 3. 新規テスト全件 PASS
cd backend && pytest tests/test_idempotency.py tests/test_approval_workflow.py tests/test_delivery_window.py tests/test_step_delivery.py tests/test_broadcast_delivery.py tests/test_reminder_delivery.py tests/test_live_line_connector.py -v

# 4. E2E: plan → approve → execute → scheduler cycle → check status transitions

# 5. エビデンス保存
cd backend && pytest tests/ -v > tests/evidence/phase4_test_result.txt
```

---

## 絶対に避けるべきこと

1. Agent 層のコードを変更する
2. Phase 2.5 / 3 の既存 API の振る舞いを壊す
3. Scheduler を Agent 層や ExecutionPlanner に混在させる
4. 冪等性チェックを省略した step 実行
5. 監査ログなしの状態遷移
6. `live` モードをデフォルトにする（デフォルトは `db`）
7. connector 内部にビジネスロジックを置く
8. ステルスエンジン（ジッター・zero-width 文字等）を Worker 層に実装する（connector 内部の責務）
9. Alembic マイグレーションなしのテーブル変更
