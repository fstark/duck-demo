import sqlite3
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).parent
DB_PATH = ROOT / "demo.db"
SCHEMA_PATH = ROOT / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    owns_conn = False
    if conn is None:
        conn = get_connection()
        owns_conn = True
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()
    if owns_conn:
        conn.close()


def dict_rows(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


def generate_id(conn: sqlite3.Connection, prefix: str, table: str, column: str = "id") -> str:
    seed_defaults = {"CUST": 101, "SO": 1041, "SHIP": 899, "INV": 2000, "PAY": 3000}
    pattern = f"{prefix}-%"
    prefix_len = len(prefix) + 2  # skip "PREFIX-"
    row = conn.execute(
        f"SELECT MAX(CAST(SUBSTR({column}, ?) AS INTEGER)) FROM {table} WHERE {column} LIKE ?",
        (prefix_len, pattern),
    ).fetchone()
    max_num = row[0] if row[0] is not None else seed_defaults.get(prefix, 0)
    return f"{prefix}-{max_num + 1:04d}"
