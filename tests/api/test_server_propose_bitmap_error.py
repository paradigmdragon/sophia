from fastapi.testclient import TestClient

from api import server as server_module


def test_propose_returns_standard_bitmap_error(monkeypatch):
    client = TestClient(server_module.app)

    def _raise_invalid(_episode_id: str, _text: str):
        raise ValueError("invalid backbone_bits for candidate: 61440 [reason=INVALID_CHUNK_A] (invalid chunk A)")

    monkeypatch.setattr(server_module.system, "propose", _raise_invalid)

    response = client.post("/propose", json={"episode_id": "ep_test", "text": "plan"})
    assert response.status_code == 400
    body = response.json()
    detail = body.get("detail", {})
    assert detail.get("code") == "BITMAP_INVALID"
    assert detail.get("reason") == "INVALID_CHUNK_A"
    assert "invalid backbone_bits" in str(detail.get("message", ""))

