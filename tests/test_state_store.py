from app.storage.sqlite_store import SQLiteStateStore


def test_state_store_idempotency(tmp_path) -> None:
    db = tmp_path / "s.sqlite3"
    s = SQLiteStateStore(db)
    s.save_draft("2026-04-20", "h1", "m1")
    s.save_draft("2026-04-20", "h1", "m1")
    assert s.is_duplicate("2026-04-20", "h1") is True
    assert s.has_submitted("m1") is False
    s.mark_published("m1", "p1", "0")
    assert s.has_submitted("m1") is True
