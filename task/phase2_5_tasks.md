# Phase 2.5: Workload Execution — 実装タスク

> **設計の参照先:** [`docs/phase2.5/phase2_5_roadmap.md`](../docs/phase2.5/phase2_5_roadmap.md)
> **最上位ルール:** `AGENTS.md`
> **実務ガイド:** `CLAUDE.md`

---

## 前提

- `backend/app/agent/` 配下のファイルは変更禁止
- 既存の `POST /api/convert` エンドポイントが壊れていないことをテストで常に保証する
- AGENTS.md §6（日本語 docstring ①〜⑤）を全ファイルで満たすこと
- テスト完了時は `tests/evidence/` にエビデンスを保存すること

---

## Task 1: 設計ドキュメントの作成

**作業:** `docs/phase2.5/phase2_5_design.md` を作成する。

**内容:**
- Phase 2.5 の目的と範囲
- BusinessDefinition と ExecutionPlan の責務境界
- Workload Catalog の一覧と各 workload の意味
- approval / dry-run / connector adapter の責務定義
- アーキテクチャの Mermaid 図

> 設計の元ネタは [`docs/phase2.5/phase2_5_roadmap.md`](../docs/phase2.5/phase2_5_roadmap.md) §2〜§5 を参照。

**完了条件:**
- `docs/phase2.5/phase2_5_design.md` が存在する
- 責務境界と Workload Catalog が明記されている
- Mermaid 図が含まれている

---

## Task 2: Pydantic スキーマの追加

**作業:** `backend/app/schemas/` に以下の 3 ファイルを追加する。

- `execution_plan.py` — ExecutionPlan, ExecutionStep, ApprovalPolicy
- `execution_result.py` — ExecutionResult, StepResult, DryRunPreview
- `connector_capability.py` — ConnectorCapability

> フィールド定義は [`docs/phase2.5/phase2_5_roadmap.md`](../docs/phase2.5/phase2_5_roadmap.md) §5 を参照。

**完了条件:**
- 各モデルに日本語 docstring がある
- import が通る
- バリデーションのユニットテストが追加されている

---

## Task 3: Connector Adapter の抽象化

**作業:** `backend/app/connectors/` に以下を追加する。

- `base_connector.py` — 抽象基底クラス（execute / dry_run / capabilities）
- `mock_line_connector.py` — 5 種類の workload kind に対応する mock 実装
- `mock_internal_job_connector.py` — 内部ジョブキュー用 mock

**完了条件:**
- WorkloadRunner は BaseConnector のインターフェースのみに依存する
- mock connector で全 5 workload kind の疎通ができる
- capabilities() が正しい action リストを返す

---

## Task 4: ExecutionPlanner の実装

**作業:** `backend/app/execution/execution_planner.py` を作成する。

**実装するメソッド:**
- `plan(definition, dry_run=True) -> ExecutionPlan`

**判定ロジック:**

> 変換ルール・承認判定・risk_level 判定は [`docs/phase2.5/phase2_5_roadmap.md`](../docs/phase2.5/phase2_5_roadmap.md) §3 を参照。

- BusinessDefinition の内容から workload kind を判定する
- 承認要否を step ごとに判定する
- risk_level を plan 全体で判定する
- idempotency_key を各 step に UUID v4 で付与する

**完了条件:**
- BusinessDefinition → ExecutionPlan の変換が動作する
- 少なくとも以下 6 パターンのテストがある:
  1. タグ付与のみ
  2. 一斉配信予約
  3. シナリオ作成
  4. リマインダー作成（複数ステップ）
  5. 複合指示（タグ + シナリオ）
  6. 承認必須ケースの判定

---

## Task 5: WorkloadRunner の実装

**作業:** `backend/app/execution/workload_runner.py` を作成する。

**実装するメソッド:**
- `run(plan) -> ExecutionResult`

**実行フロー:**
- `dry_run=True` → connector.dry_run() を呼び、DryRunPreview を返す
- `requires_approval=True` で未承認 → status=blocked を返す
- 本実行 → connector.execute() を呼び、StepResult を集約する
- step 失敗時は後続 step を skipped にする

**connector の解決:**
- connector registry（dict）から connector 名で解決する。具象実装を直接 import しない

**完了条件:**
- dry-run と本実行の分岐が正しく動作する
- step ごとの結果が ExecutionResult に格納される
- 失敗時にどの step で止まったか分かる
- 承認必須 step が未承認時に blocked を返す

---

## Task 6: 承認フローの最低限実装

**作業:** `backend/app/execution/approval.py` を作成する。

**スコープ:**
- 承認の永続化やワークフローエンジンは対象外
- `requires_approval=True` の step が即実行されないことを保証する
- API レスポンスに `approval_required: true` を含める

**実装するメソッド:**
- `check_approval(plan) -> tuple[bool, list[str]]`

**完了条件:**
- broadcast.schedule を含む plan で承認必須と判定される
- 承認なしで execute を呼ぶと blocked が返る
- dry-run は承認なしでも常に実行可能

---

## Task 7: FastAPI エンドポイントの追加

**作業:** 以下の 3 エンドポイントを追加する。**既存の `POST /api/convert` は触らない。**

| エンドポイント | Request | Response | 処理 |
|---|---|---|---|
| `POST /api/plan` | `{ definition_id, definition }` | ExecutionPlan | ExecutionPlanner.plan() |
| `POST /api/dry-run` | `{ plan_id }` or `{ plan }` | DryRunPreview | WorkloadRunner.run(dry_run=True) |
| `POST /api/execute` | `{ plan_id, approved }` | ExecutionResult | WorkloadRunner.run(dry_run=False) |

> レスポンス例は [`docs/phase2.5/phase2_5_roadmap.md`](../docs/phase2.5/phase2_5_roadmap.md) §6 を参照。

**完了条件:**
- OpenAPI ドキュメントに反映される
- curl で一連のフロー（convert → plan → dry-run → execute）が確認できる
- 既存の `/api/convert` が壊れていないこと

---

## Task 8: ログ・監査情報の整備

**作業:**
- 実行単位に `execution_id` を付与する
- step ごとに connector 名・action 名・status・error_code を保持する
- Python の logging モジュールで構造化ログを出力する
- **生の LLM 応答や機微情報は保存しない**

**完了条件:**
- ログ出力の粒度が統一されている
- execution_id で実行を追跡可能

---

## Task 9: テストの追加

**9.1 回帰テスト（最優先）**
- `test_existing_convert.py`: 既存 `/api/convert` が壊れていないことの確認

**9.2 スキーマテスト**
- ExecutionPlan のバリデーション
- ExecutionStep の kind が不正な場合のエラー
- ExecutionResult の status 遷移

**9.3 ExecutionPlanner テスト**
- タグ付与のみ / 一斉配信予約 / シナリオ作成 / リマインダー作成（複数ステップ）/ 複合指示 / 承認必須ケース / risk_level 判定

**9.4 WorkloadRunner テスト**
- dry-run が副作用を起こさないこと
- 本実行で connector.execute() が呼ばれること
- 承認必須時に execute が即実行されないこと
- step 失敗時に後続が skipped になること
- idempotency_key が各 step に付与されていること

**9.5 Connector テスト**
- mock connector の全 action が正常応答すること
- capabilities() の返り値が正しいこと

> テストの記述ルールは `docs/test-instruction-template.md` に従うこと。

**完了条件:**
- 全テストが通る
- 既存 `/api/convert` の回帰テストが通る
- `tests/evidence/` にエビデンスが保存されている

---

## Task 10: フロントエンド / デモ導線の最小更新

**作業:** 既存のフロントエンドに最小限の変更を加え、デモできる状態にする。

- BusinessDefinition 表示の後に「実行計画を生成」ボタンを追加
- ExecutionPlan を表示する
- 「dry-run」ボタンで DryRunPreview を表示する
- approval 必須時は警告を表示する
- 「実行」ボタンは mock connector のみ有効にする

**完了条件:**
- 「自然文 → 業務定義 → 実行計画 → dry-run 結果」の流れがブラウザ上で確認できる

---

## Task 11: README / docs の更新

**作業:**
- README.md の「10. 今後の拡張」セクションに Phase 2.5 の内容を追加
- アーキテクチャ図を更新
- `docs/README_architecture.md` に Phase 2.5 の設計補足を追加

**完了条件:**
- README に Phase 2.5 の説明がある
- アーキテクチャ図が更新されている

---

## 実装順序

```
 1. 設計ドキュメント作成（Task 1）
 2. Pydantic スキーマ追加（Task 2）
 3. Connector Adapter 抽象化 + mock 実装（Task 3）
 4. ExecutionPlanner 実装（Task 4）
 5. WorkloadRunner 実装（Task 5）
 6. 承認フロー実装（Task 6）
 7. FastAPI エンドポイント追加（Task 7）
 8. ログ整備（Task 8）
 9. テスト追加（Task 9）— 回帰テストを最優先
10. デモ導線更新（Task 10）
11. README / docs 更新（Task 11）
```

---

## 絶対に避けるべきこと

1. GeneratorAgent が直接外部 API を叩く
2. PlannerAgent が外部 DB を更新する
3. ValidatorAgent が実行結果まで兼ねる
4. Orchestrator が connector ごとの実装詳細を抱える
5. dry-run と本実行の境界を曖昧にする
6. 既存の `/api/convert` エンドポイントを壊す
7. 生の LLM 出力を実行 payload にそのまま流す
