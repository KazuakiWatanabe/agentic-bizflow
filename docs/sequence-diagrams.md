# Agentic BizFlow — シーケンス図

> 本ドキュメントは主要フローのシーケンス図（Mermaid 形式）です。

---

## 1. 業務文章変換フロー（Phase 1）

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Orch as Orchestrator
    participant Reader as ReaderAgent
    participant Planner as PlannerAgent
    participant Validator as ValidatorAgent
    participant Generator as GeneratorAgent

    Client->>API: POST /api/convert {text}
    API->>Orch: convert(text)
    Orch->>Reader: read(text)
    Reader-->>Orch: entities, actions
    Orch->>Planner: plan(entities, actions)
    Planner-->>Orch: tasks, roles
    Orch->>Validator: validate(tasks, roles)
    alt issues あり
        Validator-->>Orch: issues
        Orch->>Planner: re-plan(issues)
        Planner-->>Orch: revised tasks
        Orch->>Validator: validate(revised)
    end
    Validator-->>Orch: OK
    Orch->>Generator: generate(tasks, roles)
    Generator-->>Orch: BusinessDefinition
    Orch-->>API: definition, agent_logs, meta
    API-->>Client: ConvertResponse
```

---

## 2. 実行計画 → 承認 → 実行フロー（Phase 2.5〜4）

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Planner as ExecutionPlanner
    participant DB
    participant Runner as WorkloadRunner
    participant Conn as Connector

    Note over Client,Conn: Step 1: 実行計画の生成
    Client->>API: POST /api/plan {definition}
    API->>Planner: plan(definition)
    Planner-->>API: ExecutionPlan
    API->>DB: INSERT execution_plans (status=created)
    alt requires_approval = true
        API->>DB: INSERT approval_requests (status=pending)
    end
    API->>DB: INSERT execution_audit_logs (plan_created)
    API-->>Client: PlanResponse

    Note over Client,Conn: Step 2: 承認（承認必須の場合）
    Client->>API: GET /api/approvals?status=pending
    API-->>Client: 承認待ち一覧
    Client->>API: POST /api/approvals/{id}/approve
    API->>DB: UPDATE approval_requests SET status=approved
    API->>DB: INSERT execution_audit_logs (approval_decided)
    API-->>Client: ApprovalItem

    Note over Client,Conn: Step 3: Dry-run（任意）
    Client->>API: POST /api/dry-run {plan}
    API->>Runner: run(plan, dry_run=True)
    Runner->>Conn: dry_run(action, inputs)
    Conn-->>Runner: preview
    Runner-->>API: DryRunPreview
    API-->>Client: DryRunResponse

    Note over Client,Conn: Step 4: 本実行
    Client->>API: POST /api/execute {plan, approved=true}
    API->>DB: UPDATE execution_plans SET status=executing
    API->>Runner: run(plan, approved=true)

    loop 各 step
        Runner->>DB: 冪等性チェック (processed_idempotency_keys)
        alt 処理済み
            Runner-->>Runner: skip
        else 未処理
            Runner->>Conn: execute(action, inputs)
            Conn->>DB: ドメインテーブルに書き込み
            Conn-->>Runner: result
            Runner->>DB: INSERT processed_idempotency_keys
        end
        Runner->>DB: INSERT execution_audit_logs
    end

    Runner-->>API: ExecutionResult
    API->>DB: INSERT execution_results + step_results
    API->>DB: UPDATE execution_plans SET status=completed/failed
    API-->>Client: ExecuteResponse
```

---

## 3. 実行履歴照会フロー（Phase 3）

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant DB

    Client->>API: GET /api/executions
    API->>DB: SELECT execution_results ORDER BY started_at DESC
    DB-->>API: 実行結果一覧
    API-->>Client: ExecutionListResponse

    Client->>API: GET /api/executions/{execution_id}
    API->>DB: SELECT execution_results + step_results
    DB-->>API: 実行詳細
    API-->>Client: ExecutionDetailResponse
```

---

## 4. Scheduler 定期処理フロー（Phase 4）

```mermaid
sequenceDiagram
    participant Sched as Scheduler (5分間隔)
    participant StepW as StepDeliveryWorker
    participant BCW as BroadcastWorker
    participant RemW as ReminderWorker
    participant Conn as Connector
    participant DB

    Sched->>StepW: process_step_deliveries()
    StepW->>DB: SELECT scenario_enrollments WHERE status=active AND next_delivery_at <= now
    loop 各 enrollment
        StepW->>DB: 冪等性チェック
        StepW->>Conn: execute(scenario.deliver, inputs)
        Conn-->>StepW: result
        alt 成功
            StepW->>DB: UPDATE current_step_order, next_delivery_at
            alt 最終ステップ
                StepW->>DB: UPDATE status=completed
            end
        else 失敗
            StepW->>DB: UPDATE retry_count++
            alt max_retries 超過
                StepW->>DB: UPDATE status=failed
            end
        end
        StepW->>DB: INSERT execution_audit_logs
    end
    StepW->>DB: INSERT worker_task_logs

    Sched->>BCW: process_scheduled_broadcasts()
    BCW->>DB: SELECT broadcasts WHERE status=scheduled AND scheduled_at <= now
    loop 各 broadcast
        BCW->>DB: UPDATE status=sending
        BCW->>Conn: execute(broadcast.send, inputs)
        alt 成功
            BCW->>DB: UPDATE status=sent, sent_at=now
        else 失敗
            BCW->>DB: UPDATE status=failed
        end
        BCW->>DB: INSERT execution_audit_logs
    end
    BCW->>DB: INSERT worker_task_logs

    Sched->>RemW: process_reminder_deliveries()
    RemW->>DB: SELECT reminder_enrollments WHERE status=active
    loop 各 enrollment
        RemW->>DB: SELECT reminder_steps (未配信分)
        loop 各 due step
            RemW->>Conn: execute(reminder.deliver, inputs)
            alt 成功
                RemW->>DB: INSERT reminder_deliveries (UNIQUE制約で冪等性担保)
            end
        end
        alt 全ステップ完了
            RemW->>DB: UPDATE status=completed
        end
        RemW->>DB: INSERT execution_audit_logs
    end
    RemW->>DB: INSERT worker_task_logs
```

---

## 5. Cross-domain 実行フロー（Phase 5）

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Planner as ExecutionPlanner
    participant WKR as WorkloadKindRegistry
    participant Runner as WorkloadRunner
    participant CR as ConnectorRegistry
    participant LINE as LINE Connector
    participant EMAIL as Email Connector
    participant DB

    Client->>API: POST /api/plan {definition}
    API->>Planner: plan(definition)
    Planner->>WKR: get_all_keywords()
    WKR-->>Planner: kind → keywords マッピング
    Note over Planner: テキストとキーワードをマッチング
    Planner-->>API: ExecutionPlan (LINE + Email steps)
    API->>DB: INSERT execution_plans
    API-->>Client: PlanResponse

    Client->>API: POST /api/execute {plan, approved=true}
    API->>Runner: run(plan, approved=true)
    Runner->>CR: get("line")
    CR-->>Runner: LINE Connector
    Runner->>LINE: execute(line.tag.assign, inputs)
    LINE->>DB: INSERT tags + tag_assignments
    LINE-->>Runner: success

    Runner->>CR: get("line")
    Runner->>LINE: execute(line.broadcast.schedule, inputs)
    LINE->>DB: INSERT broadcasts (status=scheduled)
    LINE-->>Runner: success

    Runner->>CR: get("email")
    CR-->>Runner: Email Connector
    Runner->>EMAIL: execute(email.broadcast.schedule, inputs)
    EMAIL->>DB: INSERT email_broadcasts (status=scheduled)
    EMAIL-->>Runner: success

    Runner-->>API: ExecutionResult (3 steps success)
    API->>DB: INSERT execution_results + step_results
    API-->>Client: ExecuteResponse
```

---

## 6. ドメイン管理フロー（Phase 5）

```mermaid
sequenceDiagram
    participant Admin
    participant API as FastAPI
    participant DB
    participant WKR as WorkloadKindRegistry

    Admin->>API: GET /api/domains
    API->>DB: SELECT domain_configs
    API-->>Admin: ドメイン一覧

    Admin->>API: POST /api/domains/email/enable
    API->>DB: UPDATE domain_configs SET is_enabled=true
    API-->>Admin: 有効化完了

    Admin->>API: GET /api/workload-kinds
    API->>WKR: list_all()
    WKR-->>API: 全 kind 一覧
    API-->>Admin: WorkloadKindListResponse
```
