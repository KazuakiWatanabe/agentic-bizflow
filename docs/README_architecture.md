> このドキュメントは Agentic BizFlow のアーキテクチャ設計詳細です。  
> README.md に掲載している Mermaid 図の正（Single Source of Truth）です。

# Agentic BizFlow

## Project Overview（プロジェクト概要）
Agentic BizFlow は、自然文で書かれた業務手順を、実行可能な業務定義（JSON）に変換する
Agentic AI の実装例です。提出/審査に必要な要素を最小構成でまとめています。

## What it does（できること）
- 日本語業務文からアクション/条件/エンティティを抽出
- 複合文を分割し、非業務的な雑談を除外
- Validator で不備を検出し、必要に応じて再計画
- Pydantic スキーマで厳格に出力を検証
- LIFF向け1画面UIで結果を可視化

## Why it’s agentic / key idea（Agenticである理由）
- Reader / Planner / Validator / Generator の明確な役割分担
- Orchestrator による順序制御とリトライ
- validation を通過しない限り出力しない
- ルールベース前処理で task 分割の再現性を向上

## Architecture（アーキテクチャ）
```mermaid
flowchart TB
  UI[Frontend (LIFF)] -->|POST /api/convert| API[FastAPI]
  API --> ORCH[Orchestrator]

  subgraph Agents
    R[ReaderAgent] --> P[PlannerAgent]
    P --> V[ValidatorAgent]
    V -->|issues?| P
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
  V --> META[meta / agent_logs]
```

### 責務とフローの要点
- ReaderAgent: 入力文から actions / entities / 条件情報などを抽出する
- PlannerAgent: actions を基に tasks を分割し、roles / trigger などの骨格を作る
- ValidatorAgent: 不備・曖昧さ・非業務タスクを検出し、issues を返す
- GeneratorAgent: 検証済み情報のみで最終JSONを生成する
- Orchestrator: 実行順序・Retry 制御・ログ収集を担う

Retry の意味:
- Validator が issues を返した場合のみ Planner に差し戻して再計画する
- 再試行回数には上限がある（無限ループ防止）

## Data Model (Output JSON)
- `definition`: 生成された業務定義（tasks / roles / assumptions / open_questions）
- `meta`: デバッグ用メタ情報（actions, entities, role_inference, retries など）
- `agent_logs`: 各 Agent の要約ログ

構造イメージ（抜粋）:
```json
{
  "definition": {
    "title": "...",
    "overview": "...",
    "tasks": [
      {
        "id": "task_1",
        "name": "申請する",
        "role": "Applicant",
        "trigger": "",
        "steps": ["申請する"],
        "exception_handling": [],
        "notifications": [],
        "recipients": []
      }
    ],
    "roles": [{ "name": "Applicant", "responsibilities": ["..."] }],
    "assumptions": [],
    "open_questions": []
  },
  "meta": {
    "actions": ["..."],
    "actions_raw": ["..."],
    "actions_filtered_out": ["..."],
    "entities": { "people": [] },
    "role_inference": [],
    "splitter_version": "ja_v1",
    "action_filter_version": "biz_v1",
    "retries": 0
  },
  "agent_logs": [{ "step": "reader", "summary": "..." }]
}
```

## Demo（デモ）
1. フロントを開く
2. サンプル文章のまま「変換」を押す
3. `definition` / `meta` / `agent_logs` を確認

スクショ/GIFを追加する場合は `docs/` に置き、ここにリンクしてください。

## How to run locally（ローカル実行）
Backend:
```sh
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8080
```

Frontend (Docker):
```sh
cd frontend
docker build -t agentic-bizflow-frontend .
docker run --rm -p 8081:8080 \
  -e LIFF_ID="<liff-id>" \
  -e BACKEND_BASE_URL="http://localhost:8080" \
  agentic-bizflow-frontend
```

## Deploy（Cloud Run）
Backend:
- 環境変数: `GCP_PROJECT_ID`, `GCP_LOCATION`, `GEMINI_MODEL`（任意）, `CORS_ALLOW_ORIGINS`（任意）
- Vertex AI 利用時はサービスアカウントに権限付与が必要

Frontend:
- 環境変数: `LIFF_ID`, `BACKEND_BASE_URL`, `PORT`（任意）
- `config.js` は起動時に生成され `no-store` で配信

例（プレースホルダのみ）:
```sh
gcloud run deploy <backend-service> \
  --source=./backend \
  --region=<region> \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=<project-id>,GCP_LOCATION=<region>"
```

```sh
gcloud run deploy <frontend-service> \
  --source=./frontend \
  --region=<region> \
  --allow-unauthenticated \
  --set-env-vars "LIFF_ID=<liff-id>,BACKEND_BASE_URL=<backend-url>"
```

## Repository structure（構成）
```
agentic-bizflow/
├─ backend/          # FastAPI + agentic core
├─ frontend/         # LIFF single-page UI
├─ docs/             # 設計資料/セットアップ
└─ AGENTS.md         # 最上位ルール
```

## Limitations & Next steps（制約と今後）
- 分割はルールベース。形態素解析への拡張余地あり
- IDトークンの署名検証は未実装（デモ優先）
- Role推定はヒューリスティック。業務別ルール拡張が必要
- エンティティ抽出（org/date/amount）を今後拡張可能

## License
See `LICENSE`.
