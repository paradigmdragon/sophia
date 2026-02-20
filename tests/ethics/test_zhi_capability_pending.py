from core.ethics.gate import EthicsOutcome, GateInput, pre_output_gate


def test_zhi_capability_mismatch_for_latest_request_returns_pending():
    gen_meta = {
        "provider": "ollama",
        "model": "llama3",
        "route": "local",
        "capabilities": {
            "web_access": False,
            "file_access": False,
            "exec_access": False,
            "device_actions": False,
        },
        "latency_ms": 10,
        "tokens_in": None,
        "tokens_out": None,
        "trace_id": "trace_test",
        "created_at": "2026-02-15T00:00:00Z",
    }

    result = pre_output_gate(
        GateInput(
            draft_text="최신 환율 알려줘",
            task="reply",
            mode="chat",
            risk_level="med",
            context_refs=["chat"],
            capabilities={"web_access": False},
            generation_meta=gen_meta,
            commit_allowed=False,
            commit_allowed_by="none",
            source="assistant",
            subject="reply",
            facet="CANDIDATE",
        )
    )

    assert result.outcome == EthicsOutcome.PENDING
    assert "CAPABILITY_MISMATCH" in result.reason_codes
    assert result.required_inputs is not None
    assert "web_access" in result.required_inputs
