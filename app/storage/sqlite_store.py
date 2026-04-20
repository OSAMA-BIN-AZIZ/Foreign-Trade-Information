import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class SQLiteStateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._conn() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS publish_state (
                    digest_date TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    draft_media_id TEXT,
                    publish_id TEXT,
                    publish_status TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(digest_date, content_hash),
                    UNIQUE(draft_media_id)
                )
                """
            )

    def is_duplicate(self, digest_date: str, content_hash: str) -> bool:
        with self._conn() as con:
            row = con.execute(
                "SELECT 1 FROM publish_state WHERE digest_date=? AND content_hash=?",
                (digest_date, content_hash),
            ).fetchone()
            return row is not None

    def save_draft(self, digest_date: str, content_hash: str, draft_media_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO publish_state
                (digest_date, content_hash, draft_media_id, publish_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (digest_date, content_hash, draft_media_id, "draft_created", now, now),
            )

    def mark_published(self, draft_media_id: str, publish_id: str, publish_status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as con:
            con.execute(
                """
                UPDATE publish_state
                SET publish_id=?, publish_status=?, updated_at=?
                WHERE draft_media_id=?
                """,
                (publish_id, publish_status, now, draft_media_id),
            )

    def has_submitted(self, draft_media_id: str) -> bool:
        with self._conn() as con:
            row = con.execute(
                "SELECT publish_id FROM publish_state WHERE draft_media_id=? AND publish_id IS NOT NULL",
                (draft_media_id,),
            ).fetchone()
            return row is not None
