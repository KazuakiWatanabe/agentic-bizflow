# AGENTS.md

Agentic BizFlow ― 最上位ルール定義書（日本語）

本ドキュメントは、本リポジトリに関わる **すべてのAI（Codex等）と人間**が遵守すべき最上位ルールです。  
README や設計資料よりも **AGENTS.md を優先**します。

---

## 1. プロジェクトの目的

本プロジェクトは、業務マニュアル・引き継ぎ資料・Notion・Slack 等に書かれた  
**「人が読めば分かるが、システムは実行できない自然文」**を対象に、

- AIが業務内容を理解し
- 構造化・分解・検証を行い
- **実行可能な業務定義（JSON）**として出力する

**Agentic AI の実装例**を提示することを目的とします。

---

## 2. Agentic AI としての成立条件（必須）

以下を **すべて満たす場合のみ** Agentic AI とみなします。

- 明確に役割分担された複数 Agent
- 中央制御を行う Orchestrator
- 失敗を返す Validator Agent
- 検証結果に基づく Retry（再試行）ループ
- Pydantic スキーマによる決定論的な出力検証

---

## 3. Agent 構成（責務定義）

- **ReaderAgent**  
  業務文章を読み取り、登場人物・操作・条件・例外・前提を抽出する

- **PlannerAgent**  
  抽出結果を基に、業務を実行可能なタスク単位に分解する

- **ValidatorAgent**  
  抜け漏れ・曖昧さ・矛盾を検出し、失敗判定を行う

- **GeneratorAgent**  
  検証済み情報のみを用いて、業務定義 JSON を生成する

- **Orchestrator**  
  Agent 実行順序・Retry 制御・ログ収集を担当する

---

## 4. 日本語コメント（docstring）記載ルール【必須】

本リポジトリで作成・更新する **すべての Python ファイル**は、以下①〜④を **日本語で必ず記載**してください。  
未記載の場合、実装は **未完成扱い**です。

### 4.1 ① ファイルサマリーを日本語で記載する（必須）

各 `.py` の先頭に、モジュールドックストリング（ファイルサマリー）を記載する。

含める内容：

- このファイルの責務
- 主な入出力
- 重要な制約（例：最大Retry回数など）

### 4.2 ② クラスの説明を日本語で記載する（必須）

クラスには必ず docstring を付ける。

含める内容：

- クラスの責務
- 主要メソッドの役割
- 前提・制約

### 4.3 ③ 関数の説明を日本語で記載する（必須）

関数・メソッドには必ず docstring を付ける。

含める内容：

- 何をする関数か
- 引数の意味
- 戻り値の意味
- エラー条件（ある場合）

### 4.4 ④ 条件付き実装などのメモを Note として日本語で記載する（必須）

if/else、retry、例外、環境変数分岐など **条件付きの挙動**がある場合、必ず `Note:` に条件を明記する。

例：

- 「issues が存在する場合のみ retry する」
- 「retry は最大2回」
- 「Generator は Validation 通過後のみ実行する」

### 4.5 ⑤ 変数の意味を日本語で説明する（必須）

関数内・クラス内で定義される 主要な変数 について、以下のいずれかの方法で 日本語による意味説明 を必ず記載する。

対象となる変数例：

- 業務上の意味を持つ変数（definition, issues, retries, agent_logs など）
- 条件分岐や制御に影響する変数（flags, counters, status など）
- 一時変数であっても文脈理解に重要なもの
- 記載方法（いずれか必須）：
- 変数定義直前のコメント
- docstring 内の Variables: セクション

未記載の場合、その実装は **レビュー未通過（未完成）扱い** とする。

---

## 5. コーディング規約

- Python は **PEP8 準拠**
- black / isort 互換（line length = 88）
- import の暗黙利用禁止
- Agent の責務混在禁止（I/O層とロジック層を分離）
- 生のLLM応答・プロンプト全文をログに出さない（要約のみ）

---

## 6. Git 運用（ブランチ戦略）

main
├─ docs/architecture
├─ agentic-core
├─ backend-mvp
├─ frontend-mvp
└─ polish-for-submission

yaml
コードをコピーする

| ブランチ | 役割 |
| -------- | ------ |
| main | 常に提出・デモ可能 |
| docs/architecture | 設計思想・定義（コードなし） |
| agentic-core | Agent / Orchestrator 中核 |
| backend-mvp | FastAPI / Cloud Run |
| frontend-mvp | デモUI |
| polish-for-submission | README・表現調整 |

---

## 7. 禁止事項

- Agentic 構成を満たさない単発 LLM 実装
- Validator を通さない出力
- 日本語docstring無しの Python 実装
- secrets / APIキーのコミット
- `.venv` 等の環境依存ファイルのコミット

---

## 8. Python 実装サンプル（本ルール準拠例）

以下は、本リポジトリで推奨する **docstringの書き方と実装の骨格**の例です。  
（Google style / reST / NumPy style は自由だが、日本語で①〜⑤を満たすこと）

### 8.1 ファイルサマリー（①）＋条件Note（④）の例

```python
"""
業務文章を業務定義へ変換する Orchestrator を提供する。

本モジュールは Reader → Planner → Validator → Generator の順に処理を行い、
Validator が issues を返した場合、制約付きで再試行する。

Note:
- 再試行は最大2回までとする
- Generator は Validation 通過後のみ実行する
- ログには要約のみを保存し、生のLLM応答やプロンプト全文は保存しない
"""

### 8.2 クラス説明（②）の例

python
コードをコピーする
class ValidatorAgent:
    """Plannerの出力を検証するAgent。

    必須項目の欠落、曖昧な条件、矛盾を検出し、issues と open_questions を返す。
    issues が1つでもある場合、Orchestratorは失敗とみなし再試行を行う。

    Note:
        - issues が存在する場合のみ「失敗」として扱う
    """


### 8.3 関数説明（③）＋条件Note（④）の例

python
コードをコピーする
def convert(self, text: str):
    """業務文章を業務定義に変換する。

    Args:
        text: 入力となる業務文章（自然文）

    Returns:
        definition: Pydanticスキーマに準拠した業務定義
        agent_logs: 各ステップの要約ログ（短文）
        meta: retries回数などのメタ情報

    Note:
        - Validator が issues を返した場合のみ再試行する
        - 再試行は最大2回まで
    """


### 8.4 関数説明（③）＋条件Note（④）＋変数説明（⑤）の例

```python

def convert(self, text: str):
    """業務文章を業務定義に変換する。

    Args:
        text: 入力となる業務文章（自然文）

    Returns:
        definition: Pydanticスキーマに準拠した業務定義
        agent_logs: 各ステップの要約ログ（短文）
        meta: retries回数などのメタ情報

    Variables:
        retries:
            Validator で失敗した場合に再試行した回数を表すカウンタ。
            初回実行時は 0 から開始し、再試行のたびにインクリメントされる。

        agent_logs:
            Reader / Planner / Validator / Generator 各 Agent の
            実行結果を要約したログの一覧。
            デバッグ用途ではなく、人が処理の流れを追うための情報を保持する。

        issues:
            ValidatorAgent が検出した問題点の一覧。
            空配列の場合のみ Validation 通過とみなされる。

    Note:
        - Validator が issues を返した場合のみ再試行する
        - 再試行は最大2回まで
    """
    retries = 0  # Validator失敗時の再試行回数
    agent_logs = []  # 各Agentの実行要約ログを格納する

    reader_out = self._reader(text)

    while True:
        planner_out = self._planner(reader_out, retries=retries)
        validator_out = self._validator(planner_out)

        issues = validator_out.get("issues", [])  # 検出された問題点一覧

        if not issues:
            definition = self._generator(text, reader_out, planner_out, validator_out)
            meta = {"retries": retries}
            return definition, agent_logs, meta

        if retries >= self.max_retries:
            raise ValueError("再試行上限に達しました")

        retries += 1


### 8.5 最小の Agentic パイプライン骨格（参考）

これは 構造の例です。実際の実装では backend/app/agent/ 配下の責務分離を維持してください。

python
コードをコピーする
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

@dataclass
class AgentLog:
    """Agent実行ログ（要約）。"""
    step: str
    summary: str
    issues_count: int = 0


class Orchestrator:
    """Agenticパイプラインを制御する。

    Reader → Planner → Validator → Generator の順で実行する。
    Validator で issues が検出された場合は、最大2回まで再試行する。

    Note:
        - 再試行は最大2回
        - Generator は Validation 通過後のみ実行
    """

    def __init__(self, max_retries: int = 2) -> None:
        """Orchestratorを初期化する。

        Args:
            max_retries: 再試行の最大回数

        Note:
            - max_retries は 0 以上を想定する
        """
        self.max_retries = max_retries

    def convert(self, text: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
        """業務文章を業務定義（dict）へ変換する。

        Args:
            text: 入力となる業務文章

        Returns:
            (definition_dict, agent_logs, meta)

        Note:
            - issues がある場合、Planner/Generatorへの制約を増やして再試行する
        """
        agent_logs: List[Dict[str, Any]] = []
        retries = 0

        # ここでは例として dict を返す。実際は Pydantic モデルを返す想定。
        reader_out = self._reader(text)
        agent_logs.append({"step": "reader", "summary": "要素を抽出しました", "issues_count": 0})

        while True:
            planner_out = self._planner(reader_out, retries=retries)
            agent_logs.append({"step": "planner", "summary": "タスク案を生成しました", "issues_count": 0})

            validator_out = self._validator(planner_out)
            issues = validator_out.get("issues", [])
            agent_logs.append(
                {"step": "validator", "summary": "検証を実施しました", "issues_count": len(issues)}
            )

            if not issues:
                definition = self._generator(text, reader_out, planner_out, validator_out)
                agent_logs.append({"step": "generator", "summary": "業務定義を生成しました", "issues_count": 0})
                meta = {"retries": retries, "model": "stub"}
                return definition, agent_logs, meta

            if retries >= self.max_retries:
                # 失敗時は要約のみ返す（詳細ログを出しすぎない）
                raise ValueError("スキーマ必須項目の不足が解消できませんでした（再試行上限）")

            retries += 1
            agent_logs.append(
                {"step": "orchestrator", "summary": "issues を踏まえて再試行します", "issues_count": len(issues)}
            )

    def _reader(self, text: str) -> Dict[str, Any]:
        """Readerの仮実装。"""
        return {"entities": [], "actions": [], "conditions": [], "exceptions": [], "assumptions": []}

    def _planner(self, reader_out: Dict[str, Any], retries: int) -> Dict[str, Any]:
        """Plannerの仮実装。

        Note:
            - retries が増えるほど、欠落項目を補う方向で出力を改善する想定
        """
        return {"tasks": [{"id": "task_1", "name": "仮タスク", "role": "店長", "trigger": "開店前"}], "roles": [{"name": "店長"}]}

    def _validator(self, planner_out: Dict[str, Any]) -> Dict[str, Any]:
        """Validatorの仮実装。"""
        issues: List[str] = []
        if not planner_out.get("tasks"):
            issues.append("tasks が空です")
        return {"issues": issues, "open_questions": []}

    def _generator(self, text: str, reader_out: Dict[str, Any], planner_out: Dict[str, Any], validator_out: Dict[str, Any]) -> Dict[str, Any]:
        """Generatorの仮実装（dict）。"""
        return {"title": "仮タイトル", "overview": "仮概要", "tasks": [], "roles": [], "assumptions": [], "open_questions": []}


## 9. このルールの意図（Why）

本プロジェクトは「AIにコードを書かせること」そのものが目的ではありません。

曖昧な業務を構造化する

AIの思考を外に出す（可視化）

人がレビュー可能な形にする

そのために 日本語docstringを設計要件として強制しています。
