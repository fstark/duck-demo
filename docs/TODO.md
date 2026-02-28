# TODO – Simplification & Cleanup

Small, targeted improvements to reduce code, remove duplication, and streamline behavior.

---

### 1. Delete the three migration scripts
**Files:** `migrate_customers_table.py`, `migrate_documents_table.py`, `migrate_quotes_table.py`

All migrated tables are already defined in `schema.sql`. The migration scripts are dead code left over from incremental development. Two of them even reference `duck.db` instead of the current `demo.db`. Delete all three files.

---

### 2. Extract shared pricing totals calculation
**Files:** `services/quote.py`, `services/pricing.py`

Both independently implement the same discount/shipping logic:
```python
discount = config.PRICING_VOLUME_DISCOUNT_PCT * subtotal if total_qty >= config.PRICING_VOLUME_QTY_THRESHOLD else 0.0
shipping = 0.0 if subtotal >= config.PRICING_FREE_SHIPPING_THRESHOLD else 20.0
```
Extract a single `compute_totals(subtotal, total_qty)` helper in `PricingService` and call it from both places.

---

### 3. Fix `confirm_tools.py` dispatcher method name mismatches
**File:** `mcp_tools/confirm_tools.py`

The confirmation dispatcher calls ~15 service methods by wrong names:
- `sales_service.link_shipment_to_order()` → should be `link_shipment()`
- `production_service.create_production_order()` → should be `create_order()`
- `production_service.start_production_order()` → should be `start_order()`
- `production_service.complete_production_order()` → should be `complete_order()`
- `purchase_service.create_purchase_order()` → should be `create_order()`
- `purchase_service.restock_material()` → should be `restock_materials()`
- `purchase_service.receive_purchase_order()` → should be `receive()`
- `quote_service.revise_quote()` → method doesn't exist

Fix all method names and argument signatures to match the actual service APIs.

---

### 4. Fix broken imports/queries in `purchase_tools.py`
**File:** `mcp_tools/purchase_tools.py`

`purchase_restock_materials()` imports `get_db` (doesn't exist — should be `get_connection`), then queries `stock` using wrong column names (`quantity`, `reorder_quantity`, `type` instead of `on_hand`, `reorder_qty`). `purchase_create_order()` calls `inventory_service.get_stock(item_sku)` which doesn't exist.

Replace inline SQL with calls to the existing service methods that already do this correctly.

---

### 5. Fix `production_tools.py` calling nonexistent `get_order()`
**File:** `mcp_tools/production_tools.py`

`production_start_order` and `production_complete_order` call `production_service.get_order()`, but `ProductionService` only has `get_order_status()`.

Change both calls to `production_service.get_order_status()`.

---

### 6. Deduplicate CORS preflight handling across all route files
**Files:** All 13 files in `api_routes/`

Every route handler contains the same boilerplate:
```python
if request.method == "OPTIONS":
    return _cors_preflight(["GET"])
```
Add a `@cors("GET")` decorator or a Starlette middleware to handle OPTIONS automatically, eliminating ~26 copies of this pattern.

---

### 7. Remove unnecessary class wrappers from services
**Files:** All 16 files in `services/`

Every service is a class with only `@staticmethod` methods and a module-level singleton. There's no instance state, inheritance, or polymorphism. The class adds zero value. Converting to plain module-level functions would remove ~32 lines of `class Foo:` / `@staticmethod` / singleton boilerplate across the codebase.

---

### 8. Fix `DocumentService` to use `dict(row)` instead of index-based access
**File:** `services/document.py`

Unlike every other service (which uses `dict(row)`), `DocumentService` accesses columns by position (`row[0]`, `row[1]`, …). This is fragile and verbose. Since `row_factory = sqlite3.Row` is already set, just use `dict(row)` for consistency.

---

### 9. Deduplicate overdue-invoice logic
**Files:** `services/simulation.py`, `services/invoice.py`

`SimulationService.advance_time()` has inline SQL to mark invoices overdue — the exact same logic that `InvoiceService.mark_overdue()` already implements. Have `advance_time()` call `invoice_service.mark_overdue()` instead of duplicating the SQL.

---

### 10. Fix field access mismatches in invoice/quote tool confirmation dialogs
**Files:** `mcp_tools/invoice_tools.py`, `mcp_tools/quote_tools.py`

These tools call service methods and then access keys that don't exist in the response:
- `invoice_create` calls `sales_service.get_order()` (should be `get_order_details()`) and accesses flat keys like `customer_name`, `total_amount` — but the response is nested (`{"sales_order": {…}, "customer": {…}, …}`).
- `quote_send` / `quote_accept` access `quote.get("customer_name")` — but the response shape is `{"quote": {…}, "customer": {…}, "lines": […]}`.

Fix field access to match the actual return structures.
