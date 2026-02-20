from fastapi.testclient import TestClient

from api import server as server_module


def test_reject_returns_404_when_candidate_missing(monkeypatch):
    client = TestClient(server_module.app)

    monkeypatch.setattr(server_module.system, "get_candidate", lambda _candidate_id: None)

    response = client.post("/reject", json={"episode_id": "ep_missing", "candidate_id": "cand_missing"})
    assert response.status_code == 404
    assert "Candidate not found" in str(response.json().get("detail", ""))


def test_reject_returns_success(monkeypatch):
    client = TestClient(server_module.app)
    called: dict[str, str | None] = {}

    monkeypatch.setattr(
        server_module.system,
        "get_candidate",
        lambda candidate_id: {"candidate_id": candidate_id, "status": "PENDING"},
    )

    def _reject(episode_id: str, candidate_id: str, reason: str | None = None):
        called["episode_id"] = episode_id
        called["candidate_id"] = candidate_id
        called["reason"] = reason
        return True

    monkeypatch.setattr(server_module.system, "reject", _reject)

    response = client.post(
        "/reject",
        json={"episode_id": "ep_1", "candidate_id": "cand_1", "reason": "manual_reject_ui"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "rejected"
    assert body.get("candidate_id") == "cand_1"
    assert body.get("reason") == "manual_reject_ui"
    assert body.get("idempotent") is False
    assert called == {"episode_id": "ep_1", "candidate_id": "cand_1", "reason": "manual_reject_ui"}


def test_reject_already_rejected_returns_idempotent(monkeypatch):
    client = TestClient(server_module.app)

    monkeypatch.setattr(
        server_module.system,
        "get_candidate",
        lambda candidate_id: {"candidate_id": candidate_id, "status": "REJECTED"},
    )
    monkeypatch.setattr(server_module.system, "reject", lambda episode_id, candidate_id, reason=None: False)

    response = client.post("/reject", json={"episode_id": "ep_1", "candidate_id": "cand_1"})
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "already_rejected"
    assert body.get("idempotent") is True


def test_adopt_already_adopted_returns_idempotent(monkeypatch):
    client = TestClient(server_module.app)

    monkeypatch.setattr(
        server_module.system,
        "get_candidate",
        lambda candidate_id: {"candidate_id": candidate_id, "status": "ADOPTED"},
    )
    monkeypatch.setattr(server_module.system, "adopt", lambda episode_id, candidate_id: "bb_existing")

    response = client.post("/adopt", json={"episode_id": "ep_1", "candidate_id": "cand_1"})
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "already_adopted"
    assert body.get("idempotent") is True
    assert body.get("backbone_id") == "bb_existing"


def test_adopt_episode_mismatch_returns_409(monkeypatch):
    client = TestClient(server_module.app)

    monkeypatch.setattr(
        server_module.system,
        "get_candidate",
        lambda candidate_id: {"candidate_id": candidate_id, "status": "PENDING"},
    )
    monkeypatch.setattr(
        server_module.system,
        "adopt",
        lambda episode_id, candidate_id: (_ for _ in ()).throw(
            ValueError("Candidate episode mismatch: candidate=ep_a requested=ep_b")
        ),
    )

    response = client.post("/adopt", json={"episode_id": "ep_b", "candidate_id": "cand_1"})
    assert response.status_code == 409
    detail = response.json().get("detail", {})
    assert detail.get("code") == "CANDIDATE_EPISODE_MISMATCH"


def test_reject_episode_mismatch_returns_409(monkeypatch):
    client = TestClient(server_module.app)

    monkeypatch.setattr(
        server_module.system,
        "get_candidate",
        lambda candidate_id: {"candidate_id": candidate_id, "status": "PENDING"},
    )
    monkeypatch.setattr(
        server_module.system,
        "reject",
        lambda episode_id, candidate_id, reason=None: (_ for _ in ()).throw(
            ValueError("Candidate episode mismatch: candidate=ep_a requested=ep_b")
        ),
    )

    response = client.post("/reject", json={"episode_id": "ep_b", "candidate_id": "cand_1"})
    assert response.status_code == 409
    detail = response.json().get("detail", {})
    assert detail.get("code") == "CANDIDATE_EPISODE_MISMATCH"
