import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router, forest_router, work_router
from core.forest import layout as forest_layout
from core.memory.schema import create_session_factory


def _build_client(tmp_path, monkeypatch) -> tuple[TestClient, Path]:
    db_url = f"sqlite:///{tmp_path / 'forest_api.db'}"
    session_factory = create_session_factory(db_url)
    chat_router.session_factory = session_factory
    work_router.session_factory = session_factory
    forest_router.session_factory = session_factory
    chat_router._legacy_backfilled = True

    forest_root = tmp_path / "forest" / "project"
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", forest_root)
    monkeypatch.setattr(forest_router, "BASE_DIR", tmp_path)
    monkeypatch.setattr(forest_router, "WORKSPACE_ROOT", tmp_path / "workspace")
    monkeypatch.setattr(forest_router, "SOPHIA_WORKSPACE_ROOT", tmp_path / "sophia_workspace")

    app = FastAPI()
    app.include_router(chat_router.router)
    app.include_router(work_router.router)
    app.include_router(forest_router.router)
    return TestClient(app), forest_root


def test_forest_init_and_grove_analysis(tmp_path, monkeypatch):
    client, forest_root = _build_client(tmp_path, monkeypatch)

    init_res = client.post("/forest/projects/init", json={"project_name": "SonEsonjapgo"})
    assert init_res.status_code == 200
    project = "sonesonjapgo"
    project_root = forest_root / project
    assert (project_root / "docs").exists()
    assert (project_root / "analysis").exists()
    assert (project_root / "ledger").exists()
    assert (project_root / "questions").exists()
    assert (project_root / "status").exists()
    assert (project_root / "work").exists()

    analyze_res = client.post(
        f"/forest/projects/{project}/grove/analyze",
        json={
            "doc_name": "spec_v2.md",
            "content": "# 로그인 로직 수정\nsession-manager 영향 가능\n범위는 추후 결정",
            "target": "auth-module",
            "change": "로그인 로직 수정",
        },
    )
    assert analyze_res.status_code == 200
    body = analyze_res.json()
    assert body["status"] == "ok"
    assert (project_root / "analysis" / "last_delta.sone.json").exists()
    assert (project_root / "analysis" / "dependency_graph.json").exists()
    assert (project_root / "analysis" / "risk_snapshot.json").exists()
    snapshot = (project_root / "analysis" / "risk_snapshot.json").read_text(encoding="utf-8")
    assert "reason_code" in snapshot

    pool_rows = client.get("/chat/questions/pool").json()
    assert any(row["cluster_id"] == "scope_ambiguity" for row in pool_rows)


def test_project_init_seeds_bootstrap_roadmap_and_status_snapshot(tmp_path, monkeypatch):
    client, forest_root = _build_client(tmp_path, monkeypatch)
    project = "projectalpha"

    response = client.post("/forest/projects/init", json={"project_name": project})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["project"] == project
    assert int(body["bootstrap"]["recorded"] or 0) >= 1
    assert str(body["bootstrap"].get("path", "")).endswith("/status/roadmap_journal.jsonl")
    assert "inventory_seed" in body
    assert body["inventory_seed"]["status"] in {"ok", "error", "skipped"}
    assert body["status_sync"]["status"] in {"ok", "error", "skipped"}

    project_root = forest_root / project
    journal_path = project_root / "status" / "roadmap_journal.jsonl"
    assert journal_path.exists()
    journal_rows = [line for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(journal_rows) >= 1

    canopy_res = client.get(f"/forest/projects/{project}/canopy/data")
    assert canopy_res.status_code == 200
    canopy_data = canopy_res.json()
    roadmap_journal = canopy_data.get("roadmap_journal", {})
    assert int(roadmap_journal.get("total", 0) or 0) >= 1


def test_seed_work_from_inventory_creates_ready_tasks_and_dedupes(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "seedproj"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    first = client.post(
        f"/forest/projects/{project}/work/seed-from-inventory",
        json={"limit": 100, "include_statuses": ["READY", "IN_PROGRESS", "BLOCKED"]},
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["status"] == "ok"
    assert int(first_body.get("created_count", 0) or 0) >= 0
    assert int(first_body.get("skipped_existing", 0) or 0) >= 1

    second = client.post(
        f"/forest/projects/{project}/work/seed-from-inventory",
        json={"limit": 100, "include_statuses": ["READY", "IN_PROGRESS", "BLOCKED"]},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["status"] == "ok"
    assert int(second_body.get("created_count", 0) or 0) == 0
    assert int(second_body.get("skipped_existing", 0) or 0) >= 1

    forced = client.post(
        f"/forest/projects/{project}/work/seed-from-inventory",
        json={"limit": 100, "include_statuses": ["READY", "IN_PROGRESS", "BLOCKED"], "force": True},
    )
    assert forced.status_code == 200
    forced_body = forced.json()
    assert forced_body["status"] == "ok"
    assert int(forced_body.get("created_count", 0) or 0) >= 1
    assert isinstance(forced_body.get("items", []), list)


def test_work_generate_roots_export_and_canopy_split(tmp_path, monkeypatch):
    client, forest_root = _build_client(tmp_path, monkeypatch)
    project = "sophia"

    client.post("/forest/projects/init", json={"project_name": project})

    gen_res = client.post(
        f"/forest/projects/{project}/work/generate",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "auth-module",
            "issue": "success_condition missing",
            "required": ["define success criteria", "update spec", "verify dependency with session-manager"],
            "deliverables": ["work/package_001.md", "return_payload.json"],
        },
    )
    assert gen_res.status_code == 200
    work_package_id = gen_res.json()["work_package_id"]

    report_res = client.post(
        f"/work/packages/{work_package_id}/report",
        json={
            "work_package_id": work_package_id,
            "status": "BLOCKED",
            "signals": [
                {
                    "cluster_id": "scope_ambiguity",
                    "risk_score": 0.85,
                    "evidence": "범위 불명확",
                }
            ],
            "artifacts": ["logs/report.txt"],
            "notes": "waiting for user decision",
        },
    )
    assert report_res.status_code == 200

    export_res = client.post(f"/forest/projects/{project}/roots/export")
    assert export_res.status_code == 200
    project_root = forest_root / project
    assert (project_root / "questions" / "question_pool.json").exists()
    assert list((project_root / "work").glob("package_*.md"))
    assert (project_root / "status" / "export_meta.json").exists()

    canopy_data = client.get(f"/forest/projects/{project}/canopy/data")
    assert canopy_data.status_code == 200
    data = canopy_data.json()
    assert "nodes" in data
    assert "status_summary" in data
    assert "risk" in data
    assert "module_overview" in data
    assert "roadmap" in data
    assert "sone_summary" in data
    assert "question_queue" in data
    assert "focus" in data
    assert "current_mission_id" in data
    assert "next_action" in data
    assert "focus_lock" in data
    assert "frozen_ideas" in data
    assert "journey" in data
    assert "metrics" in data
    assert "sync_status" in data
    assert str(data["sync_status"].get("state", "")).strip().lower() in {"ok", "warning", "blocked", "unknown"}
    assert isinstance(data["sync_status"].get("label", ""), str)
    assert str(data["sync_status"].get("route_type", "")).strip() in {
        "sync-router",
        "status-sync",
        "roadmap-sync",
        "unknown",
    }
    assert "human_view" in data
    assert "ai_view" in data
    assert isinstance(data["human_view"].get("summary_cards", []), list)
    assert data["ai_view"].get("contract") == "canopy_ai_view.v0.1"
    assert data["journey"]["last_footprint"] == "Roots 내보내기 완료"
    assert isinstance(data["journey"]["next_step"], str) and data["journey"]["next_step"].strip()
    assert int(data["journey"]["streak_days"] or 0) >= 1
    assert "eta_hint" in data["roadmap"]
    assert "eta_days" in data["roadmap"]
    assert "done_last_7d" in data["roadmap"]
    assert "validation_stage" in data["sone_summary"]
    assert "reason_catalog_version" in data["sone_summary"]
    assert "risk_reasons" in data["sone_summary"]
    assert isinstance(data["sone_summary"]["risk_reasons"], list)
    if data["sone_summary"]["risk_reasons"]:
        assert "reason_code" in data["sone_summary"]["risk_reasons"][0]

    canopy_export = client.post(f"/forest/projects/{project}/canopy/export")
    assert canopy_export.status_code == 200
    dashboard_path = Path(canopy_export.json()["dashboard_path"])
    assert dashboard_path.exists()
    html = dashboard_path.read_text(encoding="utf-8")
    assert "Sophia Forest Canopy" in html
    assert "BLOCKED" in html
    assert "Module Overview" in html
    assert "SonE Validation Summary" in html
    assert 'data-canopy-id="work:' in html
    if data.get("question_queue"):
        assert "data-canopy-id='question:" in html
    assert "params.get(\"highlight\")" in html


def test_roadmap_record_snapshot_writes_journal(tmp_path, monkeypatch):
    client, forest_root = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200
    create = client.post(
        f"/forest/projects/{project}/work/generate",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "forest:canopy",
            "issue": "focus snapshot test",
            "required": ["acceptance 정의"],
        },
    )
    assert create.status_code == 200

    record = client.post(
        f"/forest/projects/{project}/roadmap/record",
        json={"note": "manual snapshot"},
    )
    assert record.status_code == 200
    body = record.json()
    assert body["status"] == "ok"
    journal_path = Path(body["path"])
    assert journal_path.exists()
    lines = [line for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    assert "summary_cards" in body["entry"]
    assert "roadmap_now" in body["entry"]
    assert body["entry"]["project"] == project
    assert body["recorded"] == 1
    assert body["skipped"] == 0
    assert body["recorded_items"][0]["category"] in {"SYSTEM_CHANGE", "PROBLEM_FIX", "FEATURE_ADD"}
    assert "forest/project/sophia/status/roadmap_journal.jsonl" in str(journal_path).replace("\\", "/")


def test_roadmap_record_snapshot_skips_ui_only_entry(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    response = client.post(
        f"/forest/projects/{project}/roadmap/record",
        json={
            "title": "focus panel spacing tweak",
            "summary": "ui margin 조정",
            "files": ["apps/desktop/src/pages/ReportPage.tsx"],
            "tags": ["ui"],
            "category": "UI_CHANGE",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recorded"] == 0
    assert body["skipped"] == 1
    assert any(str(row.get("reason", "")).startswith("policy_skip") for row in body.get("skipped_items", []))


def test_roadmap_sync_records_only_meaningful_categories(tmp_path, monkeypatch):
    client, forest_root = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    response = client.post(
        f"/forest/projects/{project}/roadmap/sync",
        json={
            "items": [
                {
                    "title": "chat router bug fix",
                    "summary": "context overwrite 오류 수정",
                    "files": ["api/chat_router.py"],
                    "tags": ["backend", "fix"],
                },
                {
                    "title": "forest new sync endpoint",
                    "summary": "sync handshake API 추가",
                    "files": ["api/sync_router.py", "core/forest_logic.py"],
                    "tags": ["feature"],
                },
                {
                    "title": "focus panel spacing tweak",
                    "summary": "ui margin 조정",
                    "files": ["apps/desktop/src/pages/ReportPage.tsx"],
                    "tags": ["ui"],
                },
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 3
    assert body["recorded"] == 2
    assert body["skipped"] == 1
    assert all(row["category"] in {"PROBLEM_FIX", "FEATURE_ADD", "SYSTEM_CHANGE"} for row in body["recorded_items"])
    assert any(row["reason"].startswith("policy_skip") for row in body["skipped_items"])

    journal_path = Path(body["path"])
    assert journal_path.exists()
    lines = [line for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 2
    sync_rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and str(row.get("type", "")).upper() == "SYNC_CHANGE":
            sync_rows.append(row)
    assert len(sync_rows) == 2


def test_roadmap_sync_deduplicates_same_item(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    payload = {
        "items": [
            {
                "title": "work router blocker fix",
                "summary": "focus lock policy fix",
                "files": ["api/work_router.py"],
                "tags": ["fix"],
            }
        ]
    }
    first = client.post(f"/forest/projects/{project}/roadmap/sync", json=payload)
    assert first.status_code == 200
    assert first.json()["recorded"] == 1

    second = client.post(f"/forest/projects/{project}/roadmap/sync", json=payload)
    assert second.status_code == 200
    body = second.json()
    assert body["recorded"] == 0
    assert body["skipped"] == 1
    assert any(row["reason"] == "duplicate" for row in body["skipped_items"])


def test_roadmap_journal_endpoint_returns_recent_records(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    sync_res = client.post(
        f"/forest/projects/{project}/roadmap/sync",
        json={
            "items": [
                {
                    "title": "forest status sync fix",
                    "summary": "status/sync 경로로 새로고침 통일",
                    "files": ["apps/desktop/src/pages/report/useReportController.ts"],
                    "tags": ["sync", "fix"],
                    "category": "SYSTEM_CHANGE",
                },
                {
                    "title": "report page spacing tweak",
                    "summary": "ui spacing only",
                    "files": ["apps/desktop/src/pages/ReportPage.tsx"],
                    "tags": ["ui"],
                    "category": "UI_CHANGE",
                },
            ]
        },
    )
    assert sync_res.status_code == 200

    journal_res = client.get(f"/forest/projects/{project}/roadmap/journal?limit=20")
    assert journal_res.status_code == 200
    body = journal_res.json()
    assert body["status"] == "ok"
    assert body["project"] == project
    assert int(body["total"]) >= 1
    assert isinstance(body.get("entries"), list)
    assert body["entries"]
    first = body["entries"][0]
    assert first["category"] in {"SYSTEM_CHANGE", "PROBLEM_FIX", "FEATURE_ADD"}
    assert "title" in first
    assert "summary" in first
    assert "category_counts" in body
    assert set(body["category_counts"].keys()) == {"FEATURE_ADD", "PROBLEM_FIX", "SYSTEM_CHANGE"}


def test_canopy_parallel_board_and_spec_endpoints(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    docs_dir = tmp_path / "Docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    spec_path = docs_dir / "sophia_parallel_spec.md"
    spec_path.write_text("# 병렬 작업 명세\n\n- owner/lane 분리\n", encoding="utf-8")

    sync_res = client.post(
        f"/forest/projects/{project}/roadmap/sync",
        json={
            "items": [
                {
                    "title": "parallel lane codex active",
                    "summary": "codex lane 진행중 작업",
                    "files": [str(spec_path), "core/forest/canopy.py"],
                    "spec_refs": [str(spec_path)],
                    "tags": ["owner:codex", "lane:codex", "scope:project", "review_state:draft"],
                    "category": "SYSTEM_CHANGE",
                    "owner": "codex",
                    "lane": "codex",
                    "scope": "project",
                    "review_state": "draft",
                }
            ]
        },
    )
    assert sync_res.status_code == 200
    assert int(sync_res.json().get("recorded", 0) or 0) >= 1

    canopy_res = client.get(f"/forest/projects/{project}/canopy/data")
    assert canopy_res.status_code == 200
    canopy = canopy_res.json()
    board = canopy.get("parallel_workboard", {})
    lanes = board.get("lanes", []) if isinstance(board, dict) else []
    assert any(str(row.get("owner", "")).strip() == "codex" for row in lanes)

    index_res = client.get(f"/forest/projects/{project}/spec/index")
    assert index_res.status_code == 200
    index_body = index_res.json()
    assert index_body["status"] == "ok"
    assert any(str(row.get("path", "")).strip() == str(spec_path) for row in index_body.get("items", []))

    read_res = client.get(f"/forest/projects/{project}/spec/read", params={"path": str(spec_path)})
    assert read_res.status_code == 200
    read_body = read_res.json()
    assert read_body["status"] == "ok"
    assert "병렬 작업 명세" in str(read_body.get("content", ""))

    review_res = client.post(
        f"/forest/projects/{project}/spec/review-request",
        json={"path": str(spec_path), "owner": "codex", "lane": "codex", "note": "검토 요청"},
    )
    assert review_res.status_code == 200
    review_body = review_res.json()
    assert review_body["status"] == "ok"
    assert int(review_body.get("recorded", 0) or 0) + int(review_body.get("skipped", 0) or 0) >= 1


def test_frozen_idea_lifecycle(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    freeze_res = client.post(
        f"/forest/projects/{project}/ideas/freeze",
        json={"title": "Canopy focus cockpit 개선", "tag": "forest"},
    )
    assert freeze_res.status_code == 200
    frozen = freeze_res.json()["idea"]
    assert frozen["status"] == "FROZEN"
    assert frozen["tag"] == "forest"

    listed = client.get(f"/forest/projects/{project}/ideas")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(row["idea_id"] == frozen["idea_id"] for row in items)

    promote_res = client.post(
        f"/forest/projects/{project}/ideas/{frozen['idea_id']}/promote",
        json={"north_star_link": "focus cockpit", "proof_48h": "focus view api+ui 검증"},
    )
    assert promote_res.status_code == 200
    body = promote_res.json()
    promoted = body["idea"]
    assert promoted["status"] == "PROMOTED"
    assert promoted["promote_requirements"]["north_star_link"] == "focus cockpit"
    assert promoted["promote_requirements"]["proof_48h"] == "focus view api+ui 검증"
    assert body["work"] is not None
    assert body["work"]["work_package_id"]
    listed_work = client.get("/work/packages", params={"status": "READY"}).json()["items"]
    assert any(row["id"] == body["work"]["work_package_id"] for row in listed_work)


def test_idea_promote_blocked_by_hard_focus_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(forest_router.settings, "forest_focus_mode", True, raising=False)
    monkeypatch.setattr(forest_router.settings, "forest_focus_lock_level", "hard", raising=False)
    monkeypatch.setattr(forest_router.settings, "forest_wip_limit", 3, raising=False)
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    # Create one active mission to activate hard lock.
    create_res = client.post(
        "/work/packages",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "forest:phase3",
            "title": "active mission",
            "description": "keep in progress",
        },
    )
    assert create_res.status_code == 200
    package_id = create_res.json()["package"]["id"]
    ack_res = client.post(f"/work/packages/{package_id}/ack")
    assert ack_res.status_code == 200

    freeze_res = client.post(
        f"/forest/projects/{project}/ideas/freeze",
        json={"title": "승격 대기 아이디어", "tag": "forest"},
    )
    assert freeze_res.status_code == 200
    idea_id = freeze_res.json()["idea"]["idea_id"]

    promote_res = client.post(
        f"/forest/projects/{project}/ideas/{idea_id}/promote",
        json={"north_star_link": "focus cockpit", "proof_48h": "contract check"},
    )
    assert promote_res.status_code == 409
    detail = promote_res.json().get("detail", {})
    assert detail.get("code") == "FOCUS_LOCKED"
    assert detail.get("reason", "").startswith("HARD_LOCK_ACTIVE")


def test_grove_analyze_path_accepts_workspace_md(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    client.post("/forest/projects/init", json={"project_name": project})

    workspace_dir = tmp_path / "workspace" / "notes"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    source = workspace_dir / "spec.md"
    source.write_text("# 로그인 설계\n성공 조건 없음\nsession-manager 영향", encoding="utf-8")

    response = client.post(
        f"/forest/projects/{project}/grove/analyze/path",
        json={
            "path": str(source),
            "target": "auth-module",
            "change": "로그인 구조 검토",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["source_path"] == str(source)


def test_forest_live_roadmap_record_from_generate_and_status_sync(tmp_path, monkeypatch):
    client, forest_root = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    create_res = client.post(
        f"/forest/projects/{project}/work/generate",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "forest:canopy",
            "issue": "live roadmap record test",
            "required": ["acceptance 정의"],
        },
    )
    assert create_res.status_code == 200
    create_body = create_res.json()
    assert "roadmap_live_record" in create_body

    sync_res = client.post(f"/forest/projects/{project}/status/sync?view=focus&export_canopy=false")
    assert sync_res.status_code == 200
    sync_body = sync_res.json()
    assert "roadmap_live_record" in sync_body

    journal_path = forest_root / project / "status" / "roadmap_journal.jsonl"
    assert journal_path.exists()
    lines = [line for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    assert any('"type": "LIVE_EVENT"' in line for line in lines)
    assert any('"title": "[forest]' in line for line in lines)


def test_apple_status_plan_and_sync_updates_todo(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    status_res = client.get(f"/forest/projects/{project}/apple/status-plan")
    assert status_res.status_code == 200
    status_body = status_res.json()
    assert status_body["status"] == "ok"
    assert status_body["project"] == project
    assert isinstance(status_body.get("checks"), list)
    assert isinstance(status_body.get("plan"), list)
    assert "runtime" in status_body

    sync_res = client.post(
        f"/forest/projects/{project}/apple/plan/sync",
        json={"owner": "codex", "lane": "codex", "force": False},
    )
    assert sync_res.status_code == 200
    sync_body = sync_res.json()
    assert sync_body["status"] == "ok"
    assert int(sync_body.get("created", 0) or 0) >= 1
    assert "apple" in sync_body
    assert isinstance(sync_body.get("touched_ids"), list)

    todo_res = client.get(f"/forest/projects/{project}/todo")
    assert todo_res.status_code == 200
    todo_items = todo_res.json().get("items", [])
    apple_rows = [row for row in todo_items if str(row.get("category", "")).strip().lower() == "apple"]
    assert apple_rows
    assert any("[apple_plan_id:" in str(row.get("detail", "")) for row in apple_rows)


def test_apple_plan_sync_deduplicates_existing_items(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    first = client.post(
        f"/forest/projects/{project}/apple/plan/sync",
        json={"owner": "codex", "lane": "codex", "force": False},
    )
    assert first.status_code == 200
    assert int(first.json().get("created", 0) or 0) >= 1

    second = client.post(
        f"/forest/projects/{project}/apple/plan/sync",
        json={"owner": "codex", "lane": "codex", "force": False},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert int(second_body.get("created", 0) or 0) == 0
    assert int(second_body.get("updated", 0) or 0) == 0
