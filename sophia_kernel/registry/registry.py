from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator


SKILL_SCHEMA_PATH = "/Users/dragonpd/Sophia/sophia_kernel/schema/skill_manifest_schema_v0_1.json"
REGISTRY_ROOT = "/Users/dragonpd/Sophia/.sophia/registry/skills"


def load_skill_schema() -> dict:
    return json.loads(Path(SKILL_SCHEMA_PATH).read_text(encoding="utf-8"))


def validate_skill_manifest(manifest: dict) -> None:
    schema = load_skill_schema()
    Draft202012Validator(schema).validate(manifest)


def make_skill_key(id: str, version: str) -> str:
    return f"{id}__{version}".replace("/", "_").replace(":", "_")


def _manifest_version(manifest: dict) -> str:
    version = manifest.get("version", manifest.get("schema_version"))
    if version is None:
        raise KeyError("manifest version is required")
    return str(version)


def register_skill(manifest: dict) -> Path:
    validate_skill_manifest(manifest)

    skill_id = manifest["skill_id"]
    version = _manifest_version(manifest)
    key = make_skill_key(skill_id, version)

    root = Path(REGISTRY_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{key}.json"

    if target.exists():
        raise FileExistsError(str(target))

    with target.open("x", encoding="utf-8") as f:
        f.write(json.dumps(manifest, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

    return target


def get_skill(skill_id: str, version: str) -> dict:
    target = Path(REGISTRY_ROOT) / f"{make_skill_key(skill_id, version)}.json"
    if not target.exists():
        raise FileNotFoundError(str(target))
    return json.loads(target.read_text(encoding="utf-8"))


def list_skills() -> list[dict]:
    root = Path(REGISTRY_ROOT)
    if not root.exists():
        return []

    items: list[dict] = []
    for file_path in sorted(root.glob("*.json")):
        manifest = json.loads(file_path.read_text(encoding="utf-8"))
        items.append(
            {
                "id": manifest.get("skill_id"),
                "version": str(manifest.get("version", manifest.get("schema_version"))),
                "scope": manifest.get("scope"),
                "capabilities": manifest.get("capabilities", []),
            }
        )
    return items
