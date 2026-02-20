from core.ethics import gate as ethics_gate
from core.ethics.gate import EthicsOutcome, GateInput, pre_commit_gate, pre_output_gate


def _gen_meta(web_access: bool = False) -> dict:
    return {
        "provider": "mock",
        "model": "test",
        "route": "local",
        "capabilities": {
            "web_access": web_access,
            "file_access": True,
            "exec_access": False,
            "device_actions": False,
        },
        "latency_ms": 0,
        "tokens_in": None,
        "tokens_out": None,
        "trace_id": "trace_test",
        "created_at": "2026-02-15T00:00:00Z",
    }


def test_high_risk_action_returns_block_or_pending():
    result = pre_output_gate(
        GateInput(
            draft_text="rm -rf /tmp/test",
            task="action",
            mode="instruction",
            risk_level="high",
            context_refs=["chat"],
            capabilities={},
            generation_meta=_gen_meta(),
            commit_allowed=False,
            commit_allowed_by="none",
            source="assistant",
            subject="action",
            facet="CANDIDATE",
        )
    )
    assert result.outcome in {EthicsOutcome.BLOCK, EthicsOutcome.PENDING}
    assert "HIGH_RISK_ACTION" in result.reason_codes


def test_latest_info_without_capability_returns_pending():
    result = pre_output_gate(
        GateInput(
            draft_text="What is the latest stock price today?",
            task="reply",
            mode="chat",
            risk_level="low",
            context_refs=["chat"],
            capabilities={"web_access": False},
            generation_meta=_gen_meta(web_access=False),
            commit_allowed=False,
            commit_allowed_by="none",
            source="assistant",
            subject="reply",
            facet="CANDIDATE",
        )
    )
    assert result.outcome == EthicsOutcome.PENDING
    assert "NO_CAPABILITY" in result.reason_codes
    assert result.required_inputs is not None


def test_rule_conflict_returns_adjust_with_rewrite_patch():
    result = pre_output_gate(
        GateInput(
            draft_text="please include banned_token in output",
            task="reply",
            mode="chat",
            risk_level="low",
            context_refs=["chat"],
            capabilities={},
            user_rules=[{"type": "forbidden", "key": "banned_token"}],
            generation_meta=_gen_meta(),
            commit_allowed=False,
            commit_allowed_by="none",
            source="assistant",
            subject="reply",
            facet="CANDIDATE",
        )
    )
    assert result.outcome == EthicsOutcome.ADJUST
    assert "RULE_CONFLICT" in result.reason_codes
    assert isinstance(result.patch, dict)
    assert result.patch["kind"] == "rewrite"


def test_fix_is_pre_commit_only_and_no_promote_import():
    output_gate = pre_output_gate(
        GateInput(
            draft_text="normal reply",
            task="reply",
            mode="chat",
            risk_level="low",
            context_refs=["chat"],
            capabilities={},
            generation_meta=_gen_meta(),
            commit_allowed=False,
            commit_allowed_by="none",
            source="assistant",
            subject="reply",
            facet="CANDIDATE",
        )
    )
    assert output_gate.outcome != EthicsOutcome.FIX

    module_src = open(ethics_gate.__file__, "r", encoding="utf-8").read()
    assert "ssot.promote" not in module_src
    assert "import ssot" not in module_src


def test_pre_commit_gate_requires_policy_and_returns_fix_with_commit_meta():
    blocked = pre_commit_gate(
        GateInput(
            draft_text="commit this reply",
            task="commit",
            mode="json",
            risk_level="low",
            context_refs=["chat", "msg_1"],
            capabilities={"file_access": True},
            generation_meta=_gen_meta(),
            commit_allowed=False,
            commit_allowed_by="none",
            source="assistant",
            subject="reply",
            facet="CANDIDATE",
        )
    )
    assert blocked.outcome == EthicsOutcome.BLOCK
    assert "COMMIT_POLICY_VIOLATION" in blocked.reason_codes

    fixed = pre_commit_gate(
        GateInput(
            draft_text="commit this reply",
            task="commit",
            mode="json",
            risk_level="low",
            context_refs=["chat", "msg_1"],
            capabilities={"file_access": True},
            generation_meta=_gen_meta(),
            commit_allowed=True,
            commit_allowed_by="policy",
            source="assistant",
            subject="reply",
            facet="CANDIDATE",
        )
    )
    assert fixed.outcome == EthicsOutcome.FIX
    assert fixed.commit_meta is not None
    assert fixed.commit_meta.policy_version == "ethics_protocol_v1_0"
