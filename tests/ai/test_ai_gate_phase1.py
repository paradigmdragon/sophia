from core.ai.gate import validate_contract


def test_ingest_contract_validation_passes():
    contract, gate = validate_contract(
        "ingest",
        {
            "schema": "ingest_contract.v0.1",
            "summary_120": "요약 텍스트",
            "entities": [{"type": "concept", "text": "Sophia"}],
            "tags": ["ai", "ingest"],
            "context_tag": "chat",
            "confidence_model": 0.7,
        },
    )
    assert contract["schema"] == "ingest_contract.v0.1"
    assert gate["fallback_applied"] is False


def test_fallback_keeps_required_schema_shape():
    contract, gate = validate_contract("transcript", {"schema": "wrong"})
    assert gate["fallback_applied"] is True
    assert contract["schema"] == "transcript_contract.v0.1"
    assert "summary" in contract
    assert "action_items" in contract
    assert "decisions" in contract
    assert "open_questions" in contract
