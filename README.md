# Agentic BizFlow

## 1. タイトル & 概要

自然文の業務手順を、実行可能な業務定義（JSON）に変換する Agentic Architecture 実装例です。

## 2. 解決したい課題

企業の業務手順は自然文で記載されることが多く、解釈が担当者依存になりやすいため、曖昧さ・属人化・自動化困難が同時に発生します。  
この状態は、企業システムでの再利用性や監査可能性を下げ、運用品質のばらつきを生みます。

## 3. ソリューション概要

Agentic BizFlow は単一プロンプトで一括生成する方式ではなく、Reader → Planner → Generator の段階処理で意味を構造化します。  
さらに Validator による検証と差し戻しを組み込み、自然文から実行可能な業務定義（JSON）へ変換します。

## 4. アーキテクチャ概要

バックエンドは Cloud Run 上で動作し、各エージェントが実行時に Vertex AI（Gemini）を呼び出して、業務定義 JSON と実行メタ情報を返します。

```mermaid
flowchart TB
  UI[Frontend LIFF] -->|POST api convert| API[FastAPI]
  API --> ORCH[Orchestrator]

  subgraph Agents
    R[ReaderAgent] --> P[PlannerAgent]
    P --> V[ValidatorAgent]
    V -->|issues| P
    V --> G[GeneratorAgent]
  end

  ORCH --> R
  ORCH --> P
  ORCH --> V
  ORCH --> G

  subgraph Preprocessors
    S[Text Splitter + Action Filter]
    E[Entity Extractor]
    RI[Role Inference]
  end

  R --> S
  R --> E
  P --> RI
  G --> OUT[BusinessDefinition JSON]
  V --> META[meta and agent logs]
```

設計補足は `docs/README_architecture.md` に整理しています。

## 5. Agentic Flow の説明

- Reader: 業務文を読解し、登場人物・操作・条件などの意味構造を抽出します。
- Planner: 抽出結果をもとに、役割、手順、承認に関わるタスク構造を推論します。
- Generator: 検証済みの情報のみを使って実行可能な業務定義（JSON）を生成します。
- Validator: `issues` を返した場合は Planner に差し戻し、再計画後に再検証します。

上記エージェントは実行時に Vertex AI（Gemini）を呼び出して処理します。

## 6. LLM / Vertex AI 利用

- Provider: Vertex AI
- Model: Gemini 2.0 Flash
- 実行環境: Cloud Run
- `meta.llm.reader.used` / `meta.llm.planner.used` / `meta.llm.generator.used` が `true` となる実行パスで動作します。
- モックやスタブではなく、Vertex AI への実呼び出しです。

## 7. デモ例

入力例: 「申請者が申請書を提出し、上長が確認する。不備があれば差し戻し、問題なければ経理へ回付する。」  
出力では、役割（申請者・上長・経理）、手順、条件分岐、通知先を持つ業務定義構造が生成されます。

## 8. 信頼性・設計上の工夫

- LLM 呼び出しに失敗した場合は、Reader/Planner は抽出済み情報で継続し、Generator は既定値へフォールバックします。
- Validator が `issues` を検出した場合のみ再試行し、上限付きの制御で安定動作させます。
- 最終出力は Pydantic スキーマ検証を通すため、業務定義 JSON の構造破綻を防止できます。

## 9. ハッカソンとの関連

本プロジェクトは Google Cloud Japan AI Hackathon Vol.4 向けに作成しました。  
Cloud Run と Vertex AI（Gemini）を用いて、企業業務への適用を前提に設計しています。

## 10. Phase 2.5: Workload Execution（実装済み）

Phase 2.5 では、GeneratorAgent が出力する BusinessDefinition の「その先」を実装しました。

### Workload Catalog（5 種類）

`tag.assign` / `broadcast.schedule` / `scenario.create` / `scenario.start` / `reminder.create`

### 設計の特徴

- **3 層分離**: Agent 層（変更なし）→ Executor 層 → Connector 層
- **dry-run**: 副作用なしで実行計画をプレビュー可能
- **承認フロー**: `broadcast.schedule` は常に承認必須

詳細は [`docs/phase2.5/phase2_5_design.md`](docs/phase2.5/phase2_5_design.md) を参照。

## 11. Phase 3: Stateful Execution Platform（実装済み）

Phase 3 では、メモリ上の一時オブジェクトだった実行計画・実行結果を DB に永続化し、「状態を持つ実行基盤」に拡張しました。

### 追加アーキテクチャ

```mermaid
flowchart TB
    UI[Frontend / API Client] --> API[FastAPI]

    API --> CONVERT[POST /api/convert]
    API --> PLAN_EP[POST /api/plan]
    API --> DRYRUN_EP[POST /api/dry-run]
    API --> EXEC_EP[POST /api/execute]
    API --> HISTORY_EP[GET /api/executions]

    CONVERT --> ORCH[Orchestrator]
    ORCH --> BD[BusinessDefinition]

    PLAN_EP --> EP[ExecutionPlanner]
    BD --> EP
    EP --> PLAN[ExecutionPlan]
    EP --> DB_PLAN[(execution_plans)]

    DRYRUN_EP --> WR_DRY[WorkloadRunner dry_run=True]
    PLAN --> WR_DRY
    WR_DRY --> PREVIEW[DryRunPreview]

    EXEC_EP --> WR[WorkloadRunner dry_run=False]
    PLAN --> WR
    WR --> CONN[DB Connector]
    CONN --> DB_DOMAIN[(scenarios / broadcasts / reminders / tags)]
    WR --> DB_RESULT[(execution_results + step_results)]

    HISTORY_EP --> DB_RESULT
```

### Phase 3 で解決した課題

| 課題 | Phase 2.5 | Phase 3 |
|---|---|---|
| 実行計画の保存 | メモリ上のみ | DB に保存し後から参照可能 |
| 実行結果の保存 | レスポンスで返すだけ | DB に履歴として蓄積 |
| workload の状態管理 | mock が即座に成功を返す | DB 上で状態遷移 |
| 実行の追跡 | なし | API で実行履歴を照会可能 |

### 追加 API エンドポイント

| エンドポイント | 処理 |
|---|---|
| `POST /api/plan` | BusinessDefinition → ExecutionPlan（DB 保存） |
| `POST /api/dry-run` | 副作用なしのプレビュー |
| `POST /api/execute` | DB Connector による本実行（結果を DB 保存） |
| `GET /api/plans` | 保存済み plan 一覧 |
| `GET /api/plans/{plan_id}` | plan 詳細 |
| `GET /api/executions` | 実行履歴一覧 |
| `GET /api/executions/{execution_id}` | 実行詳細（step_results 含む） |

### DB 構成

SQLAlchemy + Alembic を使用。開発環境は SQLite、本番は `DATABASE_URL` で切替可能。

**実行管理テーブル:**
- `execution_plans` — 実行計画の永続化
- `execution_results` — 実行結果の永続化
- `step_results` — ステップごとの実行結果

**workload ドメインテーブル:**
- `scenarios` / `scenario_steps` / `scenario_enrollments` — ステップ配信シナリオ
- `broadcasts` — 一斉配信（status=scheduled で登録）
- `reminders` / `reminder_steps` / `reminder_enrollments` / `reminder_deliveries` — リマインダー
- `tags` / `tag_assignments` — タグ管理

### 設計の特徴

- **Agent 層は変更なし**: 既存の Reader → Planner → Validator → Generator パイプラインはそのまま維持
- **DB Connector**: mock connector を DB 書き込み connector に進化させ、実行結果がドメインテーブルに永続化される
- **状態遷移**: execution_plans.status が created → executing → completed/failed と遷移
- **原子性**: connector 内は flush のみ、route レベルで commit し、全 step の一貫性を保証

詳細は [`docs/phase3/phase3_design.md`](docs/phase3/phase3_design.md) を参照。

## 12. Phase 4: Async Execution Engine（実装済み）

Phase 4 では、Phase 3 で DB に「登録」された業務オブジェクトをバックグラウンドで安全に消化する仕組みを構築しました。

### 追加機能

- **Scheduler / Worker**: APScheduler で 5 分間隔の定期処理（scenario step 配信 / broadcast 送信 / reminder 配信）
- **承認ワークフロー永続化**: `approval_requests` テーブルで承認状態を管理、approve / reject API
- **冪等性チェック**: `processed_idempotency_keys` テーブルで二重実行を防止
- **監査ログ**: `execution_audit_logs` テーブルで全操作の証跡を記録
- **配信ウィンドウ**: 9:00-23:00 JST の配信制御
- **再試行**: retry_count / max_retries による失敗再試行（指数バックオフ）
- **Connector Registry**: 環境変数 `LINE_CONNECTOR_MODE` で mock / db / live を切替可能
- **LINE Connector 枠組み**: 本番 LINE Messaging API 接続の準備

### 追加 API エンドポイント

| エンドポイント | 処理 |
|---|---|
| `GET /api/approvals` | 承認リクエスト一覧（status フィルタ対応） |
| `GET /api/approvals/{id}` | 承認リクエスト詳細 |
| `POST /api/approvals/{id}/approve` | 承認 |
| `POST /api/approvals/{id}/reject` | 却下 |

### 状態遷移

- **broadcasts**: scheduled → sending → sent（Scheduler が消化）
- **scenario_enrollments**: active → step 進行 → completed（Worker が配信）
- **reminder_enrollments**: active → 全 step 配信 → completed（Worker が配信）

詳細は [`docs/phase4/phase4_design.md`](docs/phase4/phase4_design.md) を参照。

## 13. Phase 5: Multi-Domain Execution Platform（実装済み）

Phase 5 では、LINE 以外の業務ドメインにも同じオーケストレーション層で対応できる共通基盤に拡張しました。

### 追加機能

- **Workload Kind Registry**: workload kind を動的に登録・検索。ドメイン別フィルタ、エイリアス解決に対応
- **Domain Module 構造**: `domains/line/`, `domains/email/` にドメイン固有コードをパッケージ化
- **後方互換**: 旧 kind（`tag.assign` 等）は `line.tag.assign` のエイリアスとして動作
- **Email ドメイン**: Email connector + Worker（`email.broadcast.schedule`, `email.template.create`）
- **Cross-domain ExecutionPlan**: 1 つの plan に LINE + Email の step が混在可能
- **Domain 設定テーブル**: `domain_configs` でドメインの有効/無効・設定を管理
- **ドメイン追加テンプレート**: `domains/_template/` をコピーして新ドメインを追加可能

### 追加 API エンドポイント

| エンドポイント | 処理 |
|---|---|
| `GET /api/domains` | 有効なドメイン一覧 |
| `GET /api/domains/{domain}` | ドメイン詳細 |
| `PUT /api/domains/{domain}/config` | ドメイン設定更新 |
| `POST /api/domains/{domain}/enable` | ドメイン有効化 |
| `POST /api/domains/{domain}/disable` | ドメイン無効化 |
| `GET /api/workload-kinds` | 全 workload kind 一覧 |

詳細は [`docs/phase5/phase5_design.md`](docs/phase5/phase5_design.md) を参照。

## 14. Phase 6: Demo-Ready Integration（実装済み）

Phase 6 では、これまでの全機能を横断的に可視化するデモ基盤を構築しました。

### 追加機能

- **Workload 状態 API**: シナリオ・配信・リマインダー・タグの統合サマリー
- **Worker 状態 API**: Scheduler 各 Worker の最終実行状態
- **管理 UI（Streamlit）**: Workload サマリー / 実行履歴 / 承認管理 / Worker 状態 / ドメイン管理 / 業務文章変換
- **LINE live connector 拡張**: tag.assign の LINE API 呼び出し枠組み

### 追加 API エンドポイント

| エンドポイント | 処理 |
|---|---|
| `GET /api/workloads/summary` | Workload 統合サマリー |
| `GET /api/workloads/scenarios` | シナリオ + enrollment 状態 |
| `GET /api/workloads/broadcasts` | 配信ステータス別カウント |
| `GET /api/workloads/reminders` | リマインダー + enrollment 状態 |
| `GET /api/workers/status` | Worker 最終実行状態 |

### 管理 UI の起動

```bash
pip install streamlit requests
streamlit run admin/app.py
```

詳細は [`docs/phase6/phase6_design.md`](docs/phase6/phase6_design.md) を参照。

## 15. 今後の拡張

- Cloud Scheduler + Cloud Run Jobs への移行
- POS / CRM / ERP ドメインの connector 追加（`domains/_template/` からコピー）
- automations / scoring / notification_rules
- マルチテナント認証
- 社内業務自動化への展開
