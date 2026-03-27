# Phase 6: LINE Demo & Admin UI — 実装タスク

> **設計の参照先:** `docs/phase6/phase6_design.md`
> **全体ロードマップ:** `docs/roadmap-phase6-to-phase9.md`
> **最上位ルール:** `AGENTS.md`
> **実務ガイド:** `CLAUDE.md`

---

## 前提

- Phase 2.5〜5 が実装済みであること（20 テーブル、全 API、Scheduler / Worker / 承認 / 冪等性 / 監査 / Multi-domain）
- `backend/app/agent/` 配下のファイルは変更禁止
- 既存の全 API（Phase 1〜5）が壊れていないことをテストで常に保証する
- **Phase 6 では新テーブルを追加しない**（既存 20 テーブルのみ使用）
- AGENTS.md §6（日本語 docstring ①〜⑤）を全ファイルで満たすこと
- テスト完了時は `tests/evidence/` にエビデンスを保存すること

---

## Task 1: デモシナリオの固定

**作業:** Phase 6 のデモで使う 1 本の完成ストーリーを手順書として固定する。

**追加・変更するファイル:**
- `backend/scripts/seed_demo.py` — デモ前の状態確認 + デモ後の期待状態を定義
- `docs/demo-guide.md` — 管理 UI 操作手順を追加

> デモシナリオの詳細は `docs/phase6/phase6_design.md` §2 を参照。

**デモストーリー:**

```
自然文: 「セミナー参加者にVIPタグをつけて、明日10時にセール告知を一斉配信して、セミナー3日前と前日にリマインドを送って」
  ↓ convert → plan → dry-run → 承認 → execute → Scheduler消化 → 履歴確認
```

**seed_demo.py の内容:**
- DB リセット（dev.db 削除 + alembic upgrade head）
- デモ後の期待レコード数をアサートするヘルパー関数

**完了条件:**
- seed_demo.py を実行後、API のみでデモシナリオが一気通貫で動く
- demo-guide.md にデモの完全手順（API + 管理 UI 両方）が記載されている

---

## Task 2: Workload 状態確認 API の追加

**作業:** 管理 UI から workload の状態を確認するための API を追加する。

**追加するファイル:**
- `backend/app/api/routes_workload_status.py`

**エンドポイント:**

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `GET /api/workloads/scenarios` | GET | scenarios 一覧 + enrollment 数 + status 別件数 |
| `GET /api/workloads/broadcasts` | GET | broadcasts の status 別件数（draft / scheduled / sending / sent / failed） |
| `GET /api/workloads/reminders` | GET | reminders 一覧 + enrollment 数 + 配信済み step 数 |
| `GET /api/workloads/summary` | GET | 全 workload 種別の統合サマリ |

**レスポンス例（summary）:**

```json
{
  "scenarios": {"total": 3, "active_enrollments": 12, "completed_enrollments": 45},
  "broadcasts": {"draft": 1, "scheduled": 2, "sending": 0, "sent": 15, "failed": 0},
  "reminders": {"total": 2, "active_enrollments": 8, "completed_enrollments": 20},
  "tags": {"total": 5, "total_assignments": 132}
}
```

**テスト:** `backend/tests/test_workload_status_api.py`

**完了条件:**
- 各エンドポイントが正しいサマリを返す
- workload が 0 件でも空のレスポンスが返る（エラーにならない）
- OpenAPI ドキュメントに反映される

---

## Task 3: Worker 状態確認 API の追加

**作業:** Scheduler / Worker の稼働状態を確認する API を追加する。

**追加するファイル:**
- `backend/app/api/routes_worker_status.py`

**エンドポイント:**

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `GET /api/workers/status` | GET | 各 Worker の最新実行状態（worker_task_logs から取得） |

**レスポンス例:**

```json
{
  "workers": [
    {
      "task_name": "process_step_deliveries",
      "last_run": "2026-03-26T15:30:00Z",
      "status": "completed",
      "processed_count": 5,
      "error_count": 0
    },
    {
      "task_name": "process_scheduled_broadcasts",
      "last_run": "2026-03-26T15:30:00Z",
      "status": "completed",
      "processed_count": 1,
      "error_count": 0
    },
    {
      "task_name": "process_reminder_deliveries",
      "last_run": "2026-03-26T15:30:00Z",
      "status": "completed",
      "processed_count": 3,
      "error_count": 0
    }
  ],
  "scheduler_enabled": true
}
```

**テスト:** `backend/tests/test_worker_status_api.py`

**完了条件:**
- Worker の最新状態が返る
- worker_task_logs が空でも正常にレスポンスが返る
- scheduler_enabled が環境変数 SCHEDULER_ENABLED と一致する

---

## Task 4: 管理 UI（Streamlit）の実装

**作業:** Streamlit で管理 UI を実装する。

> 画面構成は `docs/phase6/phase6_design.md` §3.2 を参照。

**追加するファイル:**

```
admin/
  app.py                    ← エントリポイント（サイドバーナビゲーション）
  pages/
    01_convert.py            ← 自然文入力 → BusinessDefinition → Plan 生成
    02_plans.py              ← Plan 一覧 / 詳細 / dry-run / 実行ボタン
    03_approvals.py          ← 承認一覧 / 承認・却下ボタン
    04_executions.py         ← 実行履歴一覧 / 詳細（step_results）
    05_workloads.py          ← Workload 状態（scenarios / broadcasts / reminders / tags）
    06_workers.py            ← Worker 状態
  requirements.txt           ← streamlit, requests
  .streamlit/config.toml     ← テーマ設定
```

**各画面の仕様:**

| 画面 | 操作 | 呼び出す API |
|---|---|---|
| 自然文入力 | テキスト入力 → 変換 → Plan 生成 | POST /api/convert → POST /api/plan |
| Plan 一覧 | 一覧表示 + 状態バッジ + 詳細リンク | GET /api/plans |
| Plan 詳細 | step 列表示 + 承認要否表示 + dry-run ボタン + 実行ボタン | GET /api/plans/{id}, POST /api/dry-run, POST /api/execute |
| 承認一覧 | pending 一覧 + 承認/却下ボタン | GET /api/approvals?status=pending, POST approve/reject |
| 実行履歴 | 一覧 + 詳細（step_results の成否表示） | GET /api/executions, GET /api/executions/{id} |
| Workload 状態 | scenarios / broadcasts / reminders / tags のサマリ | GET /api/workloads/summary |
| Worker 状態 | 各 Worker の最新実行状態 | GET /api/workers/status |

**設計方針:**
- 全ての操作は backend API 経由（DB 直接参照しない）
- API の base URL は環境変数 `API_BASE_URL` で設定（デフォルト: `http://localhost:8080`）
- 各画面で loading / empty / error 状態を表示する
- 認証は Phase 9 で追加するため、Phase 6 では不要

**完了条件:**
- `streamlit run admin/app.py` で全画面が表示される
- 自然文入力 → Plan → dry-run → 承認 → Execute → 履歴確認が UI 上で完結する
- backend が停止中でもエラーメッセージが適切に表示される

---

## Task 5: LINE Live Connector の最小接続

**作業:** LINE_CONNECTOR_MODE=live で tag.assign のみ LINE API に接続する。

> 設計は `docs/phase6/phase6_design.md` §4 を参照。

**変更するファイル:**
- `backend/app/domains/line/connector.py` — tag.assign のみ LINE API 呼び出しを追加

**実装内容:**
- `execute("line.tag.assign", inputs)` で LINE Messaging API を呼び出す + DB にも書き込む
- tag.assign 以外のアクション（broadcast.schedule 等）は DB connector にフォールバック
- `dry_run()` は LINE API を呼ばない

**環境変数:**
```
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
LINE_CONNECTOR_MODE=live   # default: db
```

**テスト:** `backend/tests/test_live_line_minimal.py`（LINE API を mock して引数を検証）

**完了条件:**
- LINE_CONNECTOR_MODE=live で tag.assign が LINE API に正しいリクエストを送る
- tag.assign 以外は DB connector にフォールバックする
- LINE_CONNECTOR_MODE=db ではこれまで通り DB のみに書き込む
- テストでは LINE API は mock され、引数とヘッダーが検証される

---

## Task 6: 外部説明資料の作成

**作業:** 外部向けの 1 ページ説明資料を作成する。

**追加するファイル:**
- `docs/external/one-pager.md`

> 構成は `docs/phase6/phase6_design.md` §5.1 を参照。

**内容:**
- 問題提起（LINE 配信の属人化）
- ソリューション（自然文 → 計画 → 承認 → 実行）
- 管理 UI のスクリーンショット
- 技術的な強み（dry-run / 承認 / 冪等性 / 監査 / Scheduler）
- 将来の展開（Email / 店舗向け集客アプリ等への拡張）

**完了条件:**
- 1 ページ資料が存在する
- 非エンジニアが読んで「何をするプロダクトか」が分かる

---

## Task 7: テストの追加と回帰確認

**7.1 回帰テスト（最優先）**

| テストファイル | 内容 |
|---|---|
| `test_existing_convert.py` | Phase 1 回帰（維持） |
| `test_existing_phase25.py` | Phase 2.5 回帰（維持） |
| `test_existing_phase3.py` | Phase 3 回帰（維持） |
| `test_existing_phase4.py` | Phase 4 回帰（維持） |
| `test_existing_phase5.py` | Phase 5 回帰（維持） |

**7.2 新規テスト**

| テストファイル | 対象 |
|---|---|
| `test_workload_status_api.py` | Workload 状態 API |
| `test_worker_status_api.py` | Worker 状態 API |
| `test_live_line_minimal.py` | LINE live connector（mock API） |

> テストの記述ルールは `docs/test-instruction-template.md` に従うこと。

**完了条件:**
- 全テストが通る
- 回帰テスト（Phase 1〜5）が通る
- `tests/evidence/` にエビデンスが保存されている

---

## Task 8: demo-guide.md の拡充

**作業:** 既存の demo-guide.md に管理 UI 経由の操作手順を追加する。

**変更するファイル:**
- `docs/demo-guide.md`

**追加する内容:**
- 管理 UI の起動手順（`streamlit run admin/app.py`）
- 管理 UI 経由のデモフロー（Task 1 のストーリーを UI 操作で）
- スクリーンショットの挿入位置（後から追加）
- LINE live connector を使った確認手順（任意）

**完了条件:**
- API 手順と管理 UI 手順の両方が記載されている
- Phase 6 のデモシナリオが完全に記述されている

---

## Task 9: README の更新

**作業:** README.md に Phase 6 の説明を追加する。

**変更するファイル:**
- `README.md` — Phase 6 セクション追加

**追加する内容:**
- Phase 6 の概要（管理 UI、デモシナリオ、live connector）
- 管理 UI の起動方法
- スクリーンショット（後から追加可能な構成で）

**完了条件:**
- README に Phase 6 の説明がある
- 管理 UI の起動手順が記載されている

---

## 実装順序

```
 1. デモシナリオの固定（Task 1）
 2. Workload 状態 API（Task 2）
 3. Worker 状態 API（Task 3）
 4. 管理 UI（Task 4）— Task 2, 3 の API を使う
 5. LINE live connector 最小接続（Task 5）
 6. 外部説明資料（Task 6）
 7. テスト追加と回帰確認（Task 7）
 8. demo-guide.md 拡充（Task 8）
 9. README 更新（Task 9）
```

---

## 検証手順（Phase 6 完了時に実行）

```bash
# 1. 既存テスト全件 PASS
cd backend && pytest tests/ -v

# 2. 新規テスト全件 PASS
cd backend && pytest tests/test_workload_status_api.py tests/test_worker_status_api.py tests/test_live_line_minimal.py -v

# 3. 管理 UI 起動確認
cd admin && streamlit run app.py

# 4. デモシナリオ一気通貫（管理 UI 経由）
#    自然文入力 → Plan → dry-run → 承認 → Execute → Scheduler 消化 → 履歴確認

# 5. LINE live connector（手動・任意）
#    LINE_CONNECTOR_MODE=live で tag.assign が LINE API に到達することを確認

# 6. エビデンス保存
cd backend && pytest tests/ -v > tests/evidence/phase6_test_result.txt
```

---

## 絶対に避けるべきこと

1. Agent 層のコードを変更する
2. 既存 API の振る舞いを壊す
3. 新テーブルを追加する（Phase 6 は既存 20 テーブルのみ）
4. LINE_CONNECTOR_MODE=live をデフォルトにする（デフォルトは db）
5. 管理 UI から DB に直接アクセスする（API 経由のみ）
6. デモのために承認フローをバイパスする
7. フロントエンド開発に時間をかけすぎる（Streamlit で最小限に）
