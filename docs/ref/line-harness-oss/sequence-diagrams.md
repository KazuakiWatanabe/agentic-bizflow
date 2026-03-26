# シーケンス図

## 1. 友だち追加 → シナリオ開始

ユーザーが LINE 公式アカウントを友だち追加した際のフロー。

```mermaid
sequenceDiagram
    participant U as LINE ユーザー
    participant LP as LINE Platform
    participant W as Worker (Hono)
    participant DB as D1 Database
    participant EB as Event Bus

    U->>LP: 友だち追加
    LP->>W: POST /webhook (follow イベント)

    Note over W: 署名検証（マルチアカウント対応）
    W->>LP: GET profile (line_user_id)
    LP-->>W: displayName, pictureUrl

    W->>DB: upsertFriend()
    DB-->>W: friend レコード

    Note over W: line_account_id を設定（マルチアカウント時）

    W->>DB: getScenarios() — trigger_type = 'friend_add'
    DB-->>W: アクティブなシナリオ一覧

    loop 各 friend_add シナリオ
        W->>DB: enrollFriendInScenario()
        DB-->>W: friend_scenario レコード
        W->>DB: getScenarioSteps()
        DB-->>W: ステップ一覧

        alt 最初のステップが delay=0
            Note over W: テンプレート変数展開<br/>{{name}}, {{uid}} 等
            W->>LP: replyMessage (無料) — 即時配信
            W->>DB: INSERT messages_log

            alt 次のステップあり
                Note over W: 配信ウィンドウ (9:00-23:00 JST) 適用
                W->>DB: advanceFriendScenario()<br/>next_delivery_at を設定
            else 最後のステップ
                W->>DB: completeFriendScenario()
            end
        end
    end

    W->>EB: fireEvent('friend_add', {friendId, displayName})

    par 並列実行
        EB->>DB: applyScoring() — スコアリング
        EB->>DB: getActiveAutomationsByEvent() — 自動化ルール
        EB->>DB: getActiveNotificationRulesByEvent() — 通知
        EB-->>LP: Outgoing Webhook (HTTP POST)
    end

    W-->>LP: 200 OK (即座に応答)
```

## 2. ステップ配信 (Cron)

5 分間隔の Cron トリガーによるステップ配信処理。

```mermaid
sequenceDiagram
    participant CR as Cron Trigger
    participant W as Worker
    participant DB as D1 Database
    participant ST as Stealth Engine
    participant LP as LINE Platform

    CR->>W: scheduled() — */5 * * * *

    Note over W: JST 時刻チェック<br/>9:00-23:00 以外はスキップ

    W->>DB: getLineAccounts()
    DB-->>W: アクティブアカウント一覧

    loop 各アカウント
        W->>DB: getFriendScenariosDueForDelivery(now)
        DB-->>W: next_delivery_at ≤ now の<br/>friend_scenarios

        loop 各エンロールメント
            W->>DB: getFriendById()
            DB-->>W: friend レコード

            alt フォロー解除済み
                W->>DB: completeFriendScenario()
            else フォロー中
                W->>DB: getScenarioSteps()
                DB-->>W: ステップ一覧

                Note over W: current_step_order > の<br/>次ステップを特定

                alt condition_type あり
                    W->>DB: evaluateCondition()
                    DB-->>W: true / false

                    alt 条件不一致
                        Note over W: next_step_on_false or<br/>次のステップへスキップ
                        W->>DB: advanceFriendScenario()
                    end
                end

                Note over W: テンプレート変数展開<br/>{{name}}, {{uid}}, {{auth_url:CHANNEL_ID}}<br/>{{#if_ref}}...{{/if_ref}}

                W->>ST: addJitter(50, 200)
                ST-->>W: ランダム遅延 (ms)
                Note over W: sleep(jitter) — バースト回避

                W->>LP: pushMessage()
                W->>DB: INSERT messages_log

                alt 次のステップあり
                    W->>ST: enforceDeliveryWindow()
                    ST-->>W: ウィンドウ内の時刻
                    W->>ST: jitterDeliveryTime()
                    ST-->>W: ±5分のジッター追加
                    W->>DB: advanceFriendScenario()<br/>next_delivery_at を設定
                else 最後のステップ
                    W->>DB: completeFriendScenario()
                end
            end
        end
    end
```

## 3. ブロードキャスト送信

即時送信またはスケジュール配信のフロー。

```mermaid
sequenceDiagram
    participant C as Client (API/管理画面)
    participant W as Worker
    participant DB as D1 Database
    participant ST as Stealth Engine
    participant LP as LINE Platform

    alt 即時送信
        C->>W: POST /api/broadcasts/:id/send
    else 予約配信 (Cron)
        Note over W: processScheduledBroadcasts()<br/>status=scheduled, scheduled_at ≤ now
    end

    W->>DB: updateBroadcastStatus('sending')
    W->>DB: getBroadcastById()
    DB-->>W: broadcast レコード

    alt target_type = 'all'
        W->>LP: broadcast() — 全フォロワーに配信
    else target_type = 'tag'
        W->>DB: getFriendsByTag(target_tag_id)
        DB-->>W: フォロー中の友だち一覧

        Note over W: MULTICAST_BATCH_SIZE = 500

        loop 各バッチ (500件ずつ)
            alt batchIndex > 0
                W->>ST: calculateStaggerDelay()
                Note over ST: ≤100人: 100-600ms<br/>≤1000人: ~2分間に分散<br/>>1000人: ~5分間に分散
                ST-->>W: 遅延時間
                Note over W: sleep(delay)
            end

            alt text メッセージ & 複数バッチ
                W->>ST: addMessageVariation()
                Note over ST: zero-width 文字を挿入<br/>視覚的に同一だが<br/>バイナリは異なる
                ST-->>W: 変異メッセージ
            end

            W->>LP: multicast(lineUserIds, [message])

            loop 各友だち (バッチ内)
                W->>DB: INSERT messages_log
            end
        end
    end

    W->>DB: updateBroadcastStatus('sent',<br/>{totalCount, successCount})
```

## 4. メッセージ受信 → 自動返信

ユーザーからのテキストメッセージ受信と自動返信のフロー。

```mermaid
sequenceDiagram
    participant U as LINE ユーザー
    participant LP as LINE Platform
    participant W as Worker
    participant DB as D1 Database
    participant EB as Event Bus

    U->>LP: テキストメッセージ送信
    LP->>W: POST /webhook (message イベント)

    Note over W: 署名検証

    W->>DB: getFriendByLineUserId()
    DB-->>W: friend レコード

    W->>DB: INSERT messages_log (incoming)

    W->>DB: upsertChatOnMessage()
    Note over DB: チャットステータス更新<br/>(オペレーター画面連携)

    alt 配信時間設定メッセージ
        Note over W: 正規表現マッチ:<br/>"配信時間は○時"
        W->>DB: UPDATE friends SET metadata<br/>(preferred_hour)
        W->>LP: replyMessage — 確認 Flex メッセージ
    else 通常メッセージ
        W->>DB: SELECT * FROM auto_replies<br/>WHERE is_active = 1
        DB-->>W: 自動返信ルール一覧

        loop 各ルール
            alt exact マッチ or contains マッチ
                Note over W: テンプレート変数展開
                W->>LP: replyMessage (無料)
                W->>DB: INSERT messages_log (outgoing)
                Note over W: break — 最初の一致で終了
            end
        end

        W->>EB: fireEvent('message_received',<br/>{friendId, text, matched})

        par 並列実行
            EB->>DB: applyScoring()
            EB->>DB: processAutomations()
            EB->>DB: processNotifications()
            EB-->>LP: Outgoing Webhooks
        end
    end

    W-->>LP: 200 OK
```

## 5. リマインダ配信 (Cron)

基準日からのオフセットに基づくカウントダウン配信。

```mermaid
sequenceDiagram
    participant CR as Cron Trigger
    participant W as Worker
    participant DB as D1 Database
    participant ST as Stealth Engine
    participant LP as LINE Platform

    CR->>W: scheduled()
    W->>W: processReminderDeliveries()

    W->>DB: getDueReminderDeliveries(now)
    Note over DB: target_date + offset_minutes ≤ now<br/>かつ未配信のステップを取得
    DB-->>W: 配信対象リスト

    loop 各 friend_reminder
        W->>ST: addJitter(50, 200)
        Note over W: sleep(jitter) — バースト回避

        W->>DB: getFriendById()
        DB-->>W: friend レコード

        alt フォロー解除済み
            Note over W: スキップ
        else フォロー中
            loop 各 reminder_step (未配信分)
                W->>LP: pushMessage()
                W->>DB: INSERT messages_log
                W->>DB: markReminderStepDelivered()
            end

            W->>DB: completeReminderIfDone()
            Note over DB: 全ステップ配信済み →<br/>status = 'completed'
        end
    end
```

## 6. BAN 検知 (Cron)

LINE アカウントのヘルスチェックと BAN 検知。

```mermaid
sequenceDiagram
    participant CR as Cron Trigger
    participant W as Worker
    participant DB as D1 Database
    participant LP as LINE Platform

    CR->>W: scheduled()
    W->>W: checkAccountHealth()

    W->>DB: getLineAccounts()
    DB-->>W: アクティブアカウント一覧

    loop 各アカウント
        W->>DB: COUNT messages_log<br/>(直近1時間の outgoing)
        DB-->>W: totalSent

        W->>LP: GET /v2/bot/info
        LP-->>W: HTTP ステータス

        alt 200 OK
            Note over W: risk_level = 'normal'
        else 403 Forbidden
            Note over W: risk_level = 'danger'<br/>⚠️ BAN の可能性
        else 429 Too Many Requests
            Note over W: risk_level = 'warning'<br/>レート制限超過
        end

        alt totalSent > 5000
            Note over W: risk_level = 'warning'<br/>大量送信警告
        end

        W->>DB: createAccountHealthLog()
    end
```

## 7. イベントバス処理

システムイベント発火時の並列処理フロー。

```mermaid
sequenceDiagram
    participant SRC as イベント発生源
    participant EB as Event Bus
    participant DB as D1 Database
    participant WH as 外部 Webhook
    participant LP as LINE Platform

    SRC->>EB: fireEvent(eventType, payload)

    par 1. Outgoing Webhook
        EB->>DB: getActiveOutgoingWebhooksByEvent()
        DB-->>EB: Webhook 一覧
        loop 各 Webhook
            Note over EB: HMAC-SHA256 署名生成<br/>(secret がある場合)
            EB->>WH: POST (JSON + X-Webhook-Signature)
        end
    and 2. スコアリング
        EB->>DB: applyScoring(friendId, eventType)
        Note over DB: scoring_rules とマッチ<br/>→ friend_scores に記録<br/>→ friends.score を更新
    and 3. 自動化ルール
        EB->>DB: getActiveAutomationsByEvent()
        DB-->>EB: 自動化ルール一覧
        loop 各ルール
            Note over EB: 条件マッチング:<br/>score_threshold, tag_id
            alt 条件一致
                loop 各アクション
                    alt add_tag / remove_tag
                        EB->>DB: タグ操作
                    else start_scenario
                        EB->>DB: enrollFriendInScenario()
                    else send_message
                        EB->>LP: pushMessage()
                    else send_webhook
                        EB->>WH: POST
                    else switch_rich_menu
                        EB->>LP: linkRichMenuToUser()
                    else set_metadata
                        EB->>DB: UPDATE friends.metadata
                    end
                end
                EB->>DB: createAutomationLog()
            end
        end
    and 4. 通知ルール
        EB->>DB: getActiveNotificationRulesByEvent()
        DB-->>EB: 通知ルール一覧
        loop 各ルール × 各チャネル
            EB->>DB: createNotification()
        end
    end
```

## 8. マルチアカウント Webhook ルーティング

複数 LINE アカウントを 1 つの Worker で処理する際のルーティング。

```mermaid
sequenceDiagram
    participant LP as LINE Platform
    participant W as Worker
    participant DB as D1 Database

    LP->>W: POST /webhook<br/>Body: { destination: "Uxxx", events: [...] }<br/>Header: X-Line-Signature: "abc123"

    W->>W: JSON パース

    alt destination あり
        W->>DB: getLineAccounts()
        DB-->>W: 全 LINE アカウント

        loop 各アカウント (is_active)
            W->>W: verifySignature(<br/>account.channel_secret,<br/>rawBody, signature)
            alt 署名一致
                Note over W: channelSecret = account.secret<br/>channelAccessToken = account.token<br/>matchedAccountId = account.id
                Note over W: break
            end
        end
    end

    alt マッチしたアカウントなし
        Note over W: 環境変数のデフォルトアカウントで<br/>署名検証
    end

    W->>W: verifySignature(resolvedSecret)

    alt 署名無効
        W-->>LP: 200 OK (処理せず)
    else 署名有効
        Note over W: waitUntil で非同期処理開始<br/>(LINE は ~1秒以内の応答を要求)
        W-->>LP: 200 OK

        loop 各イベント
            W->>W: handleEvent(db, lineClient,<br/>event, matchedAccountId)
        end
    end
```

## 9. セグメント配信

タグ・メタデータ条件によるセグメント配信。

```mermaid
sequenceDiagram
    participant C as Client
    participant W as Worker
    participant SQ as Segment Query Builder
    participant DB as D1 Database
    participant ST as Stealth Engine
    participant LP as LINE Platform

    C->>W: POST /api/broadcasts/:id/send<br/>{ segment: { operator: "AND",<br/>  rules: [<br/>    { type: "tag_exists", value: "tag-id" },<br/>    { type: "is_following", value: true }<br/>  ]}}

    W->>SQ: buildSegmentQuery(condition)
    Note over SQ: SegmentRule の種類:<br/>・tag_exists / tag_not_exists<br/>・metadata_equals / metadata_not_equals<br/>・ref_code<br/>・is_following
    SQ-->>W: { sql, bindings }
    Note over SQ: SELECT f.id, f.line_user_id<br/>FROM friends f<br/>WHERE EXISTS (...) AND f.is_following = 1

    W->>DB: sql.all(bindings)
    DB-->>W: マッチした友だち一覧

    loop バッチ送信 (500件ずつ)
        W->>ST: calculateStaggerDelay()
        W->>LP: multicast()
        W->>DB: INSERT messages_log (各友だち)
    end

    W->>DB: updateBroadcastStatus('sent')
    W-->>C: 200 OK { broadcast }
```
