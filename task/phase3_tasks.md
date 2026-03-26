# Phase 3: Stateful Execution Platform — 実装タスク

> **設計の参照先:** `docs/phase3/phase3_design.md`
> **全体ロードマップ:** `docs/roadmap-phase2_5-to-phase5.md`
> **最上位ルール:** `AGENTS.md`
> **実務ガイド:** `CLAUDE.md`

---

## 前提

- Phase 2.5 が完了していること（ExecutionPlanner / WorkloadRunner / mock connector が動作する）
- `backend/app/agent/` 配下のファイルは変更禁止
- 既存の `POST /api/convert` および Phase 2.5 の `/api/plan`, `/api/dry-run`, `/api/execute` が壊れていないことをテストで常に保証する
- AGENTS.md §6（日本語 docstring ①〜⑤）を全ファイルで満たすこと
- テスト完了時は `tests/evidence/` にエビデンスを保存すること

---

## Task 1: DB 基盤の構築

**作業:** `backend/app/db/` ディレクトリを作成し、SQLAlchemy + Alembic の基盤を整備する。

**追加するファイル:**
- `backend/app/db/__init__.py`
- `backend/app/db/session.py` — DB セッション管理（async sessionmaker）
- `backend/app/db/base.py` — SQLAlchemy Base クラス
- `alembic.ini` — Alembic 設定
- `backend/app/db/migrations/env.py` — マイグレーション環境

**設定:**
- 開発環境は SQLite（`sqlite:///./dev.db`）
- 本番環境は環境変数 `DATABASE_URL` で切替可能にする
- セッションは `async with` で使い、リクエストごとに閉じる

> `docs/phase3/phase3_design.md` §6 のディレクトリ構成を参照。

**完了条件:**
- `alembic upgrade head` が空の状態で成功する
- FastAPI の起動時に DB 接続が確立される
- セッションの取得・解放がリクエストスコープで動作する

---

## Task 2: 実行管理テーブルのマイグレーション

**作業:** 実行計画・実行結果を保存する 3 テーブルの ORM モデルとマイグレーションを作成する。

**追加するテーブル:**
- `execution_plans`
- `execution_results`
- `step_results`

> カラム定義は `docs/phase3/phase3_design.md` §3.1 を参照。

**追加するファイル:**
- `backend/app/db/models.py` — ORM モデル（上記 3 テーブル分）
- `backend/app/db/migrations/versions/001_execution_tables.py`

**完了条件:**
- `alembic upgrade head` で 3 テーブルが作成される
- `alembic downgrade -1` で元に戻せる
- ORM モデルから CRUD 操作ができる（ユニットテスト）

---

## Task 3: workload ドメインテーブルのマイグレーション

**作業:** 5 workload kind に対応するドメインテーブルの ORM モデルとマイグレーションを作成する。

**追加するテーブル:**
- `scenarios` + `scenario_steps` + `scenario_enrollments`
- `broadcasts`
- `reminders` + `reminder_steps` + `reminder_enrollments` + `reminder_deliveries`
- `tags` + `tag_assignments`

> カラム定義は `docs/phase3/phase3_design.md` §3.2 を参照。
> line-harness-oss との命名差分は `docs/phase3/phase3_design.md` §3.3 を参照。

**追加するファイル:**
- `backend/app/db/models.py` に追記（上記テーブル分）
- `backend/app/db/migrations/versions/002_workload_tables.py`

**完了条件:**
- `alembic upgrade head` で全テーブルが作成される
- インデックスが正しく作成されている
- UNIQUE 制約（scenario_steps の scenario_id + step_order 等）が機能する
- ORM モデルから CRUD 操作ができる（ユニットテスト）

---

## Task 4: ExecutionPlan の永続化

**作業:** `ExecutionPlanner.plan()` の結果を `execution_plans` テーブルに保存する。

**変更するファイル:**
- `backend/app/execution/execution_planner.py` — plan 生成後に DB 保存
- `backend/app/api/routes_plan.py` — DB セッションの注入

**追加するファイル:**
- `backend/app/db/repositories/execution_repo.py` — execution_plans の CRUD

**実装内容:**
- `plan()` 実行後、ExecutionPlan の JSON と source_definition の JSON を `execution_plans` に INSERT
- `GET /api/plans` で保存済み plan 一覧を返す
- `GET /api/plans/{plan_id}` で plan 詳細を返す

**完了条件:**
- `POST /api/plan` で execution_plans にレコードが作成される
- `GET /api/plans` で一覧が返る
- `GET /api/plans/{plan_id}` で詳細が返る
- 既存の plan → dry-run → execute フローが壊れていない

---

## Task 5: DB Connector の実装（mock → DB 書き込み）

**作業:** Phase 2.5 の mock connector を、DB に実際のドメインレコードを書き込む connector に置き換える。

**追加するファイル:**
- `backend/app/connectors/db_line_connector.py`
- `backend/app/db/repositories/scenario_repo.py`
- `backend/app/db/repositories/broadcast_repo.py`
- `backend/app/db/repositories/reminder_repo.py`
- `backend/app/db/repositories/tag_repo.py`

**実装内容:**

| workload kind | connector が DB に書く内容 |
|---|---|
| `tag.assign` | `tags` に UPSERT + `tag_assignments` に INSERT |
| `broadcast.schedule` | `broadcasts` に INSERT（status=scheduled） |
| `scenario.create` | `scenarios` + `scenario_steps` に INSERT |
| `scenario.start` | `scenario_enrollments` に INSERT（status=active） |
| `reminder.create` | `reminders` + `reminder_steps` に INSERT |

**dry_run 時:**
- DB に書き込まない
- 「何が書き込まれるか」のプレビューを返す

**完了条件:**
- 各 workload kind の execute で対応するテーブルにレコードが作成される
- dry_run では DB にレコードが作成されない
- broadcasts は status=scheduled で登録される
- scenario_enrollments は status=active で登録される
- capabilities() が正しい action リストを返す

---

## Task 6: ExecutionResult の永続化

**作業:** WorkloadRunner の実行結果を `execution_results` + `step_results` テーブルに保存する。

**変更するファイル:**
- `backend/app/execution/workload_runner.py` — 実行後に DB 保存
- `backend/app/api/routes_execute.py` — DB セッションの注入

**追加するファイル:**
- `backend/app/db/repositories/execution_repo.py` に追記

**実装内容:**
- WorkloadRunner.run() 完了後に execution_results + step_results を INSERT
- execution_plans.status を executing → completed / failed に更新
- 失敗時もエラー情報を保存する

**完了条件:**
- execute 後に execution_results にレコードが作成される
- step ごとに step_results にレコードが作成される
- execution_plans.status が完了状態に遷移する
- 失敗時にもレコードが保存される

---

## Task 7: 実行履歴照会 API

**作業:** 実行履歴を照会するエンドポイントを追加する。

**追加するファイル:**
- `backend/app/api/routes_history.py`

**エンドポイント:**

| エンドポイント | 説明 |
|---|---|
| `GET /api/executions` | 実行履歴一覧（ページネーション対応） |
| `GET /api/executions/{execution_id}` | 実行詳細（step_results 含む） |

> レスポンス例は `docs/phase3/phase3_design.md` §7.3 を参照。

**完了条件:**
- 実行履歴一覧が返る
- execution_id で詳細が返る（step_results、作成されたレコード情報を含む）
- 存在しない execution_id で 404 が返る
- OpenAPI ドキュメントに反映される

---

## Task 8: テストの追加

**8.1 回帰テスト（最優先）**
- `test_existing_convert.py`: 既存 `/api/convert` の回帰テスト（維持）
- `test_existing_phase25.py`: Phase 2.5 の plan / dry-run / execute の回帰テスト（新規）

**8.2 DB モデルテスト**
- 全テーブルの CRUD 操作
- 外部キー制約の動作
- UNIQUE 制約の動作
- status カラムの CHECK 制約

**8.3 DB Connector テスト**
- tag.assign で tags + tag_assignments にレコードが作成される
- broadcast.schedule で broadcasts が status=scheduled で作成される
- scenario.create で scenarios + scenario_steps が作成される
- scenario.start で scenario_enrollments が status=active で作成される
- reminder.create で reminders + reminder_steps が作成される
- dry_run で DB にレコードが作成されない

**8.4 永続化テスト**
- ExecutionPlan が DB に保存・取得できる
- ExecutionResult + StepResult が DB に保存・取得できる
- execution_plans.status が正しく遷移する

**8.5 実行履歴 API テスト**
- GET /api/executions で一覧が返る
- GET /api/executions/{id} で詳細が返る
- 存在しない ID で 404 が返る

> テストの記述ルールは `docs/test-instruction-template.md` に従うこと。

**完了条件:**
- 全テストが通る
- 回帰テスト（Phase 1 + Phase 2.5）が通る
- `tests/evidence/` にエビデンスが保存されている

---

## Task 9: フロントエンド / デモ導線の更新

**作業:** 既存のデモ導線に実行履歴の表示を追加する。

- execute 後に「実行履歴を見る」リンクを表示
- 実行履歴一覧ページ（GET /api/executions を呼ぶ）
- 実行詳細ページ（step ごとの結果 + 作成されたレコード情報）

**完了条件:**
- 「自然文 → 業務定義 → 実行計画 → 実行 → 履歴確認」の流れがブラウザ上で確認できる

---

## Task 10: README / docs の更新

**作業:**
- README.md に Phase 3 の説明を追加
- アーキテクチャ図を更新（DB 層を含める）
- `docs/README_architecture.md` に Phase 3 の設計補足を追加

**完了条件:**
- README に Phase 3 の説明がある
- アーキテクチャ図に DB 層が含まれている

---

## 実装順序

```
 1. DB 基盤の構築（Task 1）
 2. 実行管理テーブル（Task 2）
 3. workload ドメインテーブル（Task 3）
 4. ExecutionPlan の永続化（Task 4）
 5. DB Connector の実装（Task 5）
 6. ExecutionResult の永続化（Task 6）
 7. 実行履歴照会 API（Task 7）
 8. テスト追加（Task 8）— 回帰テストを最優先
 9. デモ導線更新（Task 9）
10. README / docs 更新（Task 10）
```

---

## 絶対に避けるべきこと

1. Agent 層のコードを変更する
2. Phase 2.5 の既存 API の振る舞いを壊す（レスポンス形式変更等）
3. Cron / Worker / 非同期ジョブキューを導入する（Phase 4 の責務）
4. broadcasts を status=sent まで進める（Phase 4 の責務）
5. scenario_enrollments の step 進行を実装する（Phase 4 の責務）
6. 本番 LINE API を叩く connector を実装する（Phase 4 の責務）
7. DB マイグレーションなしにテーブルを追加する
