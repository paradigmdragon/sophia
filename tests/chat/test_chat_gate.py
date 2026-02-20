from core.chat.chat_gate import parse_validate_and_gate, validate_and_gate_contract


def test_answer_contract_passes_gate():
    raw = '{"schema":"chat_contract.v0.1","kind":"ANSWER","text":"요약 답변입니다.","needs":null,"task_plan":null,"sources":[{"type":"recent","ref":"msg:1"}],"confidence_model":0.82}'
    contract, gate = parse_validate_and_gate(raw, context={})
    assert contract["kind"] == "ANSWER"
    assert gate["evidence_scope"] in {"narrow", "medium", "broad"}
    assert gate["pass"] is True


def test_clarify_is_single_question():
    contract, gate = validate_and_gate_contract(
        {
            "schema": "chat_contract.v0.1",
            "kind": "CLARIFY",
            "text": "무엇을 원하시나요? 범위도 정해주실 수 있나요?",
            "needs": {"type": "scope", "options": ["auth"]},
            "task_plan": None,
            "sources": [{"type": "recent", "ref": "msg:2"}],
            "confidence_model": 0.2,
        },
        context={},
    )
    assert contract["kind"] == "CLARIFY"
    assert contract["text"].count("?") == 1
    assert gate["pass"] is True


def test_task_plan_contract_passes_gate():
    contract, gate = validate_and_gate_contract(
        {
            "schema": "chat_contract.v0.1",
            "kind": "TASK_PLAN",
            "text": "작업 계획을 제안합니다.",
            "needs": None,
            "task_plan": {
                "steps": [
                    {"title": "테스트 실행", "executor": "local", "inputs": {}},
                    {"title": "패치 적용", "executor": "ide", "inputs": {"path": "api/chat_router.py"}},
                ]
            },
            "sources": [{"type": "mind", "ref": "mind:task"}],
            "confidence_model": 0.71,
        },
        context={},
    )
    assert contract["kind"] == "TASK_PLAN"
    assert len(contract["task_plan"]["steps"]) == 2
    assert gate["pass"] is True


def test_json_parse_failure_falls_back_to_clarify():
    contract, gate = parse_validate_and_gate("not-a-json", context={"user_rules": [{"key": "scope"}]})
    assert contract["kind"] == "CLARIFY"
    assert gate["fallback_applied"] is True
    assert gate["reason"].startswith("parse_error")
