from __future__ import annotations

from typing import Any

TEMPLATE_A = "주인님, 지난주에 정리 중이던 {project_name}이 멈춰 있어요.\n잠시 쉬고 계신 건가요, 아니면 다시 이어가 볼까요?"
TEMPLATE_B = "주인님, 이 주제는 세 번째 등장했어요.\n이번에는 다른 관점으로 접근해 볼까요?"
TEMPLATE_C = "주인님, 기록이 7일간 없어요.\n지금은 정리의 시간이신가요, 아니면 멈춰 있는 상태인가요?"


def build_inactivity_question(context: dict[str, Any]) -> dict[str, Any]:
    has_incomplete_work = bool(context.get("has_incomplete_work", False))
    repeated_cluster = bool(context.get("repeated_cluster", False))
    active_project = bool(context.get("active_project", False))
    project_name = str(context.get("project_name") or "진행 중 작업")
    cluster_id = str(context.get("cluster_id") or "")

    if has_incomplete_work or active_project:
        text = TEMPLATE_A.format(project_name=project_name)
        template_id = "A"
    elif repeated_cluster:
        text = TEMPLATE_B
        template_id = "B"
    else:
        text = TEMPLATE_C
        template_id = "C"

    return {
        "template_id": template_id,
        "cluster_id": cluster_id,
        "question_text": text,
    }
