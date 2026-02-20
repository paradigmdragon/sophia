from datetime import UTC, datetime

from core.forest import layout as forest_layout
from core.forest.canopy import build_canopy_data
from core.memory.schema import QuestionPool, WorkPackage, create_session_factory


def _work_row(*, work_id: str, status: str, context_tag: str = "work") -> WorkPackage:
    now = datetime.now(UTC)
    return WorkPackage(
        id=work_id,
        title=work_id,
        description=f"desc:{work_id}",
        payload={"work_packet": {"kind": "IMPLEMENT", "context_tag": context_tag}},
        context_tag=context_tag,
        status=status,
        linked_node="auth-module",
        created_at=now,
        updated_at=now,
        completed_at=now if status == "DONE" else None,
    )


def test_canopy_excludes_learning_summary_and_exposes_module_overview(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")

    db_url = f"sqlite:///{tmp_path / 'canopy_state.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add_all(
            [
                _work_row(work_id="wp_ready", status="READY"),
                _work_row(work_id="wp_progress", status="IN_PROGRESS"),
                _work_row(work_id="wp_done", status="DONE"),
            ]
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session)
        assert "learning_summary" not in data
        assert "module_overview" in data
        assert "roadmap" in data
        assert "sone_summary" in data

        module_ids = {row["module"] for row in data["module_overview"]}
        assert {"chat", "note", "editor", "subtitle", "forest"}.issubset(module_ids)
    finally:
        session.close()


def test_module_overview_progress_is_computed_from_work_status(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")

    db_url = f"sqlite:///{tmp_path / 'canopy_module_progress.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add_all(
            [
                _work_row(work_id="wp_forest_1", status="DONE", context_tag="work"),
                _work_row(work_id="wp_forest_2", status="DONE", context_tag="work"),
                _work_row(work_id="wp_forest_3", status="BLOCKED", context_tag="work"),
            ]
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session)
        forest_row = next(row for row in data["module_overview"] if row["module"] == "forest")
        assert forest_row["work_total"] == 3
        assert forest_row["done"] == 2
        assert forest_row["blocked"] == 1
        assert forest_row["dev_progress_pct"] == 67
        assert forest_row["progress_pct"] == 67
    finally:
        session.close()


def test_module_overview_progress_is_capped_when_question_risk_remains(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")

    db_url = f"sqlite:///{tmp_path / 'canopy_module_progress_question.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add_all(
            [
                _work_row(work_id="wp_forest_done_1", status="DONE", context_tag="work"),
                _work_row(work_id="wp_forest_done_2", status="DONE", context_tag="work"),
                QuestionPool(
                    cluster_id="scope_ambiguity",
                    description="범위가 명확하지 않음",
                    hit_count=3,
                    risk_score=0.92,
                    linked_nodes=["auth-module"],
                    status="ready_to_ask",
                ),
            ]
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session)
        forest_row = next(row for row in data["module_overview"] if row["module"] == "forest")
        assert forest_row["work_total"] >= 2
        assert forest_row["done"] == 2
        assert forest_row["pending_questions"] == 1
        assert forest_row["progress_pct"] < 100
        assert int(data["roadmap"]["remaining_work"]) >= 1
        assert int(forest_row.get("dev_progress_pct", 0) or 0) >= 66
    finally:
        session.close()
