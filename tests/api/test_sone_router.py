from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import sone_router
from core.engine.scheduler import SoneScheduler


def test_sone_router_register_and_list(tmp_path):
    db_path = tmp_path / "sone_api.db"
    db_url = f"sqlite:///{db_path}"

    sone_router._scheduler = SoneScheduler(db_path=db_url, poll_interval_seconds=1)
    app = FastAPI()
    app.include_router(sone_router.router)
    client = TestClient(app)

    res = client.post(
        "/sone/commands",
        json={
            "name": "sqrt-now",
            "type": "python",
            "priority": "P3",
            "payload": {
                "module": "math",
                "function": "sqrt",
                "args": [9],
                "kwargs": {},
            },
            "schedule": {"type": "immediate", "value": ""},
            "dependencies": [],
            "timeout": 30,
            "retry": {"count": 0, "delay": 0},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "sqrt-now"
    assert body["type"] == "python"
    assert body["active"] is True

    listed = client.get("/sone/commands")
    assert listed.status_code == 200
    commands = listed.json()
    assert len(commands) == 1
    assert commands[0]["name"] == "sqrt-now"

