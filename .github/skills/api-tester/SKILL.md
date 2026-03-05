---
name: api-tester
description: Run, maintain, and extend the duck-demo API contract test suite (REST + MCP tools).
---

## Purpose

Manage the pytest-based contract test suite that validates all REST API endpoints and MCP tool interfaces against a minimal seed database.

## When to use

- **Run tests** after any code change to services, API routes, or MCP tools.
- **Add tests** when a new endpoint or MCP tool is created.
- **Update tests** when an endpoint's contract changes (new keys, renamed fields, changed types).
- **Debug failures** to determine if the issue is in the test expectation or the application code.

## Architecture overview

```
tests/
  conftest.py              # Fixtures: temp DB, seed data, Starlette TestClient, FastMCP instance
  seed_test_data.py        # Minimal deterministic dataset (~25 rows across all tables)
  contract_helpers.py      # Shape-checking utilities (assert_shape, ANY, AnyOf, ListOf, Optional)
  test_rest_system.py      # REST: /api/health, simulation, spotlight
  test_rest_customers.py   # REST: /api/customers
  test_rest_catalog.py     # REST: /api/items
  test_rest_stock.py       # REST: /api/stock
  test_rest_sales.py       # REST: /api/sales-orders, quote-options
  test_rest_shipments.py   # REST: /api/shipments
  test_rest_production.py  # REST: /api/production-orders, work-centers
  test_rest_reference.py   # REST: /api/recipes, suppliers, purchase-orders
  test_rest_documents.py   # REST: /api/emails, quotes, invoices
  test_rest_activity.py    # REST: /api/activity-log, dashboard
  test_mcp_shared.py       # MCP: shared tools (user, simulation, stats, catalog, inventory, activity)
  test_mcp_sales.py        # MCP: sales tools (CRM, orders, quotes, invoices, messaging, logistics)
  test_mcp_production.py   # MCP: production tools (orders, work centers)
```

## How to run tests

```bash
source venv/bin/activate

# Run all tests
pytest

# Run only REST tests
pytest -m rest

# Run only MCP tests
pytest -m mcp

# Run a specific test file
pytest tests/test_rest_sales.py

# Run with verbose output
pytest -v

# Run a single test
pytest tests/test_rest_sales.py::test_get_sales_order_detail -v
```

## Key design decisions

### Contract tests, not value tests

Tests check **response shape** (required keys, value types, list non-emptiness), not exact values. This means:
- Changing an item price won't break tests.
- Renaming a response key **will** break tests — which is exactly what you want.
- Adding a new key to a response is non-breaking (tests only check listed keys).

### `assert_shape` helper

```python
from tests.contract_helpers import assert_shape, AnyOf, ListOf, Optional, ANY

# Check that data has the right structure
assert_shape(data, {
    "id": str,                           # must be a string
    "total": AnyOf(int, float),          # int or float
    "lines": ListOf({"sku": str}),       # list of dicts each with "sku" key
    "notes": Optional(str),              # may be missing
    "metadata": ANY,                     # any value, just must exist
})
```

### Two test layers

| Layer | How it works | What it tests |
|-------|-------------|---------------|
| **REST** | `rest_client.get("/api/...")` via Starlette TestClient | HTTP status, JSON shape, query param parsing |
| **MCP** | `tool.fn(...)` direct Python call | Tool params, service integration, return shape |

REST tests go through the full HTTP stack (Starlette routing, CORS, serialization).
MCP tests skip JSON-RPC transport but exercise the complete tool → service → DB path.

### Session-scoped fixtures

The DB and test client are created **once per session** (not per test), making the suite fast. Tests are read-only against seed data — no test modifies the database.

### Seed data

`tests/seed_test_data.py` contains a small, static dataset with known IDs:
- 2 customers: `CUST-0101`, `CUST-0102`
- 4 items: `ITEM-PVC`, `ITEM-YELLOW-DYE`, `ITEM-BOX-SMALL`, `ITEM-CLASSIC-10`
- 1 recipe: `RCP-CLASSIC-10`
- 1 sales order: `SO-T001` (confirmed, for CUST-0101)
- 1 quote: `QUO-T001` (accepted)
- 1 shipment: `SHIP-T001`
- 1 production order: `MO-T001`
- 1 purchase order: `PO-T001`
- 1 invoice: `INV-T001` (issued)
- 1 email: `EMAIL-T001`
- 4 stock records with movements

## How to add a test for a new endpoint

### New REST endpoint

1. Identify the correct test file (by domain) or create a new `test_rest_{domain}.py`.
2. Add a test function:
   ```python
   def test_my_new_endpoint(rest_client):
       resp = rest_client.get("/api/my-endpoint", params={"key": "value"})
       assert resp.status_code == 200
       data = resp.json()
       assert_shape(data, {"expected_key": str})
   ```
3. If the endpoint needs additional seed data, add rows to `seed_test_data.py`.

### New MCP tool

1. Identify the correct test file or create a new `test_mcp_{domain}.py`.
2. Add a test function:
   ```python
   def _call(mcp_app, tool_name, **kwargs):
       tool = mcp_app._tool_manager._tools[tool_name]
       return tool.fn(**kwargs)

   def test_my_new_tool(mcp_app):
       result = _call(mcp_app, "my_tool_name", param1="value")
       assert isinstance(result, dict)
       assert_shape(result, {"expected_key": str})
   ```

### Mutating tools

Mutating MCP tools return a `CallToolResult` (confirmation response), not a dict. Test the shape of the confirmation metadata:
```python
def test_my_mutating_tool(mcp_app):
    result = _call(mcp_app, "my_mutating_tool", param="value")
    # Mutating tools return CallToolResult with structuredContent
    assert hasattr(result, 'structuredContent')
    metadata = result.structuredContent
    assert metadata["original_tool"] == "my_mutating_tool"
```

## How to update seed data

When the schema changes:
1. Update `tests/seed_test_data.py` to add/remove/rename columns.
2. Follow the `TABLE_DATA` insertion order (respects FK dependencies).
3. Run `pytest` to verify nothing else broke.

## Conventions

- All test IDs use "T" prefix: `SO-T001`, `CUST-0101`, etc.
- Simulation time is fixed at `2025-08-01T08:00:00`.
- REST tests are marked with `@pytest.mark.rest`, MCP tests with `@pytest.mark.mcp`.
- No test should modify the database. If you need to test writes, use a separate fixture with a per-test DB copy.
