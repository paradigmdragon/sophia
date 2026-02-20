from datetime import UTC, datetime, timedelta

from core.forest import layout as forest_layout
from core.forest.canopy import build_canopy_data
from core.memory.schema import QuestionPool, WorkPackage, create_session_factory


def _work_row(*, work_id: str, status: str, updated_offset_min: int) -> WorkPackage:
    now = datetime.now(UTC) + timedelta(minutes=updated_offset_min)
    return WorkPackage(
        id=work_id,
        title=work_id,
        description=work_id,
        payload={"work_packet": {"kind": "IMPLEMENT", "context_tag": "work"}},
        context_tag="work",
        status=status,
        linked_node="auth-module",
        created_at=now,
        updated_at=now,
        completed_at=now if status == "DONE" else None,
    )


def test_roadmap_and_topology_are_present(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")

    db_url = f"sqlite:///{tmp_path / 'canopy_roadmap.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add_all(
            [
                _work_row(work_id="wp_a", status="READY", updated_offset_min=-10),
                _work_row(work_id="wp_b", status="IN_PROGRESS", updated_offset_min=-5),
                _work_row(work_id="wp_c", status="DONE", updated_offset_min=-1),
            ]
        )
        session.add(
            QuestionPool(
                cluster_id="scope_ambiguity",
                description="범위 불명확",
                hit_count=3,
                risk_score=0.85,
                evidence=[],
                linked_nodes=["auth-module"],
                status="ready_to_ask",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session)
        assert "learning_summary" not in data
        assert data["roadmap"]["total_work"] == 3
        assert len(data["roadmap"]["in_progress"]) == 1
        assert len(data["roadmap"]["pending"]) == 1
        assert len(data["roadmap"]["done_recent"]) == 1

        topology = data["topology"]
        assert isinstance(topology.get("nodes"), list)
        assert isinstance(topology.get("edges"), list)
        assert any(node.get("type") == "module" for node in topology["nodes"])
        assert any(node.get("type") == "work" for node in topology["nodes"])
    finally:
        session.close()
