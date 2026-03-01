# Known Coding-Pattern Issues

Catalogued during scenario-engine development (Feb 2026).  
Severity: **Critical** > High > Medium > Low.

---

## 1. Hardcoded Constants

### 1a · ~~Hardcoded supplier-name fallback~~ — ✅ Fixed

~~[services/purchase.py](../services/purchase.py) lines 24-31 uses keyword matching on
`item["name"]` to pick a supplier string.~~

**Fixed:** Added `default_supplier_id` column to the `items` table. Material items
now store their supplier FK directly. `PurchaseService.create_order()` looks up the
supplier via `item["default_supplier_id"]` instead of name-matching heuristics.
Seed data and scenario `base_setup` both populate the mapping.

### 1b · ~~Hardcoded flat shipping cost~~ — ✅ Fixed

~~The `20.0` flat shipping fallback was hardcoded in `services/pricing.py`,
`services/quote.py` (two locations).~~

**Fixed:** Added `PRICING_FLAT_SHIPPING = 20.0` to `config.py`. All three call-sites
now use `config.PRICING_FLAT_SHIPPING`.

### 1c · ~~Magic warehouse / location strings~~ — ✅ Fixed

~~`"WH-LYON"`, `"RM/RECV-01"`, `"FG"`, `"PROD-OUT"` appear as string literals in
services and scenario code.~~

**Fixed:** Added `WAREHOUSE_DEFAULT`, `LOC_FINISHED_GOODS`, `LOC_PRODUCTION_OUT`,
and `LOC_RAW_MATERIAL_RECV` to `config.py`. All service, scenario, and seed code
now references these constants.

---

## 2. Dict Return-Type Misuse

### 2a · ~~`shipping` returned as dict, stored as REAL~~ — ✅ Fixed

~~`compute_pricing` returned `"shipping": {"amount": ..., "description": ...}` (a dict)
but `create_invoice` bound it into a `REAL` column.~~

**Fixed:** `compute_pricing` now returns `"shipping"` as a plain `float` and the
description as a separate `"shipping_note"` key. Removed the `isinstance` workaround
in `create_invoice`.

### 2b · ~~Duplicate keys in pricing dict~~ — ✅ Fixed

~~The pricing dict contained `"subtotal"` and `"discount"` twice (copy-paste).~~

**Fixed:** Removed the duplicate keys from the return dict.

---

## 3. Silently Swallowed Exceptions

### 3a · ~~Bare `except Exception: pass` in scenario code~~ — ✅ Fixed

~~Multiple places in [scenarios/s01_steady_state.py](../scenarios/s01_steady_state.py)
catch and discard all errors.~~

**Fixed:** Replaced all silent `except Exception: pass` blocks with
`logger.warning(...)` in `s01_steady_state.py` (3 sites). Two `except ValueError: pass`
blocks in `helpers.py` (expected/benign) now log at `debug` level. One PIL
`except Exception: pass` in `base_setup.py` also logs at `debug`. Two bare
`except:` in `system_routes.py` narrowed to `except Exception:`. Five
`logger.debug` exception handlers in `s01_steady_state.py` promoted to
`logger.warning`.

### 3b · ~~PDF generation failures logged but not surfaced~~ — ✅ Fixed

~~`issue_invoice` / `send_quote` returned success even when the PDF was missing.~~

**Fixed:** Both `issue_invoice` (invoice.py) and `send_quote` (quote.py) now
add a `"warning"` key to the return dict when PDF generation fails, so callers
can detect the problem. `isError=False` in `catalog_tools.py` changed to
`isError=True` for actual errors.

### 3c · ~~Exception used for normal control flow~~ — ✅ Fixed

~~`start_order()` raised `ValueError` on insufficient stock, forcing callers
to use try/except for a normal retry condition.~~

**Fixed:** `start_order()` now pre-checks ingredient availability. If stock is
insufficient it returns `{"status": "waiting_for_stock", "shortfalls": [...]}`
instead of raising. Callers check the return value — no try/except needed.

---

## 4. ~~Database Connection / Locking~~ — ✅ Fixed

All fixed by thread-local connection reuse in `services/_base.py`: nested
`db_conn()` calls on the same thread now return the existing connection instead
of opening a competing one.

### 4a · ~~Nested `db_conn()` in `advance_time` → `update_readiness`~~ — ✅ Fixed

### 4b · ~~`restock_materials` calls `create_order` inside open connection~~ — ✅ Fixed

### 4c · ~~`search_orders` loops `compute_pricing` inside connection~~ — ✅ Fixed

### 4d · ~~`create_order` nests 3 service calls inside connection~~ — ✅ Fixed

### 4e · ~~Only `deduct_stock` accepts an optional `conn` param~~ — ✅ Moot

Thread-local reuse makes explicit `conn` passing unnecessary. `deduct_stock`
still accepts it (belt-and-suspenders); other methods don't need it.

---

## 5. Inconsistent / Wrong Method Names

### 5a · `confirm_tools.py` is almost entirely broken — Critical

[mcp_tools/confirm_tools.py](../mcp_tools/confirm_tools.py) dispatches
confirmation actions using method names and signatures that **do not exist**:

| Line | Calls | Actual method |
|------|-------|---------------|
| 58-62 | `sales_service.link_shipment_to_order()` | `link_shipment()` |
| 67-70 | `logistics_service.create_shipment(sales_order_id=, carrier=)` | different signature |
| 80-83 | `production_service.create_production_order(recipe_id, qty)` | `create_order(recipe_id, notes)` |
| 84-86 | `production_service.start_production_order()` | `start_order()` |
| 89-91 | `production_service.complete_production_order()` | `complete_order(id, qty, wh, loc)` |
| 95-97 | `purchase_service.create_purchase_order(supplier_id, items)` | `create_order(sku, qty, name)` |
| 98-101 | `purchase_service.restock_material(material_id, qty)` | `restock_materials()` (no args) |
| 102-104 | `purchase_service.receive_purchase_order()` | `receive(id, wh, loc)` |
| 133-136 | `quote_service.create_quote(cust, items, notes)` | completely different signature |
| 151-155 | `invoice_service.issue_invoice(id, payment_due_days=)` | `issue_invoice(id)` |

Every MCP App UI confirmation flow will crash with `AttributeError`.

### 5b · `production_tools.py` calls `get_order()` — Critical

[mcp_tools/production_tools.py](../mcp_tools/production_tools.py) lines 110, 157
call `production_service.get_order(id)` — actual method is `get_order_status(id)`.

### 5c · `production_tools.py` reads non-existent field `qty_to_produce` — Medium

Line 117: `order.get("qty_to_produce")` — no such field in the return dict or DB
column.  Production quantity lives in `recipes.output_qty`.

---

## 6. Missing Default Parameters

### 6a · ~~`MessagingService.create_email`~~ — ✅ Fixed

~~`recipient_email` and `recipient_name` were `Optional[str]` with no default.~~

**Fixed:** Added `= None` defaults for `sales_order_id`, `recipient_email`, and
`recipient_name`. Callers no longer need to pass `None` explicitly.

### 6b · ~~`RecipeService.list_recipes`, `MessagingService.list_emails`~~ — ✅ Fixed

~~Both had `Optional` / `int` params with no defaults.~~

**Fixed:** `list_recipes(output_item_sku=None, limit=50)` and
`list_emails(customer_id=None, sales_order_id=None, status=None, limit=20)` now
have sensible defaults matching their MCP tool counterparts.

---

## 7. Type Mismatches (float / int)

### 7a · ~~`complete_order(qty_produced: int, …)` but schema is REAL~~ — ✅ Fixed

**Fixed:** Changed type hint from `int` to `float` to match the `REAL` schema.

### 7b · ~~PDF generation truncates float quantities~~ — ✅ Fixed

**Fixed:** Replaced `int(line['qty'])` with `f"{line['qty']:g}"` format spec in
both `invoice.py` and `quote.py`. Whole numbers display as `10`, fractional as `10.5`.

---

## 8. Schema / Address Inconsistencies

### 8a · ~~`ship_to` dict keys vs. DB column names~~ — ✅ Fixed

~~Callers passed `{"line1": …, "city": …}` while DB columns used `ship_to_line1`,
`ship_to_city`, etc. No shared mapping.~~

**Fixed:** Added `ship_to_columns()`, `ship_to_dict()`, and `customer_to_ship_to()`
helpers in `utils.py`. All services (`sales.py`, `logistics.py`, `quote.py`) and
scenarios now use these instead of inline `.get()` mapping.

### 8b · ~~`address_line2` exists on `customers` but not on orders / shipments / quotes~~ — ✅ Fixed

~~`customers.address_line2` had no counterpart in other tables.~~

**Fixed:** Added `ship_to_line2` column to `quotes`, `sales_orders`, and `shipments`
in `schema.sql`. The address helpers carry `line2` through the full pipeline.

---

## 9. Quantity Representation

### 9a · Use integer quantities with explicit unit-of-measure — Medium

All `qty` columns are `REAL`, which invites floating-point rounding issues
(e.g. `0.1 + 0.2 ≠ 0.3`, inexact `== 0` checks).  The `uom` column already
exists on `items` but is cosmetic — nothing enforces that `200` means "200 g".

**Suggested fix:** Switch `qty` / `output_qty` / `input_qty` / `qty_produced` /
`reorder_qty` columns to `INTEGER`, storing quantities in the item’s smallest
unit (grams, millilitres, pieces, etc.).  The `uom` on `items` becomes the
authoritative base unit.

This touches schema, seed data, all services that read/write quantities,
PDF rendering, and the UI display layer (format `1500` as `"1.5 kg"` or
`"1500 mL"` depending on `uom`).


## Summary

| #  | Category              | Severity     |
|----|-----------------------|--------------|
| 5a | Wrong method names    | **Critical** |
| 5b | Wrong method name     | **Critical** |
| 4a | Nested db_conn        | ✅ Fixed     |
| 4b | Nested db_conn        | ✅ Fixed     |
| 4c | Nested db_conn        | ✅ Fixed     |
| 4d | Nested db_conn        | ✅ Fixed     |
| 3a | Swallowed exceptions  | ✅ Fixed     |
| 1a | Hardcoded constants   | ✅ Fixed     |
| 2a | Dict return misuse    | ✅ Fixed     |
| 3b | Swallowed exceptions  | ✅ Fixed     |
| 3c | Exception as control flow | ✅ Fixed    |
| 4e | No shared conn param  | ✅ Moot      |
| 5c | Non-existent field    | Medium       |
| 7a | float/int mismatch    | ✅ Fixed     |
| 1b | Hardcoded constant    | ✅ Fixed     |
| 1c | Magic strings         | ✅ Fixed     |
| 2b | Duplicate dict keys   | ✅ Fixed     |
| 6a-b | Missing defaults   | ✅ Fixed     |
| 7b | Truncation in PDFs    | ✅ Fixed     |
| 8a-b | Address naming     | ✅ Fixed     |
| 9a   | Integer qty + UoM  | Medium       |
