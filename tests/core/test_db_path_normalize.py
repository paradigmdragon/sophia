from core.memory.schema import _normalize_db_path


def test_normalize_db_path_keeps_valid_sqlite_uri() -> None:
    value = "sqlite:///sophia.db"
    assert _normalize_db_path(value) == value


def test_normalize_db_path_supports_absolute_path() -> None:
    value = "/tmp/sophia.db"
    assert _normalize_db_path(value) == "sqlite:////tmp/sophia.db"


def test_normalize_db_path_fixes_malformed_sqlite_prefix() -> None:
    normalized = _normalize_db_path("sqlite:/sophia.db")
    assert normalized.startswith("sqlite:///")
    assert normalized.endswith("/sophia.db")
