import json
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from sophia_kernel.registry import registry


@pytest.fixture
def isolated_registry(monkeypatch, tmp_path) -> Path:
    root = tmp_path / "skills"
    monkeypatch.setattr(registry, "REGISTRY_ROOT", str(root))
    return root


def _manifest(skill_id: str = "workspace.read_only_check", scope: str = "workspace") -> dict:
    return {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": skill_id,
        "scope": scope,
        "entrypoint": "skills.workspace.read_only_check:run",
        "capabilities": ["fs.read", "audit.append"],
        "verification": {"mode": "advisory", "hook": "verify.default"},
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 1},
    }


def test_register_valid_manifest_writes_file(isolated_registry):
    manifest = _manifest()

    path = registry.register_skill(manifest)

    assert path.exists()
    assert path.parent == isolated_registry
    assert json.loads(path.read_text(encoding="utf-8")) == manifest


def test_register_duplicate_raises(isolated_registry):
    manifest = _manifest()
    registry.register_skill(manifest)

    with pytest.raises(FileExistsError):
        registry.register_skill(manifest)


def test_get_returns_manifest(isolated_registry):
    manifest = _manifest()
    registry.register_skill(manifest)

    got = registry.get_skill(skill_id=manifest["skill_id"], version="0.1.0")

    assert got == manifest


def test_list_skills_returns_metadata(isolated_registry):
    first = _manifest(skill_id="workspace.read_only_check")
    second = _manifest(skill_id="engine.core_check", scope="engine")
    registry.register_skill(first)
    registry.register_skill(second)

    got = registry.list_skills()

    assert {
        "id": "workspace.read_only_check",
        "version": "0.1.0",
        "scope": "workspace",
        "capabilities": ["fs.read", "audit.append"],
    } in got
    assert {
        "id": "engine.core_check",
        "version": "0.1.0",
        "scope": "engine",
        "capabilities": ["fs.read", "audit.append"],
    } in got


def test_register_invalid_manifest_raises(isolated_registry):
    manifest = _manifest()
    manifest.pop("entrypoint")

    with pytest.raises(ValidationError):
        registry.register_skill(manifest)

    assert list(isolated_registry.glob("*.json")) == []
