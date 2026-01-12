"""
Orchestratorのリトライ挙動と戻り値を確認する。

入出力: Orchestrator.convert を呼び、定義とメタ情報を検証する。
制約: 外部LLMは使わずスタブ実装で検証する。

Note:
    - issues が出る想定で retries >= 1 を確認する
"""

from app.agent.orchestrator import Orchestrator
from app.agent.schemas import BusinessDefinition


def test_orchestrator_retries_and_returns_definition() -> None:
    """リトライが動作し、定義が返ることを確認する。

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
        - issues が出る想定で retries >= 1 を検証する
    """
    orchestrator = Orchestrator()
    definition, agent_logs, meta = orchestrator.convert("Approve expenses")

    assert isinstance(definition, BusinessDefinition)
    assert meta["retries"] >= 1
    assert any(log.get("step") == "validator" for log in agent_logs)
