from core.engine.local_brain import build_intent_reply, build_notice, build_question_prompt, classify_intent


def test_classify_intent_routes_to_part3_categories():
    assert classify_intent("네 진행해줘") in {"approve", "directive"}
    assert classify_intent("취소해") == "reject"
    assert classify_intent("잠시 보류") == "hold"
    assert classify_intent("왜 이렇게 됐어?") == "question"


def test_template_builders_use_external_templates():
    reply = build_intent_reply("directive", "이 작업 구현해줘")
    assert isinstance(reply, str)
    assert reply.strip()

    question = build_question_prompt("dependency_missing")
    assert "의존" in question

    notice = build_notice("notice.ide_ready")
    assert "IDE 작업 패킷" in notice
