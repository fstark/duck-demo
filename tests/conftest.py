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


# ---------------------------------------------------------------------------
# Per-function-scoped QC DB fixture (for mutation tests that write QC state)
# ---------------------------------------------------------------------------

@pytest.fixture()
def qc_db(tmp_path, monkeypatch):
    """Create a fresh temporary DB with schema + minimal QC seed data per test.

    Uses function scope so QC mutation tests are fully isolated from each other
    and from the session-scoped shared DB.
    """
    from tests.seed_test_data import (
        CUSTOMERS, SUPPLIERS, ITEMS, STOCK, STOCK_MOVEMENTS,
        RECIPES, RECIPE_INGREDIENTS, RECIPE_OPERATIONS, WORK_CENTERS,
        QUOTES, QUOTE_LINES, SALES_ORDERS, SALES_ORDER_LINES,
        PRODUCTION_ORDERS,
        QC_RECIPES, QC_RECIPE_INGREDIENTS,
        QC_SALES_ORDERS, QC_SALES_ORDER_LINES,
        QC_PRODUCTION_ORDERS, QC_HOLD_BATCHES,
        SIM_TIME,
    )

    db_file = tmp_path / "qc_test.db"
    monkeypatch.setattr(db, "DB_PATH", db_file)

    db.init_db()

    conn = db.get_connection()
    ordered_data = [
        ("simulation_state", [{"id": 1, "sim_time": SIM_TIME}]),
        ("suppliers", SUPPLIERS),
        ("customers", CUSTOMERS),
        ("items", ITEMS),
        ("stock", STOCK),
        ("stock_movements", STOCK_MOVEMENTS),
        ("recipes", RECIPES),
        ("recipe_ingredients", RECIPE_INGREDIENTS),
        ("recipe_operations", RECIPE_OPERATIONS),
        ("work_centers", WORK_CENTERS),
        ("quotes", QUOTES),
        ("quote_lines", QUOTE_LINES),
        ("sales_orders", SALES_ORDERS),
        ("sales_order_lines", SALES_ORDER_LINES),
        ("production_orders", PRODUCTION_ORDERS),
        ("recipes", QC_RECIPES),
        ("recipe_ingredients", QC_RECIPE_INGREDIENTS),
        ("sales_orders", QC_SALES_ORDERS),
        ("sales_order_lines", QC_SALES_ORDER_LINES),
        ("production_orders", QC_PRODUCTION_ORDERS),
        ("qc_hold_batches", QC_HOLD_BATCHES),
    ]
    for table_name, rows in ordered_data:
        if not rows:
            continue
        cols = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        col_names = ", ".join(cols)
        for row in rows:
            values = [row[c] for c in cols]
            conn.execute(
                f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
                values,
            )
    conn.commit()
    conn.close()

    yield db_file
