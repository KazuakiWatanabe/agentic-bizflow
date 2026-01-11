import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent.orchestrator import Orchestrator  # noqa: E402
from app.agent.schemas import BusinessDefinition  # noqa: E402


def test_orchestrator_retries_and_returns_definition() -> None:
    orchestrator = Orchestrator()
    definition, agent_logs, meta = orchestrator.convert('Approve expenses')

    assert isinstance(definition, BusinessDefinition)
    assert meta['retries'] >= 1
    assert any(log.get('step') == 'validator' for log in agent_logs)
