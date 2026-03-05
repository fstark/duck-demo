"""MCP tool contract tests — shared tools (user, simulation, stats, catalog, inventory, activity, charts)."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ListOf, ANY

pytestmark = pytest.mark.mcp


def _call(mcp_app, tool_name, **kwargs):
    """Call an MCP tool function directly by name and return the result."""
    tool = mcp_app._tool_manager._tools[tool_name]
    return tool.fn(**kwargs)


# ── User ───────────────────────────────────────────────────────────────────

def test_user_get_current(mcp_app):
    result = _call(mcp_app, "user_get_current")
    assert isinstance(result, dict)
    assert "first_name" in result
    assert "role" in result


# ── Simulation ─────────────────────────────────────────────────────────────

def test_simulation_get_time(mcp_app):
    result = _call(mcp_app, "simulation_get_time")
    assert isinstance(result, dict)
    assert "current_time" in result


# ── Stats ──────────────────────────────────────────────────────────────────

def test_stats_get_summary_count(mcp_app):
    result = _call(mcp_app, "stats_get_summary", entity="customers", metric="count")
    assert isinstance(result, dict)


def test_stats_get_summary_group(mcp_app):
    result = _call(mcp_app, "stats_get_summary", entity="sales_orders", metric="count", group_by="status")
    assert isinstance(result, dict)


# ── Catalog ────────────────────────────────────────────────────────────────

def test_catalog_get_item(mcp_app):
    result = _call(mcp_app, "catalog_get_item", sku="CLASSIC-DUCK-10CM")
    assert isinstance(result, dict)
    assert_shape(result, {"sku": str, "name": str, "type": str})


def test_catalog_get_item_not_found(mcp_app):
    with pytest.raises(Exception):
        _call(mcp_app, "catalog_get_item", sku="NOPE-SKU")


def test_catalog_search_items(mcp_app):
    result = _call(mcp_app, "catalog_search_items", words=["classic", "duck"])
    assert isinstance(result, dict)
    assert "items" in result


def test_catalog_list_recipes(mcp_app):
    result = _call(mcp_app, "catalog_list_recipes")
    assert isinstance(result, dict)
    recipes = result["recipes"]
    assert isinstance(recipes, list)
    assert len(recipes) >= 1


def test_catalog_get_recipe(mcp_app):
    result = _call(mcp_app, "catalog_get_recipe", recipe_id="RCP-CLASSIC-10")
    assert isinstance(result, dict)
    assert_shape(result, {"id": str, "output_item_id": str})


# ── Inventory ──────────────────────────────────────────────────────────────

def test_inventory_list_items(mcp_app):
    result = _call(mcp_app, "inventory_list_items", in_stock_only=False, limit=50)
    assert isinstance(result, dict)


def test_inventory_list_items_in_stock(mcp_app):
    result = _call(mcp_app, "inventory_list_items", in_stock_only=True, limit=50)
    assert isinstance(result, dict)


def test_inventory_get_stock_by_sku(mcp_app):
    result = _call(mcp_app, "inventory_get_stock", sku="CLASSIC-DUCK-10CM")
    assert isinstance(result, dict)


def test_inventory_check_availability(mcp_app):
    result = _call(mcp_app, "inventory_check_availability", item_sku="CLASSIC-DUCK-10CM", quantity=6)
    assert isinstance(result, dict)


# ── Activity ───────────────────────────────────────────────────────────────

def test_activity_get_log(mcp_app):
    result = _call(mcp_app, "activity_get_log", limit=10)
    assert isinstance(result, dict)
    entries = result["entries"]
    assert isinstance(entries, list)
    assert len(entries) >= 1
