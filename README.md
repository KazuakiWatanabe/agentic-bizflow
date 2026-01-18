# Agentic BizFlow

業務文章（自然文）を、  
**実行可能な業務定義（運用オブジェクト）へ変換する Agentic AI の実装例**です。

本プロジェクトは  
**Google Cloud Agentic AI Hackathon** 提出を目的としており、  
単発のLLM呼び出しではなく、**Agentic AI（複数Agent＋検証＋再試行）** を明確に示す構成を採用しています。

---

## 🎯 プロジェクトの目的

- 業務マニュアル・引き継ぎ資料・Notion・Slack 等に書かれた  
  **「人が読めば分かるが、システムは実行できない文章」**を対象に
- AIが業務内容を理解・分解・検証し
- **実行可能な業務定義（JSON）**として出力する

ことを目的としています。

---

## 🤖 Agentic AI としての特徴

本プロジェクトは、以下をすべて満たすことで  
**Agentic AI** として設計されています。

- 明確に役割分担された複数Agent
- 中央制御を行う Orchestrator
- 失敗を返す Validator Agent
- 検証結果に基づく Retry（再試行）ループ
- Pydantic スキーマによる決定論的な出力検証

詳細なルール・思想は [`AGENTS.md`](./AGENTS.md) に記載しています。

---

## ドキュメント

- フロント仕様: [`frontend/README_FRONTEND_SPEC.md`](./frontend/README_FRONTEND_SPEC.md)
- LIFF設定手順: [`docs/LIFF_SETUP.md`](./docs/LIFF_SETUP.md)

---

## 🧠 Agent 構成（概要）

## 🗺️ アーキテクチャ図（Zenn/審査員向け）

![Agentic BizFlow Architecture](./docs/diagrams/agentic-architecture.png)

### ポイント

- Orchestrator が状態遷移を管理し、Validation に失敗したら Retry（最大2回）
- Reader → Planner → Validator → Generator の責務分離
- 出力は Pydantic スキーマで決定論的に検証（schema enforced）
- Cloud Run 上で API として動作（後続フェーズで実装）

- **ReaderAgent**  
  業務文章を読み取り、登場人物・操作・条件・例外を抽出
- **PlannerAgent**  
  業務を実行可能なタスク単位に分解
- **ValidatorAgent**  
  抜け漏れ・曖昧さ・矛盾を検出し、失敗判定を行う
- **GeneratorAgent**  
  検証済み情報のみを用いて業務定義JSONを生成
- **Orchestrator**  
  Agent 実行順・Retry 制御・ログ収集を担当

---

## 🧱 リポジトリ構成

agentic-bizflow/
├─ AGENTS.md # 最上位ルール（Agent定義 / PEP8 / Git運用）
├─ README.md
├─ backend/
│ ├─ app/
│ │ └─ agent/
│ │ ├─ schemas.py # Pydantic スキーマ
│ │ ├─ orchestrator.py # Agent 実行 + Retry 制御
│ │ ├─ reader.py
│ │ ├─ planner.py
│ │ ├─ validator.py
│ │ └─ generator.py
│ └─ tests/
│   ├─ test_schema.py
│   └─ test_orchestrator.py
└─ frontend/ # デモ用UI（後続フェーズ）

---

## 🌱 ブランチ戦略

本リポジトリでは、**思考レイヤーを分離するためのブランチ戦略**を採用しています。

main
├─ docs/architecture
├─ agentic-core
├─ backend-mvp
├─ frontend-mvp
└─ polish-for-submission

### 各ブランチの役割

| ブランチ | 役割 |
| -------- | ------ |
| main | 常に提出・デモ可能な状態 |
| docs/architecture | 設計思想・Agent定義（コードなし） |
| agentic-core | Agent / Orchestrator の中核実装 |
| backend-mvp | FastAPI / Cloud Run で動くAPI |
| frontend-mvp | デモ用UI |
| polish-for-submission | README・デモ表現の最終調整 |

詳細な運用ルールは `AGENTS.md` を参照してください。

---

## 🧪 現在の実装フェーズ

- ✅ ブランチ作成完了
- ✅ agentic-core のフォルダ構成確定
- ⏳ agentic-core の最小実装（schemas / orchestrator / pytest）作業中
- ⏳ backend-mvp / frontend-mvp は後続フェーズ

---

## 🚀 Cloud Run デプロイ / API 実行例

本プロジェクトの backend-mvp は、  
**FastAPI + Docker 構成のまま Cloud Run 上で実行可能**です。

### Cloud Run デプロイ例（最小）

```sh
gcloud run deploy agentic-bizflow-backend \
  --source=./backend \
  --region=asia-northeast1 \
  --allow-unauthenticated
※ Vertex AI（Gemini）を利用する場合は、
Cloud Run のサービスアカウントに roles/aiplatform.user を付与してください。


### API 実行例（curl）

sh
コードをコピーする
curl -X POST https://<cloud-run-url>/api/convert \
  -H "Content-Type: application/json" \
  -d '{"text":"経費を申請し、承認されたら精算する"}'
レスポンス例（抜粋）：

json
コードをコピーする
{
  "definition": { ... },
  "agent_logs": [ ... ],
  "meta": { ... }
}


##  🧑‍💻 開発環境

- Python 3.11+
- Pydantic v2
- pytest
- black / isort / flake8（PEP8準拠）
- Node.js 20+（frontend）

## 🚀 テスト

sh
コードをコピーする
cd backend && pytest -q


## 📜 コーディング規約

- Python は PEP8 準拠
- black / isort 互換
- import の暗黙利用禁止
- Agent の責務混在禁止


## 📌 注意事項

- 本リポジトリには 秘密情報・APIキーは含めません
- .env は使用せず .env.example のみを配置します
- 無料枠（Google Cloud Always Free）前提で設計しています

## ✨ Why Agentic BizFlow

- このプロジェクトは「AIにコードを書かせる」ためのものではありません。
- 曖昧な業務を構造化する
- AIの思考を外に出す
- 人がレビュー可能な形にする
- そのための Agentic AI 実装例です。
