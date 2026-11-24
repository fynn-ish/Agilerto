"""SQLite connection helpers."""
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DISASTER_DB", BASE_DIR / "data" / "disaster.db"))
SCHEMA_PATH = BASE_DIR / "schema.sql"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI runs sync endpoints in a thread pool.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # readers don't block the ingestion writer
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# Columns added after the first release. CREATE TABLE IF NOT EXISTS does not change an existing table,
# so databases made by an earlier step get them here, without losing any data.
MIGRATIONS = {
    "advisories": [("lat", "REAL"), ("lng", "REAL"), ("category", "TEXT")],
    "news": [("tags", "TEXT")],
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in MIGRATIONS.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, col_type in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")


def init_db() -> None:
    """Create all tables if they don't exist yet and upgrade older ones (safe to run repeatedly)."""
    conn = connect()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def get_db():
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
