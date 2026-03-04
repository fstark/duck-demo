# Story-Driven Demo Data Generator — Plan

## Goal

Generate a single, rich demo dataset containing multiple interwoven business
stories (Halloween demand spike, material shortage, geographical expansion,
price revision, etc.).  Each story contributes its slice of the narrative to
**one shared database**, so charts and analytics reveal trends and incidents
over time.

The data is regenerable on demand: `python -m scenarios --only s01`.

---

## What Has Been Built (done)

### Service Layer Enhancements

All prerequisite service-layer gaps identified in the original plan have been
resolved.  The following capabilities now exist:

| Capability | Where |
|------------|-------|
| Sim-time-aware `create_order` (production & purchase) | `services/production.py`, `services/purchase.py` |
| `SalesService.confirm_order()` — `draft → confirmed` | `services/sales.py` |
| `SalesService.complete_order()` — `confirmed → completed` | `services/sales.py` |
| `LogisticsService.dispatch_shipment()` — `planned → in_transit`, deducts stock | `services/logistics.py` |
| `LogisticsService.deliver_shipment()` — `in_transit → delivered` | `services/logistics.py` |
| `ProductionService.update_readiness()` — `waiting → ready` when materials arrive | `services/production.py` |
| Raw material consumption on `start_order()` with fallback to `waiting` if short | `services/production.py` |
| `InventoryService.deduct_stock()` — FIFO stock deduction with audit trail | `services/inventory.py` |
| `SimulationService.advance_time(side_effects=True)` — 5 side-effects (see below) | `services/simulation.py` |
| `PurchaseService.restock_materials()` accepts `raw_material`, `component`, `material` | `services/purchase.py` |
| Recipes for **all 37** finished goods (was 6) | `scenarios/base_setup.py` |

**Side-effects on `advance_time`:**

1. Mark overdue invoices
2. Auto-complete in-progress MOs (operation ticking + `eta_finish` safety net)
3. Auto-deliver shipments past `planned_arrival`
4. Expire sent quotes past `valid_until`
5. Promote `waiting → ready` MOs when materials become available

### New Orchestration Services

Two higher-level services were added to coordinate the daily factory rhythm:

- **`FulfillmentService`** (`services/fulfillment.py`) —
  `start_ready_mos()`, `receive_due_pos(date)`, `ship_ready_orders(so_ids)`,
  `invoice_shipped_orders(so_ids)`.
- **`MrpService`** (`services/mrp.py`) —
  `replan_unfulfilled_orders()` — net requirements planning across all confirmed
  unshipped SOs; creates MOs for shortages, auto-starts ready ones.

### Scenario Framework

```
scenarios/
  __init__.py
  __main__.py             # CLI entry point
  engine.py               # Orchestrator: reset DB → base_setup → run scenarios
  helpers.py              # Reusable story primitives
  base_setup.py           # Foundation data (catalog, suppliers, recipes, customers)
  s01_steady_state.py     # ✅ Implemented — Normal operations Aug–Sep 2025
  s02_halloween_spike.py  # 🔲 Not yet implemented
  s03_material_shortage.py# 🔲 Not yet implemented
  s04_geo_expansion.py    # 🔲 Not yet implemented
  s05_price_revision.py   # 🔲 Not yet implemented
  s06_new_year_recovery.py# 🔲 Not yet implemented
```

**`engine.py`** — Deletes and recreates the DB from `schema.sql` (no seed_demo),
inserts a `simulation_state` row, runs `base_setup.populate()`, then executes
selected scenario modules in order.  Prints a summary table at the end.
CLI: `python -m scenarios` or `python -m scenarios --only s01`.

**`base_setup.py`** — Sets simulation clock to `2025-08-01 08:00`.  Inserts:

| Data | Count |
|------|-------|
| Raw materials | 13 (PVC, 8 dyes, boxes, foam, gloss paint) |
| Finished goods | 37 (22 core + 15 seasonal/expansion ducks) |
| Suppliers | 10 (FR + DE) |
| Recipes | 37 (one per finished good, with ingredients + operations) |
| Work centers | per `config.WORK_CENTER_CAPACITY` |
| Initial RM stock | 13 rows (generous starting quantities) |
| Customers | 30 (all French, mix of B2B/B2C, various payment terms) |

**`helpers.py`** — Implemented primitives:

| Helper | Purpose |
|--------|---------|
| `advance_and_settle(days, hours)` | Advance sim time with side-effects |
| `set_day_time(hour)` | Intra-day clock positioning (no side-effects) |
| `run_full_sales_cycle(...)` | Quote → SO → produce → ship → invoice → pay |
| `create_sales_order_only(...)` | Quote → accept → confirm SO (no fulfillment) |
| `create_quote_only(...)` | Create + optionally send a standalone quote |
| `trigger_production_for_orders(so_ids)` | MOs for shortages only (net of stock) |
| `create_customer_batch(count, country)` | Bulk customer creation (FR or DE) |
| `create_demand_burst(...)` | Scatter orders across a time window |
| `create_supply_disruption(material_sku, delay_days)` | Delay open POs for a material |
| `restock_materials()` | Auto-reorder materials below reorder point |
| `send_email(...)` | Create + send an email |
| `pick_random_lines(sku_pool, ...)` | Random order line builder |
| `get_customer_ship_to(cust_id)` | Address lookup with fallback defaults |

### S01 — Steady State (implemented)

**Period:** 2025-08-01 → 2025-09-30 (61 days), sim clock ends at 2025-10-03.

**Daily rhythm** (one connection per day):

| Time | Action |
|------|--------|
| 08:00 | Receive due POs; start ready MOs; MRP re-plan; restock if new MOs |
| 10:00 | Create 2–4 confirmed SOs (quote→accept→confirm); trigger production |
| 14:00 | Ship ready orders; restock materials |
| 16:00 | Invoice shipped orders; record payments; complete SOs |
| 18:00 | Advance clock 14 h → next 08:00 (side-effects fire) |

Orders use a 22-SKU core pool (6 top-sellers weighted 3×).  Volume ramps
from 2–3/day in early August to 3–4/day in late August, then eases back.

After the daily loop: 15 standalone quotes (30% rejected), 10 sample emails,
and a 2-day final settle for in-flight deliveries.

**Actual volumes after s01 (latest run):**

| Entity | Count | Status breakdown |
|--------|-------|-----------------|
| Customers | 30 | — |
| Items | 50 | 13 RM + 37 FG |
| Recipes | 37 | — |
| Sales Orders | 176 | 160 completed, 16 confirmed |
| Production Orders | 531 | 490 completed, 41 waiting |
| Purchase Orders | 269 | 231 received, 38 ordered |
| Invoices | 160 | 122 paid, 22 issued, 16 overdue |
| Quotes | 191 | 176 accepted, 9 sent, 6 rejected |
| Shipments | 161 | 160 delivered, 1 planned |
| Emails | 10 | — |
| Payments | 122 | — |
| Activity log | ~4 350 | — |
| Stock movements | ~3 620 | — |

---

## Scenarios To Implement

The remaining five scenarios build on the s01 baseline.  Each receives a `ctx`
dict from the engine (containing `customer_ids`, `s01_so_ids`, `core_skus`, etc.)
and can pass data downstream to later scenarios.

### S02 — Halloween Spike

| | |
|---|---|
| **Period** | Oct 2025 (sim clock: 2025-10-01 → 2025-10-31) |
| **Story** | Massive order surge for spooky-themed ducks.  Production capacity stressed, some orders ship late. Visible demand peak in charts. |
| **Key actions** | • Demand burst on Halloween SKUs (Witch, Pumpkin, Vampire, Ghost, Frankenstein, Zombie) at 2–3× normal volume<br>• Ninja + Pirate orders also spike (costume season)<br>• Some MOs stuck in `waiting` due to material consumption outpacing restocking<br>• A few late shipments (orders placed late October won't complete before month end)<br>• Customer emails: "When will my order ship?" |
| **Expected additions** | ~100–150 SOs, ~300–400 MOs, visible spike in all charts |
| **Helpers to use** | `create_demand_burst()`, `trigger_production_for_orders()`, `restock_materials()`, `send_email()` |

### S03 — Material Shortage

| | |
|---|---|
| **Period** | Nov 2025 (sim clock: 2025-11-01 → 2025-11-30) |
| **Story** | PlasticCorp (SUP-001) PVC delivery delays (+3 weeks).  Production orders pile up in `waiting`.  Expedited POs placed with EuroPlast GmbH (SUP-004) or DuraPoly (SUP-009) at higher cost.  Customer complaint emails. Visible production dip. |
| **Key actions** | • `create_supply_disruption("PVC-PELLETS", 21)` on existing POs<br>• Normal order volume continues (demand doesn't stop)<br>• MOs accumulate in `waiting` status — chart shows production dip<br>• Expedited POs to alternate suppliers with shorter lead times<br>• Customer complaint emails about delays<br>• Mid-month: partial PVC delivery arrives, some MOs unblock |
| **Expected additions** | ~60–80 SOs, high `waiting` MO count, 5–10 expedited POs, complaint emails |
| **Helpers to use** | `create_supply_disruption()`, `create_demand_burst()`, `send_email()` |

### S04 — Geo Expansion (Germany)

| | |
|---|---|
| **Period** | Dec 2025 (sim clock: 2025-12-01 → 2025-12-31) |
| **Story** | Duck Inc expands into Germany.  New customers, Lederhosen + Oktoberfest ducks promoted, cross-border shipments.  Christmas season overlap drives volume. |
| **Key actions** | • `create_customer_batch(12, country="DE")` — new German customers<br>• Demand burst on Lederhosen, Oktoberfest + Christmas SKUs (Santa, Snowman, Reindeer, Elf, Gingerbread)<br>• German customers get `payment_terms=60`<br>• Cross-border shipments (country="DE" in ship_to)<br>• Some French Christmas orders too<br>• New revenue stream visible by country in analytics |
| **Expected additions** | ~12 DE customers, ~80–120 SOs, seasonal SKU mix shift |
| **Helpers to use** | `create_customer_batch()`, `create_demand_burst()`, `run_full_sales_cycle()` |

### S05 — Price Revision

| | |
|---|---|
| **Period** | Jan 2026 (sim clock: 2026-01-01 → 2026-01-15) |
| **Story** | 8% price increase across the board.  Old quotes still in pipeline at old prices (some get accepted — margin dip).  New quotes at new prices — some customers reject. Before/after visible in pricing data. |
| **Key actions** | • UPDATE item prices +8% on all finished goods<br>• Accept a handful of pre-existing sent quotes (still at old prices)<br>• Create new quotes at new prices — ~30% rejection rate<br>• Some customers send complaint emails about prices<br>• Reduced order volume in the first week (price shock) |
| **Expected additions** | ~30–50 SOs, ~20–30 new quotes, price-change visible in line-item data |
| **Helpers to use** | `create_quote_only()`, `create_sales_order_only()`, `send_email()` |

### S06 — New Year Recovery

| | |
|---|---|
| **Period** | Jan – Feb 2026 (sim clock: 2026-01-16 → 2026-02-28) |
| **Story** | Operations normalize.  Material supply fully restored.  Production backlog clears.  Overdue invoices get paid.  System reaches a healthy current state suitable for live demo. |
| **Key actions** | • Normal order volume resumes (~2–3/day)<br>• All `waiting` MOs get unblocked (materials arrive)<br>• Overdue invoices from previous months get paid<br>• Final settle: advance to end of Feb, let side-effects clear everything<br>• Database in clean, demo-ready state |
| **Expected additions** | ~60–80 SOs, backlog clearance, payment catch-up |
| **Helpers to use** | `advance_and_settle()`, `create_demand_burst()` |

---

## Volume Targets (all 6 scenarios combined)

| Entity | Target | After s01 |
|--------|--------|-----------|
| Customers | 60–80 | 30 |
| Items | 50 | 50 (stable) |
| Sales Orders | 500–700 | 176 |
| Production Orders | 1 000–1 500 | 531 |
| Purchase Orders | 350–500 | 269 |
| Invoices | 400–600 | 160 |
| Quotes | 250–400 | 191 |
| Shipments | 400–600 | 161 |
| Emails | 40–60 | 10 |

---

## Verification

- `python -m scenarios` → check entity counts + final sim time in summary table
- No orphaned references (SO → non-existent customer, etc.)
- Charts show visible patterns: Oct spike, Nov dip, Dec new-region revenue, Jan price jump
- Spot-check full lifecycle: random SO → quote → order → production → shipment → invoice → payment
- Status distributions make sense (mostly completed, a tail of in-progress/waiting)

---

## Key Decisions

- **Single database, additive scenarios** — chronologically ordered, run in sequence
- **Service layer only** — all data flows through services, no raw SQL in scenarios
- **`seed_demo.py` is deprecated** — `base_setup.py` replaces it entirely
- **Side-effects on `advance_time`** — automatic MO completion, shipment delivery,
  quote expiry, readiness promotion, overdue invoice marking
- **MRP net planning** — production orders only created for net shortfall (demand
  minus on-hand), preventing unbounded stock growth
- **Daily rhythm** — each sim day follows a realistic factory schedule (receive →
  produce → sell → ship → invoice → advance)
