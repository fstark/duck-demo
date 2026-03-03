# Story-Driven Demo Data Generator — Plan

## Goal

Develop a framework to generate a single, rich demo dataset containing multiple
interwoven business stories (Halloween demand spike, material shortage, geographical
expansion, price revision, etc.).  Each story contributes its slice of the narrative
to **one shared database**, so charts and analytics reveal trends and incidents over
time.

The data must be regenerable on demand as stories are revised.

---

## Current State

`seed_demo.py` is ~600 lines of **raw SQL** with hardcoded IDs and no temporal
progression.  It creates a small, static snapshot (17 customers, 26 items, 2 sales
orders, 48 production orders, etc.) pinned to a single moment (`2025-12-24 08:30`).
It bypasses the service layer entirely, so nothing validates business logic.  There
is **no narrative arc** — no seasonality, no trends, no incidents.

Meanwhile, a rich service layer already exists (`SalesService.create_order()`,
`ProductionService.create_order()`, `QuoteService.create_quote()`,
`InvoiceService.create_invoice()`, etc.) and a simulation clock
(`SimulationService.advance_time()`) — but neither is used for seeding.

---

## Approach — A+B Hybrid

**Phase 1 (now):** Python scenario scripts that call the service layer directly while
advancing simulated time.  Quick to build, full control, validates business logic.

**Phase 2 (later):** Optional YAML DSL front-end for non-developer authoring, backed
by the same Python engine.

---

## Prerequisites — Service Layer Gaps to Fix

These are blocking issues that prevent scenario scripts from driving realistic
end-to-end flows:

| # | Gap | Where |
|---|-----|-------|
| 1 | `ProductionService.create_order()` uses `datetime.utcnow()` instead of sim time for `eta_finish` / `eta_ship` | `services/production.py` |
| 2 | `PurchaseService.create_order()` uses `datetime.utcnow()` instead of sim time for `expected_delivery` | `services/purchase.py` |
| 3 | No `SalesService.confirm_order(so_id)` — can't transition `draft` → `confirmed` | `services/sales.py` |
| 4 | No `SalesService.complete_order(so_id)` — can't close an order | `services/sales.py` |
| 5 | No `LogisticsService.dispatch_shipment(ship_id)` — `planned` → `in_transit` with stock deduction | `services/logistics.py` |
| 6 | No `LogisticsService.deliver_shipment(ship_id)` — `in_transit` → `delivered` | `services/logistics.py` |
| 7 | No `ProductionService.update_readiness()` — batch `waiting` → `ready` when materials become available | `services/production.py` |
| 8 | Item type mismatch: seed uses `type='material'` but `PurchaseService.restock_materials()` checks for `'raw_material'`/`'component'` | `seed_demo.py` / `services/purchase.py` |
| 9 | No raw material consumption when `ProductionService.start_order()` fires | `services/production.py` |
| 10 | `advance_time()` only marks overdue invoices — no other side-effects | `services/simulation.py` |
| 11 | Stock is append-only (INSERT new rows), never deducted — no stock decrease path at all | `services/inventory.py` |
| 12 | Many finished goods have no recipe defined (only 6 of 22) | `seed_demo.py` |

---

## Step 1 — Enhance `SimulationService.advance_time()` with Side-Effects

Add a configurable set of side-effects triggered on each time advance
(`side_effects=True` by default):

- **Complete production orders** whose `eta_finish <= new_time` and status is
  `in_progress`
- **Deliver shipments** whose `planned_arrival <= new_time` and status is
  `in_transit`
- **Expire quotes** whose `valid_until < new_time` and status is `sent`
- **Refresh production readiness** — `waiting` → `ready` when materials available
- **Mark overdue invoices** (already exists)

---

## Step 2 — Build the Scenario Framework

### Directory Structure

```
scenarios/
  __init__.py
  engine.py              # Orchestrator: reset DB, load base, run selected scenarios
  helpers.py             # Shared utilities (batch creation, lifecycle helpers)
  base_setup.py          # Foundation: catalog, suppliers, recipes, starting clock
  s01_steady_state.py    # Normal operations Aug–Sep 2025
  s02_halloween_spike.py # October duck rush
  s03_material_shortage.py # PVC supply disruption Nov 2025
  s04_geo_expansion.py   # New region (Germany) Dec 2025
  s05_price_revision.py  # January 2026 price list update
  s06_new_year_recovery.py # Recovery Jan–Feb 2026
```

### `engine.py` — Orchestrator

- Accepts a list of scenario modules (default: all, in order)
- Calls `AdminService.reset_database()` to start fresh
- Runs `base_setup.py` first (sets simulation clock to `2025-08-01`)
- Runs each scenario in chronological order; each advances sim time as needed
- Prints summary: entity counts, final sim time, story highlights
- CLI: `python -m scenarios.engine` or `python -m scenarios.engine --only s02,s03`

### `base_setup.py` — Foundation Layer

Expands catalog and standing data:

- ~40–50 finished goods (seasonal/themed ducks: Witch, Pumpkin, Santa, Lederhosen…)
- ~10 raw materials (dye colors, PVC grades, packaging variants)
- ~8–10 suppliers (including German ones for geo expansion)
- Recipes for all finished goods
- ~30–50 customers across France
- Sensible `reorder_qty` on materials
- Simulation clock set to **2025-08-01**

### `helpers.py` — Reusable Story Primitives

High-level functions chaining service calls:

- `run_full_sales_cycle(customer_id, lines, advance_days=...)` —
  quote → accept → confirm SO → production → complete → ship → invoice → pay
- `create_customer_batch(count, region, name_pattern)` — bulk creation
- `create_demand_burst(sku_list, qty_range, customer_pool, over_days)` — scatter orders
- `create_supply_disruption(material_sku, delay_days)` — delay POs, block production
- `advance_and_settle(days)` — advance time + let side-effects process

### Individual Scenarios

| Scenario | Period | Story |
|----------|--------|-------|
| **s01 — Steady State** | Aug – Sep 2025 | ~100–200 orders at normal pace across French customers. Establishes baseline for charts. |
| **s02 — Halloween Spike** | Oct 2025 | Massive Ninja + Pirate orders. New Witch/Pumpkin ducks. Production ramps up, some orders late. Visible demand peak. |
| **s03 — Material Shortage** | Nov 2025 | PVC delays from PlasticCorp (+3 weeks). Production orders stuck in `waiting`. Expedited POs at higher cost. Customer complaint emails. Visible production dip. |
| **s04 — Geo Expansion** | Dec 2025 | 10–15 new German customers. "Lederhosen Duck" launched. Cross-border shipments. Net-60 payment terms. New revenue stream in analytics. |
| **s05 — Price Revision** | Jan 2026 | 8% price increase. Old quotes still in pipeline at old prices. Some customers reject new quotes. Before/after visible in pricing data. |
| **s06 — Recovery** | Jan – Feb 2026 | Demand normalizes. Material supply resumes. Backlog clears. Overdue invoices paid. Healthy current state for live demo. |

---

## Step 3 — Volume Calibration

Target per-entity volumes after all scenarios (approximate):

| Entity | Target | Source |
|--------|--------|--------|
| Customers | 60–80 | Base + German expansion |
| Items | 50–60 | Expanded catalog + seasonal |
| Sales Orders | 400–600 | Steady state + spikes |
| Production Orders | 500–800 | Following demand |
| Purchase Orders | 100–150 | Material restocking |
| Invoices | 300–500 | Following completed sales |
| Quotes | 150–250 | Including rejected/revised |
| Shipments | 300–500 | Following confirmed orders |
| Emails | 30–50 | Complaints, confirmations |

Adjustable via parameters in each scenario.

---

## Step 4 — (Future) YAML Front-End

Once the Python framework is stable (3+ working scenarios):

- YAML files reference `helpers.py` primitives by name
- Interpreter resolves `$ref` variables, calls Python functions
- Non-developers can tweak timelines, quantities, customer names
- Phase 2 — don't build until pattern is proven

---

## Verification

- `python -m scenarios.engine` → check entity counts, final sim time
- No orphaned references (SO → non-existent customer, etc.)
- Charts show visible patterns: Oct spike, Nov dip, Dec new-region revenue, Jan price jump
- Existing demo scripts from `Kick-off-demo.md` still work against generated dataset
- Spot-check full lifecycle chains: random SO → quote → order → production → shipment → invoice → payment

---

## Key Decisions

- **Single database, additive scenarios** — chronologically ordered, run in sequence
- **Service layer first** — fix gaps before building scenarios (no raw SQL fallback)
- **`seed_demo.py` phased out** — `base_setup.py` replaces it; keep as fallback, mark deprecated
- **Side-effects on `advance_time`** — automatic production completions, deliveries,
  quote expiry, readiness checks
