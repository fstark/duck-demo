# Tariff Codes Feature — Design (Strawman)

## Problem

When shipping internationally, each product in a shipment needs an HS (Harmonized System) tariff code for customs. Today shipments carry no tariff information. We want to:

1. Store tariff codes on shipment lines.
2. Surface tariff codes in the UI and APIs.
3. Help agents pick the right codes when creating shipments, using the MyForterro inference API for suggestions.

## Where Tariff Codes Live

Tariff codes belong on **shipment lines**, not on items or sales order lines. Rationale:

- The same item can have different tariff codes depending on origin/destination.
- Items in the catalog don't have an inherent tariff code — it depends on the trade lane.
- A sales order is a commercial document; tariff codes are a logistics/customs concern.
- Shipments already carry origin (`ship_from_warehouse` → implies country) and destination (`ship_to_country`), so this is the natural place.

## Data Model Changes

### `shipment_lines` — add tariff columns

```sql
ALTER TABLE shipment_lines ADD COLUMN tariff_code TEXT;         -- e.g. "9503.00"
ALTER TABLE shipment_lines ADD COLUMN tariff_description TEXT;  -- e.g. "Toys; other toys..."
```

Both nullable — tariff codes are optional for domestic shipments (same country origin/destination).

### When are tariff codes "needed"?

A shipment line **needs** a tariff code when the destination country is **outside the EU**. We operate from the EU (warehouse in France), and intra-EU shipments don't require customs tariff codes.

Rather than maintaining a full EU country list, we use a **closed list of non-EU countries we accept shipments to**:

```python
# config.py
WAREHOUSE_COUNTRY = "FR"
TARIFF_REQUIRED_DESTINATIONS = {"CH", "GB", "US", "CA", "JP", "AU", "NO"}
```

This is intentionally small and curated — it's a demo, and these are the realistic non-EU destinations for a French duck factory. Adding a new destination is a one-line config change.

```
tariff_required = (ship_to_country in TARIFF_REQUIRED_DESTINATIONS)
```

Intra-EU shipments (FR→DE, FR→ES, etc.) proceed without tariff codes. Shipments to unknown countries outside the list are rejected with a clear error ("destination not supported for shipping").

## Flow: Creating a Shipment with Tariff Codes

### Current flow (no tariffs)

```
Agent calls logistics_create_shipment(ship_from, ship_to, packages, ...)
  → Returns confirmation UI
  → User confirms
  → Shipment created
```

### New flow (with tariffs)

```
Agent calls logistics_create_shipment(ship_from, ship_to, packages, ...)
  │
  ├─ Intra-EU destination? → proceed as today, no tariff codes needed
  │
  ├─ Non-EU destination NOT in TARIFF_REQUIRED_DESTINATIONS? → reject with error
  │
  └─ Non-EU destination in TARIFF_REQUIRED_DESTINATIONS?
       │
       ├─ Tariff codes provided in packages[].tariff_code? → proceed to confirmation
       │
       └─ Tariff codes missing?
            → Tool internally calls tariff_suggest() for all items
            → Returns MCP-UI tariff picker with suggestions
            → User selects one code per item and confirms
            → Agent re-calls logistics_create_shipment with codes filled in
            → Proceeds to normal confirmation flow
```

This means the tariff picker is an **extra interaction step** before the existing confirmation dialog. The agent sees two round-trips for international shipments: first the tariff picker, then the shipment confirmation.

### The `packages` parameter today

```python
packages = [
    {"item_id": "ITEM-CLASSIC-10", "qty": 24},
    {"item_id": "ITEM-ELVIS-20", "qty": 12},
]
```

### Extended with tariff codes

```python
packages = [
    {"item_id": "ITEM-CLASSIC-10", "qty": 24, "tariff_code": "9503.00", "tariff_description": "Toys"},
    {"item_id": "ITEM-ELVIS-20", "qty": 12, "tariff_code": "9503.00", "tariff_description": "Toys"},
]
```

## Tariff Suggestion + Selection Flow

When `logistics_create_shipment` is called for a non-EU destination without tariff codes, the tool **internally** calls `tariff_suggest()` with the origin/destination countries and product descriptions from the shipment lines. It then returns an MCP-UI tariff picker pre-populated with the suggestions. No extra agent round-trip needed for the suggestion step.

### Sequence

1. Agent calls `logistics_create_shipment(ship_from, ship_to, packages, ...)`.
2. Tool detects non-EU destination + missing tariff codes.
3. Tool resolves item names from `item_id`s (via catalog service).
4. Tool calls `tariff_suggest(country_of_origin="FR", country_of_destination=ship_to_country, products=[item descriptions])`.
5. Tool returns MCP-UI tariff picker with suggestions embedded.
6. User selects one tariff code per item in the picker UI and confirms.
7. Picker returns selected codes to the agent.
8. Agent re-calls `logistics_create_shipment` with `tariff_code`/`tariff_description` filled in on each package.
9. Tool detects tariff codes are present → proceeds to normal confirmation dialog.
10. User confirms → shipment created.

### New MCP-UI: Tariff Code Picker (`tariff-picker.html`)

A dedicated MCP App UI for tariff code selection. Registered as a resource:

```python
@mcp.resource("ui://tariff-picker/selector", mime_type="text/html;profile=mcp-app")
```

Receives structured content:

```json
{
  "ship_to_country": "US",
  "items": [
    {
      "item_id": "ITEM-CLASSIC-10",
      "item_name": "Classic Duck 10cm",
      "qty": 24,
      "suggestions": [
        {"code": "9503.00", "description": "Toys; other toys...", "confidence": "high"},
        {"code": "4016.99", "description": "Rubber articles...", "confidence": "medium"}
      ]
    },
    {
      "item_id": "ITEM-ELVIS-20",
      "item_name": "Elvis Duck 20cm",
      "qty": 12,
      "suggestions": [
        {"code": "9503.00", "description": "Toys; other toys...", "confidence": "high"}
      ]
    }
  ],
  "original_args": { /* full original logistics_create_shipment arguments for re-call */ }
}
```

**UI layout:**
- Header: "Select tariff codes for shipment to {country}"
- One card per item showing: item name, quantity, and a radio group of suggested codes (pre-selecting the highest-confidence option).
- Each radio option shows: code, description, confidence badge.
- "Custom code" text input option per item as fallback.
- Confirm button at the bottom.

**On confirm:** The picker returns the selected tariff codes to the agent, which re-calls `logistics_create_shipment` with codes populated.

## API Changes

### `logistics_create_shipment` MCP tool

Add optional `tariff_code` and `tariff_description` fields to each package entry. If international and missing, return a structured response signaling that tariff codes are needed (not an error — a "need more info" response).

### `logistics_get_shipment` MCP tool / `GET /api/shipments/:id`

Include `tariff_code` and `tariff_description` in each shipment line in the response.

### `GET /api/shipments`

Include tariff info in line details when present.

### New tool: `tariff_suggest` (already implemented)

Already exists — suggests HS codes given countries and product descriptions.

## Service Layer Changes

### `services/logistics.py`

- `create_shipment()`: Accept optional `tariff_code`/`tariff_description` per package. Write to `shipment_lines`.
- `get_shipment_status()`: Include `tariff_code`/`tariff_description` in shipment lines query.
- Add a helper: `is_tariff_required(ship_to_country)` → bool (checks against `config.TARIFF_REQUIRED_DESTINATIONS`).
- Add a helper: `is_supported_destination(ship_to_country)` → bool (EU countries + tariff destinations).

### `services/tariff.py`

Already exists. No changes needed — `suggest_tariff_codes()` is called internally by the logistics tool when tariff codes are missing.

## UI Changes

### Shipment Detail Page

Show tariff code and description in the shipment lines table (new columns). Only display when at least one line has a tariff code (to avoid clutter on domestic shipments).

### Shipments List Page

No change — tariff info is detail-level, not list-level.

## What Doesn't Change

- **Sales orders** — no tariff columns. Tariffs are a shipment concern.
- **Sales order lines** — unchanged.
- **Quotes** — unchanged.
- **Items / catalog** — no tariff codes on items. The same item can have different codes depending on the trade lane.
- **`tariff_suggest` service** — already built, used as-is.

## Resolved Design Decisions

1. **EU vs non-EU, not origin≠destination**: We operate from the EU. Intra-EU shipments (FR→DE, FR→ES) don't need tariff codes. Only non-EU destinations do. A closed list in `config.TARIFF_REQUIRED_DESTINATIONS` defines the supported non-EU destinations.
2. **Internal suggestion**: When `logistics_create_shipment` detects a non-EU destination without tariff codes, it internally calls `tariff_suggest()` and returns the MCP-UI picker pre-populated with suggestions. No extra agent round-trip for the suggestion step.
3. **Separate picker UI**: A dedicated `tariff-picker.html` MCP App rather than overloading the generic confirmation dialog.
4. **Warehouse country**: `config.WAREHOUSE_COUNTRY = "FR"` — simple constant, used as origin for tariff suggestions.
5. **Multiple shipments for one SO**: Tariff codes are per shipment line, so partial shipments each carry their own codes. No issue.
6. **Editing tariff codes after creation**: Not needed for MVP. Shipments are created once, then dispatched.

## Open Questions

1. **EU country list maintenance**: Should we hardcode the EU27 list or use a simpler heuristic? Hardcoded set in `config.py` is fine for the demo.

## Summary of Changes

| Layer | File | Change |
|---|---|---|
| Schema | `schema.sql` | Add `tariff_code`, `tariff_description` to `shipment_lines` |
| Config | `config.py` | Add `WAREHOUSE_COUNTRY`, `TARIFF_REQUIRED_DESTINATIONS` |
| Service | `services/logistics.py` | Accept + store + return tariff fields; `is_tariff_required()` helper |
| MCP tool | `mcp_tools/logistics_tools.py` | Extended `packages` with tariff fields; internal suggestion + picker flow |
| MCP UI | `mcp_apps_ui/tariff-picker.html` | New picker UI for tariff code selection |
| MCP resource | `server.py` or tools file | Register `ui://tariff-picker/selector` resource |
| REST | `api_routes/shipment_routes.py` | Return tariff fields in responses |
| Frontend | `ui/src/pages/ShipmentDetailPage.tsx` | Show tariff columns in lines table |
| Tests | `tests/test_mcp_sales.py`, `tests/test_rest_shipments.py` | Extend with tariff fields |
