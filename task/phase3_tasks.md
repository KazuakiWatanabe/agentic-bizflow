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

## テスト DB 戦略

本 Phase で導入する DB テストは以下の構成で統一する。

```python
# backend/tests/conftest.py

# in-memory SQLite + StaticPool
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# SQLite は FK がデフォルト OFF なので event listener で有効化
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# conftest.py で get_db を override し、全テストで DB 利用可能にする
# 各テスト後に rollback で初期化
```

---

## Task 1: DB 基盤の構築

**作業:** `backend/app/db/` を作成し、SQLAlchemy + Alembic の基盤を整備する。

**追加するファイル:**

| ファイル | 内容 |
|---|---|
| `backend/app/db/__init__.py` | パッケージ初期化 |
| `backend/app/db/base.py` | `DeclarativeBase` サブクラス |
| `backend/app/db/session.py` | `async_sessionmaker` / `get_db` 依存関数 |
| `backend/alembic.ini` | Alembic 設定 |
| `backend/app/db/migrations/env.py` | マイグレーション環境 |
| `backend/tests/conftest.py` | テスト DB 設定（上記戦略） |

**設定:**
- 開発: `sqlite:///./dev.db`
- テスト: `sqlite:///:memory:` + StaticPool
- 本番: 環境変数 `DATABASE_URL` で切替

**FastAPI 統合:**
- `app/main.py` に `get_db` 依存を登録
- 既存エンドポイントには影響しない（DB を使わない既存ルートはそのまま動く）

> `docs/phase3/phase3_design.md` §7 のディレクトリ構成を参照。

**完了条件:**
- `alembic upgrade head` が空の状態で成功する
- FastAPI 起動時に DB 接続が確立される
- `conftest.py` の in-memory DB でテストが実行できる
- 既存テストが壊れていない

---

## Task 2: 実行管理テーブルのマイグレーション

**作業:** 実行計画・実行結果を保存する 3 テーブルの ORM モデルとマイグレーションを作成する。

**追加するテーブル:**
- `execution_plans`
- `execution_results`
- `step_results`

> カラム定義は `docs/phase3/phase3_design.md` §4.1 を参照。

**追加するファイル:**
- `backend/app/db/models.py` — ORM モデル（上記 3 テーブル分）
- `backend/app/db/migrations/versions/001_execution_tables.py`

**テスト:**
- `backend/tests/test_db_models.py` に CRUD テストを追加

**完了条件:**
- `alembic upgrade head` で 3 テーブルが作成される
- `alembic downgrade -1` で元に戻せる
- ORM から INSERT / SELECT / UPDATE / DELETE ができる
- FK 制約が動作する（step_results.execution_id → execution_results.id）

---

## Task 3: workload ドメインテーブルのマイグレーション

**作業:** 5 workload kind に対応するドメインテーブルを追加する。

**追加するテーブル（11 テーブル）:**

| グループ | テーブル |
|---|---|
| シナリオ | `scenarios`, `scenario_steps`, `scenario_enrollments` |
| 配信 | `broadcasts` |
| リマインダ | `reminders`, `reminder_steps`, `reminder_enrollments`, `reminder_deliveries` |
| タグ | `tags`, `tag_assignments` |

> カラム定義は `docs/phase3/phase3_design.md` §4.2 を参照。
> line-harness との命名差分は `docs/phase3/phase3_design.md` §4.3 を参照。

**追加するファイル:**
- `backend/app/db/models.py` に追記
- `backend/app/db/migrations/versions/002_workload_tables.py`

**テスト:**
- `backend/tests/test_db_models.py` に追記

**完了条件:**
- `alembic upgrade head` で全テーブルが作成される
- インデックスが正しく作成されている
- UNIQUE 制約が機能する（`scenario_steps` の `scenario_id + step_order`、`reminder_deliveries` の `enrollment_id + reminder_step_id`）
- FK 制約が機能する（`PRAGMA foreign_keys=ON` で検証）

---

## Task 4: Repository 層の実装

**作業:** 各ドメインの CRUD 操作を repository クラスに集約する。

**追加するファイル:**

| ファイル | 責務 |
|---|---|
| `backend/app/db/repositories/__init__.py` | |
| `backend/app/db/repositories/execution_repo.py` | execution_plans / execution_results / step_results の CRUD |
| `backend/app/db/repositories/scenario_repo.py` | scenarios / scenario_steps / scenario_enrollments の CRUD |
| `backend/app/db/repositories/broadcast_repo.py` | broadcasts の CRUD |
| `backend/app/db/repositories/reminder_repo.py` | reminders / reminder_steps / reminder_enrollments / reminder_deliveries の CRUD |
| `backend/app/db/repositories/tag_repo.py` | tags / tag_assignments の CRUD（UPSERT 対応） |

**設計方針:**
- 各 repository は DB セッションを引数で受け取る（DI）
- Pydantic モデルと ORM モデルの変換ロジックはここに置く
- ビジネスロジックは置かない（repository は純粋なデータアクセス層）

**完了条件:**
- 各 repository の主要メソッドにユニットテストがある
- tags の UPSERT（存在すればスキップ、なければ INSERT）が動作する
- broadcasts の status フィルタ検索ができる

---

## Task 5: ExecutionPlan の永続化

**作業:** `POST /api/plan` で生成した ExecutionPlan を DB に保存する。

**変更するファイル:**
- `backend/app/execution/execution_planner.py` — plan 生成後に `execution_repo.save_plan()` を呼ぶ
- `backend/app/api/routes_plan.py` — DB セッションを Depends で注入

**追加する API:**

| エンドポイント | 説明 |
|---|---|
| `GET /api/plans` | 保存済み plan 一覧 |
| `GET /api/plans/{plan_id}` | plan 詳細 |

**完了条件:**
- `POST /api/plan` で `execution_plans` にレコードが作成される
- `GET /api/plans` で一覧が返る
- `GET /api/plans/{plan_id}` で詳細が返る
- 既存の plan → dry-run → execute フローが壊れていない

---

## Task 6: DB Connector の実装

**作業:** Phase 2.5 の mock connector を進化させ、DB にドメインレコードを書き込む connector を追加する。

**追加するファイル:**
- `backend/app/connectors/db_line_connector.py`

**mock connector は残す** — テスト用途で引き続き使用する。connector registry の切替で選択。

**実装内容:**

| workload kind | connector が DB に書く内容 |
|---|---|
| `tag.assign` | `tags` に UPSERT + `tag_assignments` に INSERT |
| `broadcast.schedule` | `broadcasts` に INSERT（**status=scheduled**） |
| `scenario.create` | `scenarios` + `scenario_steps` に INSERT |
| `scenario.start` | `scenario_enrollments` に INSERT（**status=active**） |
| `reminder.create` | `reminders` + `reminder_steps` に INSERT |

**dry_run 時:**
- DB に書き込まない
- 「何が書き込まれるか」のプレビューを dict で返す

**テスト:**
- `backend/tests/test_db_connector.py`

**完了条件:**
- 各 workload kind の execute で対応テーブルにレコードが作成される
- dry_run では DB にレコードが作成されない
- broadcasts は status=scheduled で止まる（sending/sent にしない）
- scenario_enrollments は status=active で止まる（step 進行しない）

---

## Task 7: ExecutionResult の永続化

**作業:** WorkloadRunner の実行結果を DB に保存する。

**変更するファイル:**
- `backend/app/execution/workload_runner.py` — run() 完了後に結果を保存
- `backend/app/api/routes_execute.py` — DB セッション注入

**実装内容:**
- `execution_results` + `step_results` を INSERT
- `execution_plans.status` を `executing → completed / failed` に UPDATE
- 失敗時もエラー情報を保存する（成功 step + 失敗 step の両方を記録）

**テスト:**
- `backend/tests/test_execution_persistence.py`

**完了条件:**
- execute 後に `execution_results` にレコードが作成される
- step ごとに `step_results` にレコードが作成される
- `execution_plans.status` が正しく遷移する
- 失敗時にもレコードが保存される

---

## Task 8: 実行履歴照会 API

**作業:** 実行履歴を照会するエンドポイントを追加する。

**追加するファイル:**
- `backend/app/api/routes_history.py`

**エンドポイント:**

| エンドポイント | 説明 |
|---|---|
| `GET /api/executions` | 実行履歴一覧（ページネーション: `?limit=20&offset=0`） |
| `GET /api/executions/{execution_id}` | 実行詳細（step_results 含む） |

> レスポンス例は `docs/phase3/phase3_design.md` §8.3 を参照。

**テスト:**
- `backend/tests/test_history_api.py`

**完了条件:**
- 一覧が返る（ページネーション動作）
- execution_id で詳細が返る
- 存在しない execution_id で 404 が返る
- OpenAPI ドキュメントに反映される

---

## Task 9: テストの追加と回帰確認

**9.1 回帰テスト（最優先）**

| テストファイル | 内容 |
|---|---|
| `test_existing_convert.py` | 既存 `/api/convert` の回帰（維持） |
| `test_existing_phase25.py` | Phase 2.5 の plan / dry-run / execute の回帰（**新規**） |

Phase 2.5 の回帰テストは **mock connector を使う** 状態で確認する。DB connector 導入で Phase 2.5 のテストが壊れないことを保証する。

**9.2 DB モデルテスト** — `test_db_models.py`
- 全テーブルの CRUD
- FK 制約の動作
- UNIQUE 制約の動作
- status カラムの値域

**9.3 DB Connector テスト** — `test_db_connector.py`
- 5 workload kind すべてで DB にレコードが作成される
- dry_run で DB にレコードが作成されない
- status の初期値が正しい

**9.4 永続化テスト** — `test_execution_persistence.py`
- ExecutionPlan が DB に保存・取得できる
- ExecutionResult + StepResult が DB に保存・取得できる
- execution_plans.status の遷移

**9.5 履歴 API テスト** — `test_history_api.py`
- GET /api/executions で一覧が返る
- GET /api/executions/{id} で詳細が返る
- 存在しない ID で 404

> テストの記述ルールは `docs/test-instruction-template.md` に従うこと。

**完了条件:**
- 全テストが通る
- 回帰テスト（Phase 1 + Phase 2.5）が通る
- `tests/evidence/` にエビデンスが保存されている

---

## Task 10: フロントエンド / デモ導線の更新

**作業:** 既存のデモ導線に実行履歴表示を追加する。

- execute 後に「実行履歴を見る」リンクを表示
- 実行履歴一覧（GET /api/executions）
- 実行詳細（step ごとの結果）

**完了条件:**
- 「自然文 → 業務定義 → 実行計画 → 実行 → 履歴確認」の流れがブラウザ上で確認できる

---

## Task 11: README / docs の更新

**作業:**
- README.md に Phase 3 の説明を追加
- アーキテクチャ図を更新（DB 層を含める）
- `docs/README_architecture.md` に Phase 3 の設計補足

**完了条件:**
- README に Phase 3 の説明がある
- アーキテクチャ図に DB 層が含まれている

---

## 実装順序

```
 1. DB 基盤の構築 + conftest.py（Task 1）
 2. 実行管理テーブル（Task 2）
 3. workload ドメインテーブル（Task 3）
 4. Repository 層（Task 4）
 5. ExecutionPlan の永続化（Task 5）
 6. DB Connector の実装（Task 6）
 7. ExecutionResult の永続化（Task 7）
 8. 実行履歴照会 API（Task 8）
 9. テスト追加と回帰確認（Task 9）— 回帰テストを最優先
10. デモ導線更新（Task 10）
11. README / docs 更新（Task 11）
```

---

## 検証手順（Phase 3 完了時に実行）

```bash
# 1. マイグレーション正方向
cd backend && alembic upgrade head

# 2. マイグレーション逆方向
cd backend && alembic downgrade base

# 3. 再度正方向（往復確認）
cd backend && alembic upgrade head

# 4. 既存テスト全件 PASS
cd backend && pytest tests/test_existing_convert.py tests/test_existing_phase25.py -v

# 5. 新規テスト全件 PASS
cd backend && pytest tests/test_db_models.py tests/test_db_connector.py tests/test_execution_persistence.py tests/test_history_api.py -v

# 6. E2E フロー確認
# POST /api/plan → GET /api/plans → POST /api/execute → GET /api/executions

# 7. エビデンス保存
cd backend && pytest tests/ -v > tests/evidence/phase3_test_result.txt
```

---

## 絶対に避けるべきこと

1. Agent 層（`backend/app/agent/`）のコードを変更する
2. Phase 2.5 の既存 API の振る舞いを壊す（レスポンス形式変更等）
3. Cron / Worker / 非同期ジョブキューを導入する（→ Phase 4）
4. broadcasts を status=sent まで進める（→ Phase 4）
5. scenario_enrollments の step 進行を実装する（→ Phase 4）
6. 本番 LINE API を叩く connector を実装する（→ Phase 4）
7. Alembic マイグレーションなしにテーブルを追加する
8. conftest.py 以外の場所でテスト DB 設定を散在させる
9. Pydantic スキーマと ORM モデルを混在させる（変換は repository 層で行う）
