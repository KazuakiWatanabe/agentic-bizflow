# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**作業を開始する前に必ずこのファイルと AGENTS.md を読むこと。**
**AGENTS.md が最上位ルールであり、本ファイルはその補足である。**

---

## 1. このファイルの役割

`CLAUDE.md` は、Claude Code がこのリポジトリで実装・修正・テスト・ドキュメント更新を行う際の **実務運用ガイド** です。

このファイルが扱う内容:

- 作業開始時の参照順序
- 現在フェーズの概要と参照先
- 実行コマンド例
- テストとエビデンス保存の実務ルール

このファイルが扱わない内容:

- 最上位ルールの決定（→ AGENTS.md）
- 恒久的な禁止事項の定義（→ AGENTS.md）
- フェーズ固有の設計詳細（→ docs/*.md）
- 個別タスクの実装指示（→ task/*.md）

---

## 2. プロジェクト概要

Agentic BizFlow は、自然文の日本語業務手順を実行可能な業務定義（BusinessDefinition JSON）に変換する Agentic Architecture 実装です。複数 Agent による段階処理（Reader → Planner → Validator → Generator）を基盤とし、Pydantic スキーマ検証と Retry ループで品質を担保します。

**LLM 統合:** Vertex AI / Gemini via `agent/llm.py` → `agent/llm_client_vertex.py`。LLM は各 Agent でオプショナルであり、前処理サービスがコアロジックを担い、LLM が補完する構成。

**フロントエンド:** LIFF（LINE Front-end Framework）の静的 HTML。ビルドステップなし、Docker 経由の Nginx で配信。

---

## 3. 参照優先順位

Claude Code は、作業開始前に以下をこの順番で確認してください。

```text
1. AGENTS.md（最上位ルール）
2. CLAUDE.md（本ファイル）
3. 対象の task/*.md（個別タスク指示）
4. docs/*.md（設計参照）
5. README.md
```

**個別タスクを実行するときは、必ず `task/` 配下のタスクファイルを起点に進めてください。**
フェーズ固有の設計詳細（コンポーネント構成・API 設計・ディレクトリ変更等）は `docs/` 配下の設計書を参照すること。

---

## 4. ドキュメント参照表

| ドキュメント | 参照すべきタイミング |
|---|---|
| `AGENTS.md` | コーディング規約・テスト規約・セキュリティ規約・禁止事項の確認 |
| `task/*.md` | 実装タスク一覧・AC・作業手順の確認 |
| `docs/test-instruction-template.md` | テストタスクのテンプレート・AC ID 紐付けルールの確認 |
| `docs/README_architecture.md` | 全体アーキテクチャの設計補足 |
| フェーズ固有の設計書（`docs/` 配下） | コンポーネント構成・API 設計・責務境界の確認 |

---

## 5. コマンド早見表

```bash
# ─── 環境セットアップ ───
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt

# ─── ローカル起動 ───
cd backend && python -m uvicorn app.main:app --reload --port 8080

# ─── Lint & Format（コミット前に必ず実行）───
cd backend && black --check .
cd backend && isort --check-only .
cd backend && flake8 .

# ─── テスト実行 ───
cd backend && pytest -q                                    # 全テスト
cd backend && pytest tests/test_api.py -v                 # 単一ファイル
cd backend && pytest tests/test_api.py::test_health -v    # 単一テスト

# ─── エビデンス保存（タスク完了時に必ず実行）───
cd backend && pytest tests/ -v > tests/evidence/test_result.txt

# ─── セキュリティ監査（パッケージ追加・変更時に必ず実行）───
pip install pip-audit
pip-audit > tests/evidence/security_audit.txt
```

---

## 6. 作業開始時のチェックリスト

- [ ] `AGENTS.md` のセキュリティルール・禁止事項を確認した
- [ ] 対象タスクの `ac_ids` と `source_spec` を `task/*.md` で確認した
- [ ] 現在のフェーズと、そのフェーズで変更可能な範囲を確認した
- [ ] テストタスクの場合、`target_files` と `target_functions` が 2 つ以内であることを確認した
- [ ] 新規 `import` を追加する場合、`requirements.txt` 記載済みであることを確認した
- [ ] フェーズ固有の設計は `docs/` 配下の該当設計書で確認した

---

## 7. Mandatory Rules（AGENTS.md から — 本ファイルより優先）

- **すべての Python ファイルに日本語 docstring を記載する**（ファイルサマリー、クラス説明、関数説明、条件 Note、変数説明）。未記載は未完成扱い。
- **Agentic Architecture を壊さない**: 複数 Agent の役割分担、Orchestrator、Validator の失敗判定、Retry ループ、Pydantic スキーマ検証が常に成立すること。
- **Agent 層と実行層を分離する**: Agent 層に外部 API 呼び出しや副作用を伴う処理を混ぜないこと。
- **生の LLM プロンプト/応答をログに出さない** — 要約のみ。
- **既存機能を保護する**: 新機能追加時に既存エンドポイントの動作を壊さないこと。

---

## 8. テスト実務ルール

### 回帰テスト（常に最優先）

新機能の追加時は、既存エンドポイント（`POST /api/convert` 等）が壊れていないことを常に確認する。

### 自己検証ステップ

```
Step 1. テストが PASS であることを確認する
Step 2. 実装の核となるロジックを意図的に壊し、テストが FAIL になることを確認する
Step 3. 壊した実装を元に戻し、再度 PASS になることを確認する
Step 4. Step 2 で FAIL にならなかったテストは検証内容を見直して修正する
```

### エビデンス保存

タスク完了時に必ず以下を実行し、結果をコミットする:

```bash
cd backend && pytest tests/ -v > tests/evidence/test_result.txt
```

テストタスクの詳細なルールは `docs/test-instruction-template.md` を参照。

---

## 9. 環境変数

`backend/.env.example` を参照:

- `GCP_PROJECT_ID`（LLM 必須）
- `GCP_LOCATION`（デフォルト: `asia-northeast1`）
- `GEMINI_MODEL`（デフォルト: `gemini-2.0-flash`）
- `CORS_ALLOW_ORIGINS`（デフォルト: `*`）

---

## 10. 迷ったときの判断基準

**Q. Agent 層のコードを変更してよいか？**
→ AGENTS.md §4 の不変原則を確認すること。Agent 層と実行層は分離されている必要がある。変更が必要な場合は、先に AGENTS.md の Agent 構成を更新してからコードに着手する。

**Q. テストで実際の Vertex AI を叩いてよいか？**
→ 禁止。モックを使用すること。

**Q. 既存コードで使われている `import` をそのまま新しいファイルで使ってよいか？**
→ AGENTS.md のセキュリティチェック手順を確認してから使用すること。

**Q. 外部 API への通信を実装してよいか？**
→ AGENTS.md の allowlist に登録されているドメインのみ許可。未登録の場合は allowlist を更新してからコードに反映。

**Q. タスクが完了したとはいつ言えるか？**
→ AGENTS.md §12（Done Definition）を参照。pytest 全件 PASS、自己検証ステップ完了、evidence 保存が最低条件。

**Q. フェーズ固有の設計判断に迷ったときは？**
→ `docs/` 配下のフェーズ設計書を参照。設計書にない判断が必要な場合は、先に設計書を更新してから実装する。

---

## 11. AGENTS.md との整合ルール

本ファイルは `AGENTS.md` の内容を **具体的な実務運用に落とすためのファイル** です。

- AGENTS.md にある不変原則を上書きしない
- AGENTS.md にない新しい恒久ルールを勝手に本ファイルだけへ追加しない
- 参照順序、責務分担、Done Definition の考え方は AGENTS.md と揃える
- ルール変更が必要なら、先に AGENTS.md を見直してから CLAUDE.md を更新する
- フェーズ固有の実装詳細（コンポーネント名、ディレクトリ構成変更、API 設計等）は `docs/` や `task/` に委譲し、本ファイルには書かない
