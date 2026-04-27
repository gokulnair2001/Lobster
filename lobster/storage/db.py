import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "lobster.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_responses (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                source    TEXT NOT NULL,
                query     TEXT NOT NULL,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
                payload   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS nodes (
                id        TEXT PRIMARY KEY,
                type      TEXT NOT NULL,
                data      TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS edges (
                source_id  TEXT NOT NULL,
                target_id  TEXT NOT NULL,
                edge_type  TEXT NOT NULL,
                weight     REAL DEFAULT 1.0,
                metadata   TEXT DEFAULT '{}',
                PRIMARY KEY (source_id, target_id, edge_type)
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                library     TEXT NOT NULL,
                captured_at TEXT NOT NULL DEFAULT (datetime('now')),
                report      TEXT NOT NULL
            );
        """)


def save_raw(source: str, query: str, payload: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO raw_responses (source, query, payload) VALUES (?, ?, ?)",
            (source, query, json.dumps(payload)),
        )


def upsert_node(node_id: str, node_type: str, data: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO nodes (id, type, data) VALUES (?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=datetime('now')""",
            (node_id, node_type, json.dumps(data)),
        )


def save_snapshot(library: str, report: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO snapshots (library, report) VALUES (?, ?)",
            (library, json.dumps(report)),
        )


def get_last_snapshot(library: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT report, captured_at FROM snapshots WHERE library = ? ORDER BY captured_at DESC LIMIT 1 OFFSET 1",
            (library,),
        ).fetchone()
    if row is None:
        return None
    return {"report": json.loads(row["report"]), "captured_at": row["captured_at"]}


def upsert_edge(source_id: str, target_id: str, edge_type: str, weight: float = 1.0, metadata: dict = {}):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO edges (source_id, target_id, edge_type, weight, metadata) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(source_id, target_id, edge_type) DO UPDATE SET weight=excluded.weight, metadata=excluded.metadata""",
            (source_id, target_id, edge_type, weight, json.dumps(metadata)),
        )
