"""MCP tool contract tests — production tools (orders, work centers, purchases)."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ListOf, ANY

pytestmark = pytest.mark.mcp


def _call(mcp_app, tool_name, **kwargs):
    """Call an MCP tool function directly by name and return the result."""
    tool = mcp_app._tool_manager._tools[tool_name]
    return tool.fn(**kwargs)


# ── Production dashboard ───────────────────────────────────────────────────

def test_production_get_dashboard(mcp_app):
    result = _call(mcp_app, "production_get_dashboard")
    assert isinstance(result, dict)


# ── Production orders ──────────────────────────────────────────────────────

def test_production_get_order(mcp_app):
    result = _call(mcp_app, "production_get_order", production_order_id="MO-T001")
    assert isinstance(result, dict)
    assert_shape(result, {"id": str, "status": str})


def test_production_search_orders(mcp_app):
    result = _call(mcp_app, "production_search_orders",
                   start_date="2025-07-01", end_date="2025-09-01")
    assert isinstance(result, list)


# ── Work centers ───────────────────────────────────────────────────────────

def test_work_center_list(mcp_app):
    result = _call(mcp_app, "work_center_list")
    assert isinstance(result, dict)
    assert "work_centers" in result
    assert len(result["work_centers"]) >= 1


def test_work_center_get_status(mcp_app):
    result = _call(mcp_app, "work_center_get_status", work_center_name="MOLDING")
    assert isinstance(result, dict)


def test_work_center_get_bottlenecks(mcp_app):
    result = _call(mcp_app, "work_center_get_bottlenecks")
    assert isinstance(result, dict)
