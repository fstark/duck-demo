"""Shared pytest fixtures for duck-demo contract tests.

Key fixtures:
- ``test_db``   – creates a fresh temporary SQLite DB with schema + seed data;
                  monkeypatches ``db.DB_PATH`` so all services use it.
- ``rest_client`` – Starlette ``TestClient`` wired to the FastMCP app with REST routes.
- ``mcp_app``   – the FastMCP instance with all tools registered (for direct calls).
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import db
from tests.seed_test_data import TABLE_DATA


# ---------------------------------------------------------------------------
# Database fixture — fresh for each test *session* (fast, deterministic)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _db_path(tmp_path_factory):
    """Create a temporary DB file, apply schema + seed data once per session."""
    tmp = tmp_path_factory.mktemp("duck_test")
    db_file = tmp / "test.db"

    # Point the app's DB module at the temp file
    original = db.DB_PATH
    db.DB_PATH = db_file

    # Create schema
    db.init_db()

    # Seed test data
    conn = db.get_connection()
    for table_name, rows in TABLE_DATA:
        if not rows:
            continue
        cols = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        col_names = ", ".join(cols)
        for row in rows:
            values = [row[c] for c in cols]
            conn.execute(f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()

    yield db_file

    db.DB_PATH = original


@pytest.fixture(autouse=True)
def test_db(_db_path):
    """Ensure every test uses the test DB (auto-applied)."""
    db.DB_PATH = _db_path


# ---------------------------------------------------------------------------
# REST client fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _mcp_instance(_db_path):
    """Build a single FastMCP app for the whole test session."""
    db.DB_PATH = _db_path

    mcp = FastMCP(
        "duck-demo-test",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
            allowed_hosts=["*"],
            allowed_origins=["*"],
        ),
    )

    from mcp_tools import register_all_tools
    from api_routes import register_all_routes

    register_all_tools(mcp)
    register_all_routes(mcp)
    return mcp


@pytest.fixture(scope="session")
def rest_client(_mcp_instance):
    """Starlette TestClient for REST API routes."""
    app = _mcp_instance.streamable_http_app()
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="session")
def mcp_app(_mcp_instance):
    """The FastMCP instance — use to look up and call tool functions directly."""
    return _mcp_instance
