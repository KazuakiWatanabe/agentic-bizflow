# Phase 7: Marketing Channel Abstraction — 実装タスク

> **設計の参照先:** `docs/phase7/phase7_design.md`
> **全体ロードマップ:** `docs/roadmap-phase6-to-phase9.md`
> **最上位ルール:** `AGENTS.md`
> **実務ガイド:** `CLAUDE.md`

---

## 前提

- Phase 6 が完了していること（LINE デモ完成・管理 UI・live connector 最小接続）
- `backend/app/agent/` 配下のファイルは変更禁止
- 既存の全 API（Phase 1〜6）が壊れていないことをテストで常に保証する
- **既存 DB テーブル名は変更しない**（tags / broadcasts / scenarios / reminders 等はそのまま）
- AGENTS.md §6（日本語 docstring ①〜⑤）を全ファイルで満たすこと
- テスト完了時は `tests/evidence/` にエビデンスを保存すること

---

## Task 1: 共通 Workload Kind の定義

**作業:** 5 つの共通 kind を定義し、Workload Kind Registry に登録する。

**追加するファイル:**
- `backend/app/domains/common/__init__.py`
- `backend/app/domains/common/workload_kinds.py`

> 共通 kind の一覧は `docs/phase7/phase7_design.md` §3.2 を参照。

**登録する共通 kind:**

| 共通 kind | 説明 | キーワード例 |
|---|---|---|
| `audience.label.assign` | 対象者にラベルを付与する | タグ、付与、ラベル、セグメント |
| `campaign.schedule` | 一斉配信を予約する | 配信、一斉、全員、告知 |
| `journey.create` | ステップ配信シナリオを作成する | シナリオ、ステップ配信、フォロー |
| `journey.enroll` | 対象者をジャーニーに登録する | 開始、対象者、配信開始 |
| `followup.create` | タイミング配信を作成する | リマインド、リマインダー、通知予約 |

**共通 kind → ドメイン kind の resolution マッピングも登録する:**

```python
registry.register_resolution("audience.label.assign", {
    "line": "line.tag.assign",
    "email": None,   # Email はラベル操作非対応
})
registry.register_resolution("campaign.schedule", {
    "line": "line.broadcast.schedule",
    "email": "email.broadcast.schedule",
})
# ...
```

**変更するファイル:**
- `backend/app/connectors/workload_kind_registry.py` — `register_resolution()` メソッドを追加
- `backend/app/domains/line/__init__.py` — resolution マッピングを register() に追加
- `backend/app/domains/email/__init__.py` — 同上

**テスト:** `backend/tests/test_common_kinds.py`

**完了条件:**
- 5 つの共通 kind が Registry に登録されている
- 各共通 kind からドメイン kind への resolution マッピングが存在する
- `registry.list_by_domain("common")` で共通 kind 5 つが返る
- 既存のドメイン kind（`line.tag.assign` 等）が引き続き動作する

---

## Task 2: Kind Resolver の実装

**作業:** 共通 kind をドメイン kind に解決するモジュールを実装する。

**追加するファイル:**
- `backend/app/execution/kind_resolver.py`

> 設計は `docs/phase7/phase7_design.md` §7 を参照。

**実装するメソッド:**

```python
def resolve_kind(step: ExecutionStep, registry: WorkloadKindRegistry,
                 domain_configs: list[DomainConfig]) -> str:
    """共通 kind をドメイン kind に解決する。

    解決の優先順位:
    1. kind がすでにドメイン kind（"line." "email." 等で始まる）→ そのまま返す
    2. step に domain_hint がある → そのドメインの resolution を使う
    3. domain_hint なし → enabled なドメインの中で priority 順に解決
    4. 該当なし → エラー
    """
```

**変更するファイル:**
- `backend/app/execution/workload_runner.py` — step 実行前に `resolve_kind()` を呼ぶ

**テスト:** `backend/tests/test_kind_resolver.py`

**テストケース:**
1. 共通 kind + domain_hint あり → 指定ドメインで解決
2. 共通 kind + domain_hint なし → 有効ドメインの priority 順で解決
3. ドメイン kind（`line.tag.assign`）→ そのまま返す
4. Phase 5 エイリアス（`tag.assign`）→ そのまま返す（Registry のエイリアス解決）
5. 該当ドメインなし → エラー
6. 対象ドメインが disabled → スキップして次の priority ドメインで解決
7. resolution が None（非対応）→ 次の priority ドメインで解決、全滅ならエラー

**完了条件:**
- 全テストケースが通る
- 既存の execute フロー（ドメイン kind 直接指定）が壊れない

---

## Task 3: ExecutionPlanner の共通 kind 対応

**作業:** ExecutionPlanner が共通 kind を生成できるようにする。

**変更するファイル:**
- `backend/app/execution/execution_planner.py`

> 設計は `docs/phase7/phase7_design.md` §6 を参照。

**実装内容:**
- `plan()` に `kind_mode` パラメータを追加（デフォルト: `"common"`）
- `kind_mode="common"` → 共通 kind を生成（`audience.label.assign` 等）
- `kind_mode="domain"` → 従来通りドメイン kind を生成（Phase 5 互換）
- 自然文に「LINE で」「メールで」等のドメイン指定がある場合、step に `domain_hint` を付与

**domain_hint の検出ロジック:**

| 自然文のキーワード | domain_hint |
|---|---|
| LINE、ライン | `"line"` |
| メール、mail、email | `"email"` |
| 指定なし | `None`（WorkloadRunner が default domain で解決） |

**API の変更:**
- `POST /api/plan` のリクエストに `kind_mode` パラメータを追加（任意、デフォルト "common"）

**テスト:** 既存の ExecutionPlanner テストに共通 kind のテストケースを追加

**完了条件:**
- `kind_mode="common"` で共通 kind が生成される
- `kind_mode="domain"` で従来通りドメイン kind が生成される（後方互換）
- domain_hint が正しく付与される
- 既存の plan テストが壊れない

---

## Task 4: domain_configs への priority カラム追加

**作業:** 複数ドメインが有効な場合の解決順序を管理する priority カラムを追加する。

**追加するファイル:**
- `backend/app/db/migrations/versions/008_domain_config_priority.py`

**変更するテーブル:**
- `domain_configs` に `priority INTEGER NOT NULL DEFAULT 0` を追加

**priority の値:**
- LINE: 10（デフォルト最優先）
- Email: 20
- 値が小さいほど高優先

**変更するファイル:**
- `backend/app/db/models.py` — DomainConfig モデルに priority 追加
- `backend/app/db/repositories/domain_config_repo.py` — priority 順取得を追加

**完了条件:**
- マイグレーション正逆が動作する
- 既存の domain_configs レコードに priority が設定される
- `get_enabled_domains()` が priority 順で返る

---

## Task 5: Contact モデルの実装

**作業:** contacts / contact_channels テーブルを追加し、チャネル非依存の対象者管理を導入する。

> 設計は `docs/phase7/phase7_design.md` §4 を参照。

**追加するテーブル:**
- `contacts` — チャネル非依存の対象者
- `contact_channels` — チャネル別の外部 ID

> カラム定義は `docs/phase7/phase7_design.md` §4.3 を参照。

**追加するファイル:**
- `backend/app/db/migrations/versions/007_contacts.py`
- `backend/app/db/models.py` に追記
- `backend/app/db/repositories/contact_repo.py`
- `backend/app/schemas/contact.py`

**Contact CRUD:**
- `create_contact(display_name, channels: list[{channel_type, external_id}])` → contact + channels を作成
- `get_contact(contact_id)` → contact + channels を返す
- `find_by_external_id(channel_type, external_id)` → contact を逆引き
- `add_channel(contact_id, channel_type, external_id)` → チャネル追加
- `resolve_external_id(contact_id, channel_type)` → connector が使う外部 ID を取得

**テスト:** `backend/tests/test_contacts.py`

**完了条件:**
- contacts / contact_channels テーブルが作成される
- UNIQUE 制約 `(channel_type, external_id)` が機能する
- Contact の CRUD が動作する
- `resolve_external_id()` で channel_type ごとの外部 ID が取得できる

---

## Task 6: Connector の contact_id 対応

**作業:** connector が contact_id を受け取り、contact_channels から外部 ID を解決して使うようにする。

**変更するファイル:**
- `backend/app/domains/line/connector.py` — inputs に contact_id があれば resolve して LINE userId を取得
- `backend/app/domains/line/db_connector.py` — 同上
- `backend/app/domains/email/connector.py` — inputs に contact_id があれば resolve して email address を取得

**実装内容:**
- inputs に `contact_id` がある場合 → contact_channels から external_id を解決して使う
- inputs に `target_id` がある場合 → 従来通りそのまま使う（後方互換）
- どちらもない場合 → エラー

**テスト:** 既存の connector テストに contact_id 経由のテストケースを追加

**完了条件:**
- contact_id 経由で LINE userId が解決される
- contact_id 経由で email address が解決される
- target_id 直接指定も引き続き動作する（後方互換）
- contact_channels に該当チャネルがない場合にエラーメッセージが返る

---

## Task 7: Marketing API の追加

**作業:** 共通語彙ベースの API を追加する。

**追加するファイル:**
- `backend/app/api/routes_marketing.py`
- `backend/app/api/routes_contacts.py`

> 設計は `docs/phase7/phase7_design.md` §5.3 を参照。

**エンドポイント:**

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `GET /api/marketing/kinds` | GET | 共通 kind 一覧 + 各 kind の解決可能ドメイン |
| `GET /api/marketing/contacts` | GET | contact 一覧（ページネーション） |
| `GET /api/marketing/contacts/{contact_id}` | GET | contact 詳細 + channel 一覧 |
| `POST /api/marketing/contacts` | POST | contact 作成 + channel 紐付け |

**GET /api/marketing/kinds レスポンス例:**

```json
{
  "kinds": [
    {
      "kind": "audience.label.assign",
      "description": "対象者にラベルを付与する",
      "resolvable_domains": ["line"]
    },
    {
      "kind": "campaign.schedule",
      "description": "一斉配信を予約する",
      "resolvable_domains": ["line", "email"]
    }
  ]
}
```

**テスト:** `backend/tests/test_marketing_api.py`

**完了条件:**
- 共通 kind 一覧が返る（解決可能ドメイン付き）
- Contact CRUD API が動作する
- OpenAPI ドキュメントに反映される

---

## Task 8: Workload 状態 API の共通語彙対応

**作業:** Phase 6 で追加した Workload 状態 API のレスポンスに共通語彙キーを追加する。

**変更するファイル:**
- `backend/app/api/routes_workload_status.py`

> 設計は `docs/phase7/phase7_design.md` §5.2 を参照。

**実装内容:**
- `GET /api/workloads/summary` のレスポンスに `common` キーを追加
- 既存のキー（`scenarios`, `broadcasts` 等）はそのまま維持（後方互換）

**完了条件:**
- 既存のレスポンス形式が壊れない
- `common` キーに共通語彙（journeys, campaigns, followups, labels）のサマリが含まれる

---

## Task 9: 管理 UI の共通語彙対応

**作業:** Phase 6 で作成した管理 UI の表示ラベルを共通語彙に更新する。

**変更するファイル:**
- `admin/pages/05_workloads.py` — 画面タイトルとラベルを共通語彙に

**変更内容:**

| 変更前 | 変更後 |
|---|---|
| 「Scenarios」 | 「Journeys（シナリオ）」 |
| 「Broadcasts」 | 「Campaigns（配信）」 |
| 「Reminders」 | 「Follow-ups（リマインダ）」 |
| 「Tags」 | 「Audience Labels（タグ）」 |

括弧書きで LINE 由来の名称を残し、既存ユーザーの混乱を防ぐ。

**完了条件:**
- 管理 UI の全画面で共通語彙が表示される
- 括弧書きで LINE 名称が残っている

---

## Task 10: 展開可能性の説明資料

**作業:** 「LINE で動くが、他の集客アプリにも展開できる」ことを説明する資料を作成する。

**追加するファイル:**
- `docs/external/expansion-overview.md`

**内容:**
- 現在の製品概要（LINE 運用オーケストレーション）
- 内部の抽象化構造（共通 kind → ドメイン kind の二層）
- Contact モデルによるチャネル非依存
- Domain Module 構造（domains/ + Connector Registry）
- 展開可能な類似サービスの例（店舗向け集客アプリ、会員アプリ等）
- 新チャネル追加に必要な作業（connector + workload_kinds + config の 3 ファイル）

**完了条件:**
- 非エンジニアが読んで「他のアプリにも広げられる」と理解できる
- 技術的な裏付け（Domain Module / Registry / Contact モデル）が説明されている

---

## Task 11: テストの追加と回帰確認

**11.1 回帰テスト（最優先）**

| テストファイル | 内容 |
|---|---|
| `test_existing_convert.py` | Phase 1 回帰 |
| `test_existing_phase25.py` | Phase 2.5 回帰 |
| `test_existing_phase3.py` | Phase 3 回帰 |
| `test_existing_phase4.py` | Phase 4 回帰 |
| `test_existing_phase5.py` | Phase 5 回帰 |
| `test_existing_phase6.py` | Phase 6 回帰（**新規**） |

**11.2 後方互換テスト**

`backend/tests/test_backward_compat_phase7.py`:

- ドメイン kind（`line.tag.assign`）で plan → execute が動作する
- Phase 5 エイリアス（`tag.assign`）で plan → execute が動作する
- target_id 直接指定で execute が動作する
- 既存の plan_json（ドメイン kind 入り）を GET /api/plans で取得できる

**11.3 新規テスト**

| テストファイル | 対象 |
|---|---|
| `test_common_kinds.py` | 共通 kind 登録・resolution マッピング |
| `test_kind_resolver.py` | Kind Resolver の全パターン |
| `test_contacts.py` | Contact / ContactChannel CRUD |
| `test_marketing_api.py` | Marketing API / Contact API |
| `test_backward_compat_phase7.py` | 後方互換 |

> テストの記述ルールは `docs/test-instruction-template.md` に従うこと。

**完了条件:**
- 全テストが通る
- 回帰テスト（Phase 1〜6）が通る
- `tests/evidence/` にエビデンスが保存されている

---

## Task 12: README / docs の更新

**作業:**
- README.md に Phase 7 の説明を追加
- アーキテクチャ図を更新（Kind Resolver + Contact Model を含める）

**完了条件:**
- README に Phase 7 の説明がある
- 共通語彙と workload kind 二層化の概要が記載されている

---

## 実装順序

```
 1. 共通 Workload Kind の定義（Task 1）
 2. Kind Resolver の実装（Task 2）
 3. ExecutionPlanner の共通 kind 対応（Task 3）
 4. domain_configs への priority 追加（Task 4）
 5. Contact モデルの実装（Task 5）
 6. Connector の contact_id 対応（Task 6）
 7. Marketing API の追加（Task 7）
 8. Workload 状態 API の共通語彙対応（Task 8）
 9. 管理 UI の共通語彙対応（Task 9）
10. 展開可能性の説明資料（Task 10）
11. テスト追加と回帰確認（Task 11）
12. README / docs 更新（Task 12）
```

---

## 検証手順（Phase 7 完了時に実行）

```bash
# 1. マイグレーション
cd backend && alembic upgrade head

# 2. 全フェーズ回帰テスト
cd backend && pytest tests/test_existing_*.py -v

# 3. 後方互換テスト
cd backend && pytest tests/test_backward_compat_phase7.py -v

# 4. Phase 7 新規テスト
cd backend && pytest tests/test_common_kinds.py tests/test_kind_resolver.py tests/test_contacts.py tests/test_marketing_api.py -v

# 5. E2E: 共通 kind で plan → Kind Resolver → execute
# 6. E2E: 既存ドメイン kind で plan → execute（後方互換）
# 7. E2E: contact_id 経由の execute

# 8. エビデンス保存
cd backend && pytest tests/ -v > tests/evidence/phase7_test_result.txt
```

---

## 絶対に避けるべきこと

1. Agent 層のコードを変更する
2. 既存 DB テーブル名を変更する（tags, broadcasts, scenarios, reminders 等）
3. 既存 API レスポンスの既存キーを削除する（追加のみ）
4. ドメイン kind（`line.tag.assign` 等）を無効にする（後方互換必須）
5. Phase 5 のエイリアス（`tag.assign` → `line.tag.assign`）を無効にする
6. target_id カラムを既存テーブルから削除する（Phase 9 以降で判断）
7. Contact モデルを使わない限り既存フローが壊れる設計にする
8. capability 定義を導入する（→ Phase 8 の責務）
9. Alembic マイグレーションなしのテーブル変更
