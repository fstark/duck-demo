# Tariff Codes — Implementation Plan

Reference: [TARIFFS_DESIGN.md](TARIFFS_DESIGN.md)

---

## Step 1 — Config constants

**Files:** `config.py`

Add:

```python
WAREHOUSE_COUNTRY = "FR"
TARIFF_REQUIRED_DESTINATIONS = {"CH", "GB", "US", "CA", "JP", "AU", "NO"}
EU_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
}
SUPPORTED_SHIP_COUNTRIES = EU_COUNTRIES | TARIFF_REQUIRED_DESTINATIONS
```

`SUPPORTED_SHIP_COUNTRIES` is the union — anything outside is rejected.

**Gate:** `python -c "import config; print(config.TARIFF_REQUIRED_DESTINATIONS)"` works.

---

## Step 2 — Schema migration

**Files:** `schema.sql`

Add two nullable columns to `shipment_lines`:

```sql
CREATE TABLE IF NOT EXISTS shipment_lines (
    id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    tariff_code TEXT,
    tariff_description TEXT
);
```

Update `shipment_lines` DDL in-place (the DB is regenerated from scratch on every run via `python -m scenarios`).

**Gate:** `python -m scenarios --only s01` runs without errors. Quick SQL check:

```bash
sqlite3 demo.db "PRAGMA table_info(shipment_lines);" | grep tariff
```

---

## Step 3 — Service layer: `services/logistics.py`

### 3a — `create_shipment()`: accept tariff fields

Extend the per-content loop that inserts into `shipment_lines`. Each content dict can now optionally carry `tariff_code` and `tariff_description`. Update the INSERT to include the two new columns.

Today:
```python
conn.execute(
    "INSERT INTO shipment_lines (id, shipment_id, item_id, qty) VALUES (?, ?, ?, ?)",
    (line_id, shipment_id, item["id"], c["qty"])
)
```

After:
```python
conn.execute(
    "INSERT INTO shipment_lines (id, shipment_id, item_id, qty, tariff_code, tariff_description)"
    " VALUES (?, ?, ?, ?, ?, ?)",
    (line_id, shipment_id, item["id"], c["qty"],
     c.get("tariff_code"), c.get("tariff_description"))
)
```

### 3b — `get_shipment_status()`: return tariff fields

The query that fetches shipment lines already does `SELECT sl.*, i.sku ...`. Since we added columns to the table, they'll be included in `dict(row)` automatically. Verify the response includes `tariff_code` and `tariff_description` keys.

### 3c — Add destination validation helpers

```python
import config

def is_tariff_required(ship_to_country: str) -> bool:
    return ship_to_country.upper() in config.TARIFF_REQUIRED_DESTINATIONS

def is_supported_destination(ship_to_country: str) -> bool:
    return ship_to_country.upper() in config.SUPPORTED_SHIP_COUNTRIES
```

Export them on the `logistics_service` SimpleNamespace.

**Gate:** Direct service test:

```bash
python -c "
from services.logistics import is_tariff_required, is_supported_destination
assert is_tariff_required('US') == True
assert is_tariff_required('DE') == False
assert is_supported_destination('DE') == True
assert is_supported_destination('XX') == False
print('OK')
"
```

---

## Step 4 — MCP tool: tariff-aware `logistics_create_shipment`

**Files:** `mcp_tools/logistics_tools.py`

Modify the `create_shipment` tool function. Before building the confirmation response, add logic:

```python
ship_to_country = ship_to.get("country", "").upper()

# Reject unsupported destinations
if not logistics_service.is_supported_destination(ship_to_country):
    return {"error": f"Destination country '{ship_to_country}' is not supported for shipping."}

# Check if tariff codes are needed
if logistics_service.is_tariff_required(ship_to_country):
    # Check if all packages have tariff codes
    all_contents = [c for pkg in packages for c in pkg.get("contents", [])]
    missing_tariff = any(not c.get("tariff_code") for c in all_contents)

    if missing_tariff:
        # Resolve item names and call tariff_suggest internally
        # Return tariff picker MCP-UI instead of confirmation
        return _build_tariff_picker_response(ship_to_country, packages, arguments)

# Tariffs either not needed or already provided → proceed to confirmation
return create_confirmation_response(...)
```

The `_build_tariff_picker_response` helper:
1. Resolves item names from SKUs via `catalog_service.get_item()`.
2. Calls `services.tariff.suggest_tariff_codes()` with origin=`config.WAREHOUSE_COUNTRY`, destination=`ship_to_country`, products=[item names].
3. Builds a `ToolResult` with `meta={"ui": {"resourceUri": "ui://tariff-picker/selector"}}` and `structuredContent` containing the items + suggestions + `original_args`.

This requires importing from `fastmcp.tools.tool` (for `ToolResult`) and from `mcp.types` (for `TextContent`).

**Note:** The tool needs `structured_output=False` which it already has.

**Gate:** Unit test in Step 7 mocks `tariff_suggest` and verifies:
- Intra-EU call → returns confirmation response (no tariff picker).
- Non-EU call without tariffs → returns tariff picker response.
- Non-EU call with tariffs → returns confirmation response.
- Unsupported country → returns error.

---

## Step 5 — Register tariff picker MCP-UI resource

**Files:** `server.py`, `mcp_apps_ui/tariff-picker.html`

### 5a — Resource registration in `server.py`

Add alongside the existing `generic-confirm` resource:

```python
@mcp.resource("ui://tariff-picker/selector", mime_type="text/html;profile=mcp-app")
def get_tariff_picker_ui() -> str:
    """Serves the tariff code picker MCP App UI."""
    ui_path = os.path.join(os.path.dirname(__file__), "mcp_apps_ui", "tariff-picker.html")
    if os.path.exists(ui_path):
        with open(ui_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<html><body>Tariff picker UI not found</body></html>"
```

### 5b — Create `mcp_apps_ui/tariff-picker.html`

A standalone React SPA (similar to `generic-confirm.html`). Can be a simple self-contained HTML file with inline JS for the MVP — no Vite build required.

**UI spec:**
- Reads `structuredContent` from the MCP App data payload.
- Header: "Select tariff codes for shipment to {country}".
- One card per item: item name, quantity, radio group of suggestions (pre-selects highest confidence).
- Each radio: `[code] description (confidence badge)`.
- Optional "Custom code" text input per item.
- Confirm button → sends selected codes back to the agent.

The HTML file should be structured as:
```html
<!doctype html>
<html>
<head><title>Tariff Code Selection</title></head>
<body>
  <div id="root"></div>
  <script type="module">
    // Read structuredContent from MCP App context
    // Render picker UI
    // On confirm: post message back with selections
  </script>
</body>
</html>
```

**This is the most complex single piece** — the MCP App UI. It can be iterated on after the backend is working. A minimal version that just shows suggestions and lets the user confirm is sufficient for MVP.

**Gate:** Server starts, resource is accessible. Manual test in VS Code MCP client.

---

## Step 6 — REST API: return tariff fields

**Files:** `api_routes/shipment_routes.py`

No code changes needed if `get_shipment_status()` already returns `tariff_code`/`tariff_description` via `SELECT sl.*`. Verify by reading the response.

If the shipment list endpoint (`GET /api/shipments`) does a raw SQL query that doesn't join `shipment_lines`, tariff info won't appear there — which matches the design (tariff info is detail-level only).

**Gate:** Start server, `GET /api/shipments/SHIP-xxxx` includes `tariff_code`/`tariff_description` in lines.

---

## Step 7 — Automated tests

### 7a — Extend `tests/seed_test_data.py`

Add a second test shipment with a non-EU destination and tariff codes on its lines:

```python
# In SHIPMENTS:
{
    "id": "SHIP-T002",
    "ship_from_warehouse": config.WAREHOUSE_DEFAULT,
    "ship_to_line1": "123 Main St",
    "ship_to_line2": None,
    "ship_to_postal_code": "10001",
    "ship_to_city": "New York",
    "ship_to_country": "US",
    "planned_departure": "2025-08-18",
    "planned_arrival": "2025-08-25",
    "status": "planned",
    "tracking_ref": None,
    "dispatched_at": None,
    "delivered_at": None,
},

# In SHIPMENT_LINES:
{"id": "SHL-T002", "shipment_id": "SHIP-T002", "item_id": "ITEM-CLASSIC-10", "qty": 6,
 "tariff_code": "9503.00", "tariff_description": "Toys; other toys"},

# In SALES_ORDER_SHIPMENTS:
{"sales_order_id": "SO-T001", "shipment_id": "SHIP-T002"},
```

### 7b — `tests/test_rest_shipments.py` — new tests

```python
def test_get_shipment_with_tariff(rest_client):
    """International shipment lines include tariff_code and tariff_description."""
    resp = rest_client.get("/api/shipments/SHIP-T002")
    assert resp.status_code == 200
    data = resp.json()
    lines = data["lines"]
    assert len(lines) >= 1
    assert lines[0]["tariff_code"] == "9503.00"
    assert lines[0]["tariff_description"] == "Toys; other toys"

def test_get_shipment_without_tariff(rest_client):
    """Domestic shipment lines have null tariff fields."""
    resp = rest_client.get("/api/shipments/SHIP-T001")
    assert resp.status_code == 200
    data = resp.json()
    lines = data["lines"]
    assert len(lines) >= 1
    assert lines[0].get("tariff_code") is None
```

### 7c — `tests/test_mcp_tariff.py` — extend with logistics integration

Add tests that call the `logistics_create_shipment` tool with mocked `tariff_suggest`:

```python
@patch("services.tariff.chat_completion", return_value=_FakeResponse(...))
def test_create_shipment_non_eu_missing_tariff_returns_picker(mock, mcp_app):
    """Non-EU destination without tariff codes returns tariff picker."""
    result = _call(mcp_app, "logistics_create_shipment",
        ship_from={"warehouse": "WH-LYON"},
        ship_to={"line1": "123 Main St", "city": "New York", "postal_code": "10001", "country": "US"},
        planned_departure="2025-09-01",
        planned_arrival="2025-09-08",
        packages=[{"contents": [{"sku": "CLASSIC-DUCK-10CM", "qty": 12}]}],
    )
    # Should be a ToolResult/CallToolResult with tariff picker, not a confirmation
    # Verify it contains suggestions

@patch("services.tariff.chat_completion", return_value=_FakeResponse(...))
def test_create_shipment_non_eu_with_tariff_proceeds(mock, mcp_app):
    """Non-EU destination with tariff codes proceeds to confirmation."""
    result = _call(mcp_app, "logistics_create_shipment",
        ship_from={"warehouse": "WH-LYON"},
        ship_to={"line1": "123 Main St", "city": "New York", "postal_code": "10001", "country": "US"},
        planned_departure="2025-09-01",
        planned_arrival="2025-09-08",
        packages=[{"contents": [{"sku": "CLASSIC-DUCK-10CM", "qty": 12,
                                  "tariff_code": "9503.00", "tariff_description": "Toys"}]}],
    )
    # Should be a normal confirmation response

def test_create_shipment_eu_no_tariff_needed(mcp_app):
    """Intra-EU destination proceeds without tariff codes."""
    result = _call(mcp_app, "logistics_create_shipment",
        ship_from={"warehouse": "WH-LYON"},
        ship_to={"line1": "10 Unter den Linden", "city": "Berlin", "postal_code": "10117", "country": "DE"},
        planned_departure="2025-09-01",
        planned_arrival="2025-09-03",
        packages=[{"contents": [{"sku": "CLASSIC-DUCK-10CM", "qty": 12}]}],
    )
    # Should be a normal confirmation response

def test_create_shipment_unsupported_country(mcp_app):
    """Unsupported destination country returns error."""
    result = _call(mcp_app, "logistics_create_shipment",
        ship_from={"warehouse": "WH-LYON"},
        ship_to={"line1": "1 Street", "city": "Somewhere", "postal_code": "00000", "country": "XX"},
        planned_departure="2025-09-01",
        planned_arrival="2025-09-03",
        packages=[{"contents": [{"sku": "CLASSIC-DUCK-10CM", "qty": 12}]}],
    )
    assert "error" in result
```

**Gate:** `pytest tests/test_mcp_tariff.py tests/test_rest_shipments.py -v` — all pass.

---

## Step 8 — Frontend: Shipment Detail Page

**Files:** `ui/src/pages/ShipmentDetailPage.tsx`

Add conditional tariff columns to the shipment lines table:

```tsx
const hasTariff = shipment.lines?.some((l: any) => l.tariff_code);

// In columns array:
...(hasTariff ? [
    { key: 'tariff_code', label: 'Tariff Code', sortable: true },
    { key: 'tariff_description', label: 'Description', sortable: true },
] : []),
```

Only shows tariff columns when at least one line has a tariff code (domestic shipments stay clean).

**Gate:** Visual check — load a shipment with tariff codes in the UI, verify columns appear.

---

## Step 9 — Scenario data: add international shipments

**Files:** `scenarios/helpers.py` or `scenarios/s01_steady_state.py`

Optional: add a few international customers (e.g. US, CH) to the demo scenarios so that some shipments have tariff codes in the generated data. This makes the feature visible in the UI out of the box.

Not blocking — can be done as a follow-up.

**Gate:** `python -m scenarios --only s01` runs, `sqlite3 demo.db "SELECT tariff_code FROM shipment_lines WHERE tariff_code IS NOT NULL"` returns rows.

---

## Step 10 — Smoke test: full server

```bash
source venv/bin/activate && source secrets.sh
python -m scenarios --only s01
python server.py &
sleep 2

# Test tariff suggestion tool still works
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"tariff_suggest","arguments":{"country_of_origin":"FR","country_of_destination":"US","products":["rubber duck"]}}}' | head -c 500

# Test shipment detail includes tariff fields
curl -s http://localhost:8000/api/shipments | python -m json.tool | head -20

kill %1
```

**Gate:** Server starts. Tariff suggestion returns codes. Shipment API includes tariff fields.

---

## Step 11 — Full regression

```bash
pytest -v
```

**Gate:** All tests pass, no regressions.

---

## Step 12 — Manual E2E validation

### 12a — Via MCP tool: international shipment flow

In VS Code MCP client, ask the sales agent to create a shipment to the US. Verify:
1. Agent calls `logistics_create_shipment` with US destination.
2. Tariff picker UI appears with suggestions.
3. User selects tariff codes.
4. Agent re-calls with tariff codes filled in.
5. Normal confirmation dialog appears.
6. User confirms → shipment created.
7. `logistics_get_shipment` returns tariff codes on lines.

### 12b — Via MCP tool: intra-EU shipment

Ask for a shipment to Germany. Verify no tariff picker appears — goes straight to confirmation.

### 12c — Via UI

Open the shipment detail page for an international shipment. Verify tariff code and description columns appear in the lines table.

---

## Implementation Order & Dependencies

```
Step 1 (config) ─────────────────────────────────────┐
Step 2 (schema) ─────────────────────────────────────┤
                                                      ├→ Step 3 (service) → Step 4 (MCP tool) → Step 5 (MCP UI)
Step 7a (seed data) ─────────────────────────────────┘                                            │
                                                                                                   ↓
Step 6 (REST) ← depends on Step 3                                                        Step 7b,c (tests)
Step 8 (frontend) ← depends on Step 3                                                            │
Step 9 (scenarios) ← depends on Steps 2,3                                                        ↓
                                                                                          Step 10 (smoke)
                                                                                                   │
                                                                                                   ↓
                                                                                           Step 11 (regression)
                                                                                                   │
                                                                                                   ↓
                                                                                           Step 12 (manual E2E)
```

Steps 1, 2, 7a can be done in parallel. Step 5 (MCP UI) is the most complex single piece and can be iterated on independently after the backend works.

---

## Summary

| Step | Type | Key files | Gate |
|---|---|---|---|
| 1 | Config | `config.py` | Imports clean |
| 2 | Schema | `schema.sql` | `python -m scenarios` works |
| 3 | Service | `services/logistics.py` | Helpers work, INSERT updated |
| 4 | MCP tool | `mcp_tools/logistics_tools.py` | Tariff detection logic |
| 5 | MCP UI | `server.py`, `mcp_apps_ui/tariff-picker.html` | Resource registered, UI renders |
| 6 | REST | `api_routes/shipment_routes.py` | Tariff fields in response |
| 7 | Tests | `tests/seed_test_data.py`, `tests/test_rest_shipments.py`, `tests/test_mcp_tariff.py` | pytest green |
| 8 | Frontend | `ui/src/pages/ShipmentDetailPage.tsx` | Columns visible |
| 9 | Scenarios | `scenarios/` | International shipments in demo data |
| 10 | Smoke | — | Server runs, APIs respond |
| 11 | Regression | — | Full `pytest` green |
| 12 | Manual | — | Full MCP flow works in VS Code |
