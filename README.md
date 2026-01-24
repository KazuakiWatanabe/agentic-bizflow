# Agentic BizFlow

業務文章（自然文）を **実行可能な業務定義（運用オブジェクト）へ変換する Agentic AI の実装例**です。

本プロジェクトは **Google Cloud Agentic AI Hackathon** への提出を目的としており、単発の LLM 呼び出しではなく、**複数 Agent・検証・再試行を備えた Agentic AI アーキテクチャ**を明示的に実装しています。

---

## 🎯 プロジェクトの目的

多くの現場には、以下のような資料に **「人が読めば分かるが、システムは実行できない文章」** が存在します。

- 業務マニュアル
- 引き継ぎ資料
- Notion / Slack / Wiki に書かれた業務説明

本プロジェクトは、それらの自然文を対象に、次を実現します。

- AI が業務内容を理解・分解・検証する
- **実行可能な業務定義（JSON）** として構造化する

---

## 🤖 Agentic AI としての特徴

Agentic BizFlow は、以下を満たすことで **Agentic AI** として設計されています。

- 明確に役割分担された複数 Agent
- 中央制御を担う Orchestrator
- 不完全な結果を「失敗」と判定する Validator Agent
- 検証結果に基づく Retry（再試行）ループ
- Pydantic スキーマによる決定論的な出力検証

設計思想・実装ルールの詳細は [`AGENTS.md`](./AGENTS.md) に記載しています。

---

<<<<<<< HEAD
## ドキュメント

- フロント仕様: [`frontend/README_FRONTEND_SPEC.md`](./frontend/README_FRONTEND_SPEC.md)
- LIFF設定手順: [`docs/LIFF_SETUP.md`](./docs/LIFF_SETUP.md)

---

## 🧠 Agent 構成（概要）

## 🗺️ アーキテクチャ図（Zenn/審査員向け）
=======
## 🧠 Agent 構成
>>>>>>> backend-mvp

![Agentic BizFlow Architecture](./docs/diagrams/agentic-architecture.png)

### 構成のポイント

- Orchestrator が Agent 実行順と状態遷移を管理
- Validation に失敗した場合は Retry（最大2回）
- Reader → Planner → Validator → Generator の責務分離
- 出力は Pydantic スキーマで厳密に検証（schema enforced）
- FastAPI + Docker 構成で Cloud Run 上にデプロイ可能

### 各 Agent の役割

- **ReaderAgent**: 業務文章を読み取り、登場人物・操作・条件・例外を抽出
- **PlannerAgent**: 業務を実行可能なタスク単位に分解
- **ValidatorAgent**: 抜け漏れ・曖昧さ・矛盾を検出し、失敗判定を行う
- **GeneratorAgent**: 検証済み情報のみを用いて業務定義 JSON を生成
- **Orchestrator**: Agent 実行順制御、Retry 管理、ログ収集を担当

---

## 🧱 リポジトリ構成

```text
agentic-bizflow/
├─ AGENTS.md          # 最上位ルール（Agent定義 / PEP8 / Git運用）
├─ README.md
├─ backend/
│  ├─ app/
│  │  └─ agent/
│  │     ├─ schemas.py        # Pydantic スキーマ
│  │     ├─ orchestrator.py   # Agent 実行 + Retry 制御
│  │     ├─ reader.py
│  │     ├─ planner.py
│  │     ├─ validator.py
│  │     └─ generator.py
│  └─ tests/
│     ├─ test_schema.py
│     └─ test_orchestrator.py
└─ frontend/          # デモ用UI（後続フェーズ）
```

---

## 🌱 ブランチ戦略

本リポジトリでは、思考レイヤーと実装フェーズを分離するためのブランチ戦略を採用しています。

```text
main
├─ docs/architecture
├─ agentic-core
├─ backend-mvp
├─ frontend-mvp
└─ polish-for-submission
```

| ブランチ | 役割 |
| --- | --- |
| main | 常に提出・デモ可能な状態 |
| docs/architecture | 設計思想・Agent定義 |
| agentic-core | Agent / Orchestrator の中核実装 |
| backend-mvp | FastAPI + Cloud Run API |
| frontend-mvp | デモ用UI |
| polish-for-submission | README・デモ表現の最終調整 |

---

## 🧪 現在の実装状況

- ✅ agentic-core（schemas / orchestrator / pytest）実装完了
- ✅ backend-mvp（FastAPI + Docker）Cloud Run デプロイ・動作確認済み
- ⏳ frontend-mvp（デモ用UI）は後続フェーズ

---

## 🚀 Cloud Run デプロイ / API 実行例

backend-mvp は FastAPI + Docker 構成のまま Cloud Run 上で動作します。  
README には実URLは記載せず、コマンド例のみ掲載しています。

### Cloud Run デプロイ（最小例）

```sh
gcloud run deploy agentic-bizflow-backend \
  --source=./backend \
  --region=asia-northeast1 \
  --allow-unauthenticated
```

※ Vertex AI（Gemini）を利用する場合は、Cloud Run のサービスアカウントに `roles/aiplatform.user` を付与してください。

### API 実行例

#### curl

```sh
curl -X POST https://<cloud-run-url>/api/convert \
  -H "Content-Type: application/json" \
  -d '{"text":"経費を申請し、承認されたら精算する"}'
```

#### PowerShell（Invoke-RestMethod）

```powershell
$body = @{ text = "経費を申請し、承認されたら精算する" } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "https://<cloud-run-url>/api/convert" `
  -ContentType "application/json" `
  -Body $body
```

#### レスポンス例（抜粋）

```json
{
  "definition": { ... },
  "agent_logs": [ ... ],
  "meta": { ... }
}
```

---

## 🧑‍💻 開発環境

- Python 3.11+
- Pydantic v2
- pytest
- black / isort / flake8（PEP8準拠）
- Node.js 20+（frontend）

---

## 🧪 テスト

```sh
cd backend
pytest -q
```

---

## 📜 コーディング規約

- Python は PEP8 準拠
- black / isort 互換
- import の暗黙利用禁止
- Agent の責務混在禁止

詳細は `AGENTS.md` を参照してください。

---

## 📌 注意事項

- 本リポジトリには秘密情報・APIキーは含めません
- .env は使用せず .env.example のみを配置します
- Google Cloud 無料枠を前提に設計しています

---

## ✨ Why Agentic BizFlow

このプロジェクトは「AIにコードを書かせる」ことが目的ではありません。次を重視しています。

- 曖昧な業務を構造化する
- AIの思考を外に出す
- 人がレビュー可能な形にする
- そのための Agentic AI 実装例を示す
