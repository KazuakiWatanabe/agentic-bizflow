"""
Orchestratorのリトライ挙動と戻り値を確認する。

入出力: Orchestrator.convert を呼び、定義とメタ情報を検証する。
制約: 外部LLMは使わずスタブ実装で検証する。

Note:
    - retries は 0 以上であれば許容する
"""

from app.agent.orchestrator import Orchestrator
from app.agent.schemas import BusinessDefinition


def test_orchestrator_returns_definition() -> None:
    """定義が返り、メタ情報が含まれることを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        orchestrator:
            テスト対象のOrchestrator。
        definition:
            生成された業務定義。
        agent_logs:
            Agentの要約ログ一覧。
        meta:
            retries などのメタ情報。

    Raises:
        AssertionError: 期待する結果が得られない場合に発生

    Note:
        - retries は 0 以上であれば許容する
    """
    orchestrator = Orchestrator()
    definition, agent_logs, meta = orchestrator.convert("Approve expenses")

    assert isinstance(definition, BusinessDefinition)
    assert meta["retries"] >= 0
    assert "actions_raw" in meta
    assert "actions_filtered_out" in meta
    assert any(log.get("step") == "validator" for log in agent_logs)


def test_orchestrator_splits_tasks_from_actions() -> None:
    """事前分割されたactionsがタスク分割に反映されることを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        orchestrator:
            テスト対象のOrchestrator。
        definition:
            生成された業務定義。
        meta:
            retries などのメタ情報。

    Raises:
        AssertionError: 期待する分割結果が得られない場合に発生
    """
    orchestrator = Orchestrator()
    definition, _, meta = orchestrator.convert(
        "経費を申請し、承認されたら精算し、通知する"
    )

    assert len(definition.tasks) >= 3
    assert len(meta.get("actions", [])) >= 3
    assert meta.get("splitter_version") == "ja_v1"
    assert meta.get("compound_detected") is True
    assert isinstance(meta.get("validator_issues"), list)


def test_orchestrator_filters_non_business_actions() -> None:
    """挨拶や雑談がタスク化されないことを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        orchestrator:
            テスト対象のOrchestrator。
        definition:
            生成された業務定義。
        meta:
            メタ情報。
        task_names:
            生成タスク名の一覧。

    Raises:
        AssertionError: 期待するフィルタ結果が得られない場合に発生
    """
    orchestrator = Orchestrator()
    definition, _, meta = orchestrator.convert(
        "田中さんおはようございます。今日は天気が良いです。"
        "経費を承認されたら精算し、鈴木さんに渡してください。"
    )

    assert any("おはよう" in action for action in meta.get("actions_raw", []))
    assert all("おはよう" not in action for action in meta.get("actions", []))
    assert any("天気" in action for action in meta.get("actions_filtered_out", []))

    task_names = [task.name for task in definition.tasks]
    assert all("おはよう" not in name for name in task_names)
    assert all("天気" not in name for name in task_names)


def test_orchestrator_triggers_are_not_global() -> None:
    """条件節のあるタスクのみトリガーが付与されることを確認する。

    Args:
        None

    Returns:
        None

    Variables:
        orchestrator:
            テスト対象のOrchestrator。
        definition:
            生成された業務定義。
        triggers:
            タスクに設定されたトリガー一覧。

    Raises:
        AssertionError: 全タスクにトリガーが付与される場合に発生
    """
    orchestrator = Orchestrator()
    definition, _, _ = orchestrator.convert(
        "経費を申請し、承認されたら精算し、通知する"
    )

    triggers = [task.trigger for task in definition.tasks]
    assert len(definition.tasks) >= 3
    assert any(trigger == "" for trigger in triggers)


def test_orchestrator_role_inference_and_recipients() -> None:
    """ロール推定と通知先の付与を確認する。

    Args:
        None

    Returns:
        None

    Variables:
        orchestrator:
            テスト対象のOrchestrator。
        definition:
            生成された業務定義。
        meta:
            メタ情報。
        roles:
            タスクに含まれるロール名一覧。
        people:
            抽出した人名一覧。
        contact_tasks:
            連絡/通知系タスクの一覧。

    Raises:
        AssertionError: 期待する推定が行われない場合に発生
    """
    orchestrator = Orchestrator()
    definition, _, meta = orchestrator.convert(
        "経費を申請し、承認されたら精算し、鈴木さんに連絡して下さい。"
    )

    roles = {task.role for task in definition.tasks}
    assert "Applicant" in roles
    assert "Approver" in roles
    assert "Accounting" in roles

    people = meta.get("entities", {}).get("people", [])
    assert any(person.get("name") == "鈴木" for person in people)

    assert any(
        item.get("inferred_role") == "Approver"
        for item in meta.get("role_inference", [])
    )

    contact_tasks = [
        task
        for task in definition.tasks
        if any(keyword in task.name for keyword in ["連絡", "通知", "共有", "送付"])
    ]
    assert contact_tasks
    assert any(
        any(recipient.name == "鈴木" for recipient in task.recipients)
        for task in contact_tasks
    )
