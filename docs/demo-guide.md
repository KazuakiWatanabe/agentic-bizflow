# Agentic BizFlow デモガイド

本ドキュメントでは、ローカル環境で Agentic BizFlow の全機能を確認する手順を説明します。

---

## 前提条件

- Python 3.11 以上
- pip
- curl（API 確認用。ブラウザのみでも可）
- Docker（フロントエンド確認時のみ。任意）

---

## 1. セットアップ

```bash
cd backend
pip install -r requirements.txt
```

### DB マイグレーション

```bash
cd backend
python -m alembic upgrade head
```

> 開発環境では SQLite（`backend/dev.db`）が自動作成されます。

---

## 2. バックエンド起動

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8080
```

> **注意:** コードを変更した場合（ブランチ切替・Phase 更新など）は、サーバーを一度停止して再起動してください。`--reload` はファイル変更を検知しますが、古いプロセスが残っていると新しいルートが認識されないことがあります。
>
> ```bash
> # Windows の場合
> taskkill /F /IM python.exe
> # 再起動
> cd backend
> python -m uvicorn app.main:app --reload --port 8080
> ```

起動後、以下の URL でアクセスできます。

| URL | 内容 |
|---|---|
| http://localhost:8080/health | ヘルスチェック（`"ok"` が返れば正常） |
| http://localhost:8080/docs | Swagger UI（全 API の一覧と実行） |
| http://localhost:8080/redoc | ReDoc（API ドキュメント） |

---

## 3. デモフロー（API）

### 3.1 業務文章を変換する

```bash
curl -s -X POST http://localhost:8080/api/convert \
  -H "Content-Type: application/json" \
  -d '{"text": "VIPタグを付与し、全員に告知メッセージを一斉配信する"}' \
  | python -m json.tool
```

レスポンスに `definition`（業務定義）、`agent_logs`（Agent ログ）、`meta`（メタ情報）が返ります。

### 3.2 実行計画を生成する

```bash
curl -s -X POST http://localhost:8080/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "definition": {
      "title": "VIPタグ付与と一斉配信",
      "tasks": [
        {
          "name": "VIPタグを付与し告知を配信",
          "steps": ["対象者にVIPタグを付与する", "全員に告知メッセージを一斉配信する"],
          "role": "担当者"
        }
      ],
      "roles": [{"name": "担当者", "responsibilities": ["タグ管理", "配信管理"]}]
    }
  }' | python -m json.tool
```

レスポンスの `plan.plan_id` を以降の手順で使います。

### 3.3 保存済み plan を確認する

```bash
# 一覧
curl -s http://localhost:8080/api/plans | python -m json.tool

# 詳細（plan_id を指定）
curl -s http://localhost:8080/api/plans/<plan_id> | python -m json.tool
```

### 3.4 dry-run（副作用なしのプレビュー）

3.2 のレスポンスで得た `plan` オブジェクト全体を渡します。

```bash
curl -s -X POST http://localhost:8080/api/dry-run \
  -H "Content-Type: application/json" \
  -d '{"plan": <3.2で取得したplanオブジェクト>}' \
  | python -m json.tool
```

DB への書き込みは発生しません。

### 3.5 本実行

```bash
curl -s -X POST http://localhost:8080/api/execute \
  -H "Content-Type: application/json" \
  -d '{"plan": <3.2で取得したplanオブジェクト>, "approved": true}' \
  | python -m json.tool
```

実行後、以下が DB に保存されます。

- `execution_results` — 実行結果
- `step_results` — ステップごとの結果
- `tags` / `tag_assignments` — タグ付与結果
- `broadcasts` — 配信予約（status=scheduled）

### 3.6 実行履歴を確認する

```bash
# 一覧
curl -s http://localhost:8080/api/executions | python -m json.tool

# 詳細（execution_id を指定）
curl -s http://localhost:8080/api/executions/<execution_id> | python -m json.tool
```

---

## 4. デモフロー（Swagger UI）

ブラウザで http://localhost:8080/docs を開くと、全 API をフォームから実行できます。

1. **POST /api/convert** を展開 → 「Try it out」→ Request body に `{"text": "VIPタグを付与し、全員に告知を配信する"}` を入力 → 「Execute」
2. レスポンスの `definition` をコピー
3. **POST /api/plan** → `{"definition": <コピーした definition>}` で実行
4. レスポンスの `plan` をコピー
5. **POST /api/dry-run** → `{"plan": <コピーした plan>}` で実行（プレビュー確認）
6. **POST /api/execute** → `{"plan": <コピーした plan>, "approved": true}` で実行
7. **GET /api/executions** → 実行履歴一覧を確認
8. **GET /api/executions/{execution_id}** → ステップごとの結果を確認

---

## 5. デモフロー（フロントエンド）

### Docker で起動する場合

```bash
cd frontend
docker build -t agentic-bizflow-frontend .
docker run --rm -p 8081:8080 \
  -e LIFF_ID="dummy" \
  -e BACKEND_BASE_URL="http://localhost:8080" \
  agentic-bizflow-frontend
```

### ブラウザで確認

1. http://localhost:8081 を開く
2. テキストエリアに業務文章を入力（デフォルトのサンプルでも可）
3. 「変換」ボタン → 業務定義・メタ情報・Agent ログが表示される
4. 「実行計画を生成」ボタン → ExecutionPlan が表示される
5. 「dry-run」ボタン → DryRunPreview が表示される
6. 「実行」ボタン → ExecutionResult が表示される
7. 「実行履歴を見る」ボタン → 実行履歴一覧パネルが表示される
8. 履歴カードをクリック → 実行詳細（step_results 含む）が表示される

> LIFF_ID が `dummy` の場合、LIFF SDK の初期化はスキップされますが、API 通信は正常に動作します。

---

## 6. DB 内容の直接確認

実行後に DB のレコードを確認する場合:

```bash
cd backend
python -c "
import sqlite3
conn = sqlite3.connect('dev.db')
cursor = conn.cursor()
tables = [
    'execution_plans', 'execution_results', 'step_results',
    'tags', 'tag_assignments',
    'scenarios', 'scenario_steps', 'scenario_enrollments',
    'broadcasts',
    'reminders', 'reminder_steps', 'reminder_enrollments', 'reminder_deliveries',
    'approval_requests', 'processed_idempotency_keys',
    'execution_audit_logs', 'worker_task_logs',
    'domain_configs',
    'email_broadcasts', 'email_templates',
    'contacts', 'contact_channels',
]
for table in tables:
    count = cursor.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(f'{table}: {count} rows')
conn.close()
"
```

---

## 7. 管理 UI（Streamlit）

バックエンド起動中に別ターミナルで:

```bash
pip install streamlit requests
streamlit run admin/app.py
```

ブラウザで http://localhost:8501 が開きます。

### 画面一覧

| 画面 | 内容 |
|---|---|
| Workload サマリー | シナリオ・配信・リマインダー・タグの統合カウント |
| 実行履歴 | 実行結果の一覧・詳細展開 |
| 承認管理 | 承認待ち一覧と承認/却下ボタン |
| Worker 状態 | Scheduler の実行ログ |
| ドメイン管理 | Workload Kind 一覧 / Domain 設定 |
| 業務文章変換 | テキスト入力 → 変換 → 計画 → dry-run → 実行の全フロー |

---

## 8. Workload 状態 API

実行後の workload の状態を確認する API:

```bash
# 統合サマリー
curl -s http://localhost:8080/api/workloads/summary | python -m json.tool

# Worker 実行状態
curl -s http://localhost:8080/api/workers/status | python -m json.tool
```

---

## 9. DB のリセット

データを全て削除して最初からやり直す場合:

```bash
cd backend
rm -f dev.db
python -m alembic upgrade head
```

---

## 10. 完成デモ（管理 UI 一気通貫）

バックエンド + Streamlit 管理 UI を同時に起動し、以下のフローを実行します。

### 準備

**ターミナル 1（バックエンド）:**
```bash
cd backend
rm -f dev.db
python -m alembic upgrade head
python -m uvicorn app.main:app --port 8080
```

**ターミナル 2（管理 UI）:**
```bash
pip install streamlit requests
streamlit run admin/app.py
```

### デモ手順

1. **管理 UI** → サイドバーで「業務文章変換」を選択
2. テキスト入力欄に以下を入力:
   ```
   セミナー参加者にVIPタグをつけて、全員にセール告知を一斉配信して
   ```
3. 「変換」ボタン → BusinessDefinition が JSON で表示される
4. 「実行計画を生成」ボタン → ExecutionPlan が表示される（tag.assign + broadcast.schedule）
5. サイドバーで「承認管理」を選択 → broadcast.schedule の承認待ちが表示される
6. 「承認」ボタンをクリック → status が approved に変わる
7. サイドバーで「業務文章変換」に戻る
8. 「Dry-run」ボタン → 副作用なしのプレビューが表示される
9. 「本実行」ボタン → ExecutionResult が表示される（2 step とも success）
10. サイドバーで「実行履歴」を選択 → 実行結果が一覧表示される
11. 実行結果を展開 → step_results（tag.assign: success, broadcast.schedule: success）が確認できる
12. サイドバーで「Workload サマリー」を選択 → tags: 1, broadcasts: scheduled 1 が確認できる

### 確認ポイント

| 確認項目 | 期待値 |
|---|---|
| execution_plans | 1 件（status=completed） |
| approval_requests | 1 件（status=approved） |
| tags | 1 件（VIP タグ） |
| tag_assignments | 1 件 |
| broadcasts | 1 件（status=scheduled） |
| execution_results | 1 件（status=success） |
| step_results | 2 件 |

---

## 全体フロー図

```
自然文（業務文章）
  │
  ▼  POST /api/convert
業務定義（BusinessDefinition JSON）
  │
  ▼  POST /api/plan
実行計画（ExecutionPlan）  ──→  GET /api/plans で一覧確認
  │
  ├─▶  POST /api/dry-run  ──→  副作用なしプレビュー
  │
  ▼  POST /api/execute (approved=true)
実行結果（ExecutionResult）
  │
  ├─→  DB: tags / broadcasts / scenarios / reminders に書き込み
  │
  ▼  GET /api/executions
実行履歴の確認
```
