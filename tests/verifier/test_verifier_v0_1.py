from sophia_kernel.verifier.verifier import verify


def _manifest(mode: str) -> dict:
    return {
        "verification": {"mode": mode, "hook": "verify.default"},
        "outputs_schema": {
            "type": "object",
            "required": ["must_exist"],
            "properties": {"must_exist": {"type": "string"}},
            "additionalProperties": True,
        },
    }


def test_verify_advisory_allows_commit_even_if_output_invalid():
    report = verify(
        manifest=_manifest("advisory"),
        inputs={},
        outputs={"ok": True},
        observed_effects=None,
    )

    assert report["mode"] == "advisory"
    assert report["pass"] is True
    assert any(v["code"] == "V_OUT_SCHEMA" for v in report["violations"])


def test_verify_strict_blocks_on_output_schema_violation():
    report = verify(
        manifest=_manifest("strict"),
        inputs={},
        outputs={"ok": True},
        observed_effects=None,
    )

    assert report["mode"] == "strict"
    assert report["pass"] is False
    assert any(v["code"] == "V_OUT_SCHEMA" for v in report["violations"])
