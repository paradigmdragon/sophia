from __future__ import annotations

from scripts.check_server_contract import evaluate_contract


def test_evaluate_contract_accepts_sync_prefix():
    paths = {
        "/health",
        "/chat/messages",
        "/forest/projects/{project_name}/canopy/data",
        "/sync/handshake/init",
        "/sync/progress",
        "/sync/commit",
        "/sync/reconcile",
    }
    result = evaluate_contract(paths)
    assert result["ok"] is True
    assert result["sync_prefix"] == "/sync"
    assert result["missing_core"] == []
    assert result["missing_sync"] == []


def test_evaluate_contract_accepts_api_sync_prefix():
    paths = {
        "/health",
        "/chat/messages",
        "/forest/projects/{project_name}/canopy/data",
        "/api/sync/handshake/init",
        "/api/sync/progress",
        "/api/sync/commit",
        "/api/sync/reconcile",
    }
    result = evaluate_contract(paths)
    assert result["ok"] is True
    assert result["sync_prefix"] == "/api/sync"


def test_evaluate_contract_accepts_forest_status_sync():
    paths = {
        "/health",
        "/chat/messages",
        "/forest/projects/{project_name}/canopy/data",
        "/forest/projects/{project_name}/status/sync",
    }
    result = evaluate_contract(paths)
    assert result["ok"] is True
    assert result["sync_prefix"] == "forest/status-sync"


def test_evaluate_contract_reports_missing_sync():
    paths = {
        "/health",
        "/chat/messages",
        "/forest/projects/{project_name}/canopy/data",
    }
    result = evaluate_contract(paths)
    assert result["ok"] is False
    assert result["sync_prefix"] == "unknown"
    assert result["missing_sync"]
