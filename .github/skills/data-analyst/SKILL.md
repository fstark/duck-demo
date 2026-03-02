---
name: data-analyst
description: Analyse data in the demo SQLite database using SQL queries
user-invokable: true
---

## Purpose

Answer data questions about the duck-demo ERP by running SQL against the SQLite database at `demo.db` in the project root.

## When to use

Use this skill when the user asks about data stored in the database: record counts, status distributions, timing analysis, trends, throughput, lead times, etc.

## How to run queries

1. Activate the venv: `source venv/bin/activate`
2. Run queries via the terminal:
   ```
   sqlite3 demo.db "SELECT ..."
   ```
3. For multi-line or complex queries, use `sqlite3 demo.db <<'SQL' ... SQL` or pipe a file.
4. Use `-header -column` for readable output, or `-json` when you need to post-process.

## Answer format

- **Be concise.** A table or a single number is often the best answer.
- **Use markdown tables** for tabular results. Keep columns relevant — don't dump every field.
- **Round monetary values** to 2 decimal places. Currency is always EUR.
- **Format quantities** according to UOM: divide grams by 1000 and show as kg, millilitres by 1000 as L, keep `ea` as-is. The `uom` column on the `items` table tells you which unit applies.
- **Show dates** as `YYYY-MM-DD`. Omit the time portion unless it matters for the question.
- **Limit output.** Default to `LIMIT 20` unless the user asks for everything. Mention when results are truncated.

## Schema reference

Read `schema.sql` in the project root for the full DDL. Key points below.

### Simulated time

All `TEXT` timestamp columns store ISO-8601 strings (`YYYY-MM-DD HH:MM:SS`).
The system runs on simulated time stored in `simulation_state.sim_time`. Use it as "now":

```sql
SELECT sim_time FROM simulation_state WHERE id = 1;
```

### Status workflows

| Entity | Table | Statuses (in order) |
|---|---|---|
| Quote | `quotes` | `draft` → `sent` → `accepted` / `rejected` / `expired` / `superseded` |
| Sales Order | `sales_orders` | `draft` → `confirmed` → `completed` |
| Production Order | `production_orders` | `planned` → `waiting` → `ready` → `in_progress` → `completed` |
| Production Operation | `production_operations` | `pending` → `in_progress` → `completed` |
| Shipment | `shipments` | `planned` → `dispatched` → `delivered` |
| Purchase Order | `purchase_orders` | `ordered` → `received` |
| Invoice | `invoices` | `draft` → `issued` → `paid` / `overdue` |
| Email | `emails` | `draft` → `sent` |

### Key relationships

```
customer ──< quotes ──< quote_lines
                │
                ▼ (accept_quote creates SO)
customer ──< sales_orders ──< sales_order_lines
                │
                ├──< production_orders ──< production_operations
                │
                ├──< sales_order_shipments >── shipments ──< shipment_lines
                │
                ├──< invoices ──< payments
                │
                └──< emails
```

- `sales_orders.quote_id` → `quotes.id`
- `production_orders.sales_order_id` → `sales_orders.id`
- `production_orders.recipe_id` → `recipes.id`
- `recipe_ingredients.recipe_id` → `recipes.id`
- `recipe_operations.recipe_id` → `recipes.id`
- `production_operations.production_order_id` → `production_orders.id`
- `production_operations.recipe_operation_id` → `recipe_operations.id`
- `invoices.sales_order_id` → `sales_orders.id`
- `payments.invoice_id` → `invoices.id`
- `items.default_supplier_id` → `suppliers.id`
- `purchase_orders.item_id` → `items.id`

### Quantities

All `qty` / `on_hand` columns are **INTEGER** in the smallest base unit:
- `ea` → pieces (use as-is)
- `g` → grams (divide by 1000 for kg in display)
- `ml` → millilitres (divide by 1000 for L in display)

Check `items.uom` to know which unit applies.

### Useful timing columns

| Question | Columns to use |
|---|---|
| Quote creation → acceptance delay | `quotes.created_at` vs `quotes.accepted_at` |
| Quote creation → SO creation | `quotes.created_at` vs `sales_orders.created_at` |
| SO confirmed → production start | `sales_orders.created_at` vs `production_orders.started_at` |
| Production duration | `production_orders.started_at` vs `production_orders.completed_at` |
| Operation duration | `production_operations.started_at` vs `production_operations.completed_at` |
| Shipment transit time | `shipments.dispatched_at` vs `shipments.delivered_at` |
| Order-to-delivery | `sales_orders.created_at` vs `shipments.delivered_at` (join via `sales_order_shipments`) |
| Invoice payment delay | `invoices.issued_at` vs `invoices.paid_at` |

### Common query patterns

**Time differences** (SQLite lacks `DATEDIFF`; use julianday):
```sql
SELECT ROUND(julianday(accepted_at) - julianday(created_at), 2) AS days_to_accept
FROM quotes
WHERE accepted_at IS NOT NULL;
```

**Status distribution:**
```sql
SELECT status, COUNT(*) AS n FROM quotes GROUP BY status ORDER BY n DESC;
```

**Join SO → production → operations for end-to-end timing:**
```sql
SELECT so.id AS so_id,
       so.created_at AS so_created,
       po.started_at AS prod_start,
       po.completed_at AS prod_done,
       ROUND(julianday(po.completed_at) - julianday(so.created_at), 1) AS days_total
FROM sales_orders so
JOIN production_orders po ON po.sales_order_id = so.id
WHERE po.completed_at IS NOT NULL
LIMIT 20;
```

## When semantics are unclear

If the meaning of a column or status transition is not obvious from the schema, look into the corresponding service file in `services/` (e.g. `services/quote.py`, `services/production.py`). The scenario scripts in `scenarios/` also show the intended data-generation flow. Only do this when the schema alone doesn't answer the question.

