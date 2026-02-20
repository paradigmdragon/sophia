from datetime import UTC, datetime
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import forest_router
from core.engine.schema import Base as EngineBase
from core.engine.schema import Episode, Event
from core.forest import layout as forest_layout
from core.forest.canopy import build_canopy_data
from core.memory.schema import QuestionPool, WorkPackage, create_session_factory


def _work_row(*, work_id: str, status: str, context_tag: str, linked_node: str) -> WorkPackage:
    now = datetime.now(UTC)
    return WorkPackage(
        id=work_id,
        title=work_id,
        description=work_id,
        payload={"work_packet": {"kind": "IMPLEMENT", "context_tag": context_tag}},
        context_tag=context_tag,
        status=status,
        linked_node=linked_node,
        created_at=now,
        updated_at=now,
        completed_at=now if status == "DONE" else None,
    )


def _build_client(tmp_path, monkeypatch) -> tuple[TestClient, Path]:
    db_url = f"sqlite:///{tmp_path / 'canopy_phase_a.db'}"
    session_factory = create_session_factory(db_url)
    forest_router.session_factory = session_factory

    forest_root = tmp_path / "forest" / "project"
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", forest_root)
    monkeypatch.setattr(forest_router, "BASE_DIR", tmp_path)
    monkeypatch.setattr(forest_router, "WORKSPACE_ROOT", tmp_path / "workspace")
    monkeypatch.setattr(forest_router, "SOPHIA_WORKSPACE_ROOT", tmp_path / "sophia_workspace")

    app = FastAPI()
    app.include_router(forest_router.router)
    return TestClient(app), forest_root


def test_module_sort_progress_orders_desc(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")

    db_url = f"sqlite:///{tmp_path / 'canopy_module_sort.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add_all(
            [
                _work_row(work_id="wp_chat_done", status="DONE", context_tag="chat", linked_node="chat-core"),
                _work_row(work_id="wp_forest_done", status="DONE", context_tag="work", linked_node="auth-module"),
                _work_row(work_id="wp_forest_blocked", status="BLOCKED", context_tag="work", linked_node="auth-module"),
                _work_row(work_id="wp_note_ready", status="READY", context_tag="note", linked_node="note-core"),
            ]
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session, module_sort="progress")
        modules = data["module_overview"]
        progress_values = [int(row["progress_pct"]) for row in modules]
        assert progress_values == sorted(progress_values, reverse=True)
        assert modules[0]["module"] == "chat"
        assert all("dev_progress_pct" in row for row in modules)

        work_nodes = [row for row in data["nodes"] if row.get("type") == "work"]
        assert work_nodes
        sample = work_nodes[0]
        assert "module" in sample
        assert "module_label" in sample
        assert "priority_score" in sample
        assert "linked_risk" in sample
        bitmap_health = data.get("bitmap_health", {})
        assert isinstance(bitmap_health, dict)
        assert "adoption_rate" in bitmap_health
        assert "invalid_count_7d" in bitmap_health
        assert "duplicate_combined_groups" in bitmap_health
        bitmap_pipeline = data.get("bitmap_pipeline", {})
        assert isinstance(bitmap_pipeline, dict)
        assert bitmap_pipeline.get("status") in {"healthy", "warning", "critical"}
        assert isinstance(bitmap_pipeline.get("next_action", ""), str)
        roadmap_journal = data.get("roadmap_journal", {})
        assert isinstance(roadmap_journal, dict)
        assert "entries" in roadmap_journal
        human_quick = (data.get("human_view") or {}).get("quick_lists", {})
        assert isinstance(human_quick.get("recorded_top", []), list)
    finally:
        session.close()


def test_focus_current_mission_falls_back_to_pending_when_no_in_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")
    db_url = f"sqlite:///{tmp_path / 'canopy_focus_fallback.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add_all(
            [
                _work_row(work_id="wp_blocked_p100", status="BLOCKED", context_tag="work", linked_node="forest:canopy"),
                _work_row(work_id="wp_ready_p40", status="READY", context_tag="work", linked_node="forest:canopy"),
            ]
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session, view="focus")
        focus = data.get("focus", {})
        current = focus.get("current_mission")
        assert isinstance(current, dict)
        assert str(current.get("id", "")).strip() in {"wp_blocked_p100", "wp_ready_p40"}
        assert str(current.get("status", "")).upper() in {"BLOCKED", "READY", "FAILED"}
        assert isinstance((focus.get("next_action") or {}).get("text", ""), str)
    finally:
        session.close()


def test_canopy_injects_virtual_plan_when_all_work_done(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")
    db_url = f"sqlite:///{tmp_path / 'canopy_virtual_plan.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add_all(
            [
                _work_row(work_id="wp_done_1", status="DONE", context_tag="work", linked_node="forest:canopy"),
                _work_row(work_id="wp_done_2", status="DONE", context_tag="work", linked_node="forest:canopy"),
            ]
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session, view="focus")
        pending = data.get("roadmap", {}).get("pending", [])
        assert isinstance(pending, list)
        assert pending
        assert str(pending[0].get("id", "")).startswith("virtual_plan:")
        assert int(data.get("roadmap", {}).get("remaining_work", 0) or 0) >= 1

        forest_row = next(row for row in data.get("module_overview", []) if str(row.get("module")) == "forest")
        assert int(forest_row.get("progress_pct", 0) or 0) < 100
    finally:
        session.close()


def test_canopy_uses_roadmap_journal_virtual_plan_when_no_work(tmp_path, monkeypatch):
    forest_root = tmp_path / "forest" / "project"
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", forest_root)
    db_url = f"sqlite:///{tmp_path / 'canopy_roadmap_virtual_plan.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        project_status = forest_root / "sophia" / "status"
        project_status.mkdir(parents=True, exist_ok=True)
        journal_path = project_status / "roadmap_journal.jsonl"
        journal_entry = {
            "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "project": "sophia",
            "type": "SYNC_CHANGE",
            "category": "PROBLEM_FIX",
            "title": "canopy sync 기준 강화",
            "summary": "로드맵 동기화 중복 억제와 계획 우선순위 정리",
            "files": ["core/forest/canopy.py"],
            "tags": ["forest", "sync"],
            "fingerprint": "sha256:test-roadmap-virtual-plan",
        }
        journal_path.write_text(json.dumps(journal_entry, ensure_ascii=False) + "\n", encoding="utf-8")

        data = build_canopy_data(project_name="sophia", session=session, view="focus")
        pending = data.get("roadmap", {}).get("pending", [])
        assert isinstance(pending, list)
        assert pending
        assert str(pending[0].get("id", "")).startswith("virtual_plan:roadmap:")
        assert "canopy sync 기준 강화" in str(pending[0].get("title", ""))

        forest_row = next(row for row in data.get("module_overview", []) if str(row.get("module")) == "forest")
        assert int(forest_row.get("progress_pct", 0) or 0) < 100
    finally:
        session.close()


def test_canopy_treats_acknowledged_question_as_open_and_caps_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")
    db_url = f"sqlite:///{tmp_path / 'canopy_acknowledged_progress.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add(_work_row(work_id="wp_done_only", status="DONE", context_tag="work", linked_node="forest:canopy"))
        session.add(
            QuestionPool(
                cluster_id="scope_ack_open",
                description="범위 확인 필요",
                hit_count=2,
                risk_score=0.72,
                linked_nodes=["forest:canopy"],
                status="acknowledged",
                evidence=[{"source": "spec.md", "snippet": "scope unclear"}],
            )
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session, view="focus")
        forest_row = next(row for row in data.get("module_overview", []) if str(row.get("module")) == "forest")
        assert int(forest_row.get("pending_questions", 0) or 0) >= 1
        assert int(forest_row.get("progress_pct", 0) or 0) < 100
        assert int(data.get("roadmap", {}).get("remaining_work", 0) or 0) >= 1
    finally:
        session.close()


def test_canopy_generates_question_plan_when_only_high_risk_questions_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")
    db_url = f"sqlite:///{tmp_path / 'canopy_risk_plan.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add(
            QuestionPool(
                cluster_id="dependency_missing_high",
                description="의존성 미정",
                hit_count=3,
                risk_score=0.91,
                linked_nodes=["forest:analysis"],
                status="acknowledged",
                evidence=[{"source": "spec.md", "snippet": "dependency unknown"}],
            )
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session, view="focus")
        pending = data.get("roadmap", {}).get("pending", [])
        assert isinstance(pending, list)
        assert pending
        assert str(pending[0].get("id", "")).startswith("virtual_plan:risk:")
        assert "질문 클러스터 정리" in str(pending[0].get("title", ""))
    finally:
        session.close()


def test_canopy_virtual_plan_count_matches_high_risk_clusters(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")
    db_url = f"sqlite:///{tmp_path / 'canopy_risk_plan_count.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        session.add_all(
            [
                QuestionPool(
                    cluster_id="risk_alpha",
                    description="alpha",
                    hit_count=3,
                    risk_score=0.92,
                    linked_nodes=["forest:analysis"],
                    status="acknowledged",
                    evidence=[{"source": "spec.md", "snippet": "alpha"}],
                ),
                QuestionPool(
                    cluster_id="risk_beta",
                    description="beta",
                    hit_count=3,
                    risk_score=0.89,
                    linked_nodes=["forest:analysis"],
                    status="acknowledged",
                    evidence=[{"source": "spec.md", "snippet": "beta"}],
                ),
            ]
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session, view="focus")
        pending = data.get("roadmap", {}).get("pending", [])
        assert isinstance(pending, list)
        assert len(pending) >= 2

        forest_row = next(row for row in data.get("module_overview", []) if str(row.get("module")) == "forest")
        assert int(forest_row.get("ready", 0) or 0) >= 2
        assert int(forest_row.get("work_total", 0) or 0) >= 2
    finally:
        session.close()


def test_canopy_data_event_filter_canopy_only(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"

    init_res = client.post("/forest/projects/init", json={"project_name": project})
    assert init_res.status_code == 200

    analyze_res = client.post(
        f"/forest/projects/{project}/grove/analyze",
        json={
            "doc_name": "spec.md",
            "content": "# spec\n성공 조건 없음\n의존성 확인",
            "target": "auth-module",
            "change": "로그인 구조 검토",
        },
    )
    assert analyze_res.status_code == 200

    export_res = client.post(f"/forest/projects/{project}/canopy/export")
    assert export_res.status_code == 200

    data_res = client.get(f"/forest/projects/{project}/canopy/data?event_filter=canopy")
    assert data_res.status_code == 200
    body = data_res.json()
    assert body["filters"]["event_filter"] == "canopy"
    for event in body.get("recent_events", []):
        assert "CANOPY" in str(event.get("event_type", "")).upper()


def test_canopy_data_event_filter_bitmap_only(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"

    init_res = client.post("/forest/projects/init", json={"project_name": project})
    assert init_res.status_code == 200

    analyze_res = client.post(
        f"/forest/projects/{project}/grove/analyze",
        json={
            "doc_name": "spec.md",
            "content": "# spec\n성공 조건 없음\n의존성 확인",
            "target": "auth-module",
            "change": "로그인 구조 검토",
        },
    )
    assert analyze_res.status_code == 200

    response = client.get(f"/forest/projects/{project}/canopy/data?event_filter=bitmap")
    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["event_filter"] == "bitmap"
    allowed = {"PROPOSE", "ADOPT", "REJECT", "BITMAP_INVALID", "CONFLICT_MARK", "EPIDORA_MARK"}
    for event in body.get("recent_events", []):
        assert str(event.get("event_type", "")).upper() in allowed


def test_canopy_data_supports_pagination_and_module_filter(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    init_res = client.post("/forest/projects/init", json={"project_name": project})
    assert init_res.status_code == 200

    payload = {
        "kind": "IMPLEMENT",
        "linked_node": "chat-core",
        "issue": "status sync",
        "required": ["sync status"],
        "deliverables": ["report.json"],
    }
    for idx in range(4):
        response = client.post(
            f"/forest/projects/{project}/work/generate",
            json={**payload, "context_tag": "work", "issue": f"forest task {idx}", "linked_node": "auth-module"},
        )
        assert response.status_code == 200

    chat_work = client.post(
        f"/forest/projects/{project}/work/generate",
        json={**payload, "context_tag": "chat", "issue": "chat lane task", "linked_node": "chat-core"},
    )
    assert chat_work.status_code == 200

    paged = client.get(f"/forest/projects/{project}/canopy/data?limit=2&offset=1")
    assert paged.status_code == 200
    paged_body = paged.json()
    assert paged_body["filters"]["module"] == "all"
    assert paged_body["pagination"]["nodes"]["limit"] == 2
    assert paged_body["pagination"]["nodes"]["offset"] == 1
    assert len(paged_body["nodes"]) <= 2

    forest_only = client.get(f"/forest/projects/{project}/canopy/data?module=forest&limit=50&offset=0")
    assert forest_only.status_code == 200
    forest_body = forest_only.json()
    assert forest_body["filters"]["module"] == "forest"
    work_nodes = [row for row in forest_body.get("nodes", []) if row.get("type") == "work"]
    assert work_nodes
    assert all(str(row.get("module")) == "forest" for row in work_nodes)


def test_canopy_data_merges_bitmap_invalid_events_as_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")
    db_url = f"sqlite:///{tmp_path / 'canopy_bitmap_event.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        EngineBase.metadata.create_all(session.get_bind())
        now = datetime.now(UTC)
        session.add(Episode(episode_id="ep_bitmap_event", status="UNDECIDED", log_ref={"uri": "memory://test", "type": "test"}))
        session.add(
            Event(
                event_id="evt_bitmap_invalid_canopy",
                episode_id="ep_bitmap_event",
                type="BITMAP_INVALID",
                payload={"stage": "propose", "reason": "INVALID_CHUNK_A", "bits_raw": 0xF000},
                at=now,
            )
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session)
        events = data.get("recent_events", [])
        bitmap_events = [row for row in events if str(row.get("event_type", "")).upper() == "BITMAP_INVALID"]
        assert bitmap_events
        assert all(str(row.get("level")) == "warning" for row in bitmap_events)
        assert str((data.get("bitmap_pipeline") or {}).get("status")) == "critical"
        assert "BITMAP_INVALID" in str((data.get("bitmap_pipeline") or {}).get("next_action", ""))
        assert "bitmap" in str((data.get("focus") or {}).get("next_action", {}).get("ref", "")).lower()

        modules = data.get("module_overview", [])
        forest_row = next(row for row in modules if str(row.get("module")) == "forest")
        assert int(forest_row.get("bitmap_pressure", 0)) > 0
        assert int(forest_row.get("importance", 0)) > 40
    finally:
        session.close()


def test_canopy_data_merges_bitmap_lifecycle_events(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")
    db_url = f"sqlite:///{tmp_path / 'canopy_bitmap_lifecycle.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        EngineBase.metadata.create_all(session.get_bind())
        now = datetime.now(UTC)
        session.add(Episode(episode_id="ep_bitmap_lifecycle", status="UNDECIDED", log_ref={"uri": "memory://test", "type": "test"}))
        session.add_all(
            [
                Event(
                    event_id="evt_bitmap_propose",
                    episode_id="ep_bitmap_lifecycle",
                    type="PROPOSE",
                    payload={"count": 2, "source": "api_user"},
                    at=now,
                ),
                Event(
                    event_id="evt_bitmap_adopt",
                    episode_id="ep_bitmap_lifecycle",
                    type="ADOPT",
                    payload={"candidate_id": "cand_a", "backbone_id": "bb_a"},
                    at=now,
                ),
                Event(
                    event_id="evt_bitmap_reject",
                    episode_id="ep_bitmap_lifecycle",
                    type="REJECT",
                    payload={"candidate_id": "cand_b"},
                    at=now,
                ),
            ]
        )
        session.commit()

        data = build_canopy_data(project_name="sophia", session=session)
        events = data.get("recent_events", [])
        event_types = {str(row.get("event_type", "")).upper() for row in events}
        assert "PROPOSE" in event_types
        assert "ADOPT" in event_types
        assert "REJECT" in event_types

        filtered = build_canopy_data(project_name="sophia", session=session, event_filter="work")
        filtered_types = {str(row.get("event_type", "")).upper() for row in filtered.get("recent_events", [])}
        assert "ADOPT" in filtered_types
        assert "REJECT" in filtered_types

        bitmap_only = build_canopy_data(project_name="sophia", session=session, event_filter="bitmap")
        bitmap_types = {str(row.get("event_type", "")).upper() for row in bitmap_only.get("recent_events", [])}
        assert bitmap_types
        assert bitmap_types.issubset({"PROPOSE", "ADOPT", "REJECT", "BITMAP_INVALID", "CONFLICT_MARK", "EPIDORA_MARK"})
    finally:
        session.close()
