import pytest

from core.ai.ai_router import AIRouterService


def test_dual_run_remains_blocked():
    service = AIRouterService(provider_default="foundation", mode="fallback")
    with pytest.raises(ValueError, match="dual-run is disabled in phase1"):
        service.run(
            task="ingest",
            payload={"text": "dual-run block check"},
            provider="foundation",
            mode="dual-run",
        )
