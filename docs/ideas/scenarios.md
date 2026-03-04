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
  s02_halloween_spike.py  # ✅ Implemented — Halloween demand spike Oct 2025
  s03_material_shortage.py# ✅ Implemented — PVC supply disruption Nov 2025
  s04_geo_expansion.py    # ✅ Implemented — Germany expansion Dec 2025
  s05_price_revision.py   # ✅ Implemented — Price revision Jan 2026
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

The remaining four scenarios build on the s01 + s02 baseline.  Each receives a
`ctx` dict from the engine (containing `customer_ids`, `s01_so_ids`,
`core_skus`, `s02_so_ids`, `halloween_skus`, `costume_skus`, etc.) and can
pass data downstream to later scenarios.

### S02 — Halloween Spike (implemented)

**Period:** 2025-10-01 → 2025-10-31 (31 days), sim clock ends at 2025-11-02.

**Story:** Massive order surge for spooky-themed ducks. Production capacity
stressed, some orders ship late. Visible demand peak in charts.

**Design:**

- Halloween SKU pool weighted 4× (Witch, Pumpkin, Vampire, Ghost, Frankenstein,
  Zombie), Costume SKUs 3× (Ninja, Pirate), core SKUs 1× baseline.
- Weekly volume ramp: W1 (4,6) → W2 (5,8) → W3 (6,9) → W4 (6,8) → W5 (4,6).
- Qty per line: 8–30 (higher than S01's 5–25) to stress materials faster.
- **Restock cutoff at day 21 (Oct 22):** no more material POs after this point,
  causing raw material depletion and MOs stuck in `waiting`.
- Late-October orders naturally won't complete before month end.
- Post-loop: 10 customer inquiry emails ("Where is my order?") linked to
  delayed SOs still in `confirmed` status.
- 1-day settle only (preserves backlog for S03).
- Returns `s02_so_ids`, `halloween_skus`, `costume_skus` in ctx.

**Actual volumes after s01 + s02 (latest run):**

| Entity | Count | Status breakdown |
|--------|-------|------------------|
| Sales Orders | 377 | 275 completed, 102 confirmed |
| Production Orders | 1 335 | 901 completed, 425 waiting, 9 other |
| Purchase Orders | 402 | 402 received |
| Invoices | 275 | 202 paid, 33 issued, 37 overdue, 3 draft |
| Quotes | 392 | 377 accepted, 9 sent, 6 rejected |
| Shipments | 279 | 270 delivered, 5 in_transit, 4 planned |
| Emails | 20 | 10 from S01 + 10 inquiry emails from S02 |
| Payments | 202 | — |

**S02 delta:** +201 SOs, +804 MOs, +133 POs, +115 invoices, +201 quotes,
+118 shipments, +10 emails, +80 payments.

### S03 — Material Shortage (implemented)

**Period:** 2025-11-01 → 2025-11-30 (30 days), sim clock ends at 2025-12-03.

**Story:** PlasticCorp (SUP-001) PVC delivery delays (+3 weeks).  Production
orders pile up in `waiting`.  Expedited POs placed with EuroPlast GmbH
(SUP-004) and DuraPoly Industries (SUP-009).  Customer complaint emails.
Visible production dip in charts.

**Design:**

- Supply disruption applied on days 1, 8, and 15 via
  `create_supply_disruption("PVC-PELLETS", 21)` — catches newly-created
  restock POs to SUP-001 each week (ongoing disruption, not one-shot).
- Normal demand continues at s01 baseline: (2,3) orders/day across all weeks,
  core SKU pool only (Halloween season is over).
- 6 expedited POs placed on days 3, 6, 9, 13, 17, 21 alternating between
  EuroPlast GmbH (12-day lead) and DuraPoly Industries (14-day lead),
  500 000 g PVC each.
- Restocking runs throughout — PVC POs to SUP-001 keep getting created and
  delayed, realistically modelling a procurement system unaware of the
  disruption.
- Mid-month: first expedited POs arrive (~day 14–15), partially unblocking
  production.  `waiting` MO count peaks then gradually recovers.
- Post-loop: 12 customer complaint emails about delays and material shortages,
  drawn from both s03 and s02 backlog SOs still in `confirmed`.
- 2-day settle (lets some in-flight expedited POs arrive).
- Returns `s03_so_ids`, `disruption_material` in ctx.

**Actual volumes after s01 + s02 + s03 (latest run):**

| Entity | Count | Status breakdown |
|--------|-------|------------------|
| Sales Orders | 454 | 365 completed, 84 confirmed, 5 other |
| Production Orders | 1 651 | 1 241 completed, 120 waiting, 279 ready, 11 other |
| Purchase Orders | 572 | 536 received, 36 ordered (incl. 5 delayed PVC) |
| Invoices | 370 | 265 paid, 34 issued, 69 overdue, 2 other |
| Quotes | 469 | 454 accepted, 9 sent, 6 rejected |
| Shipments | 376 | 354 delivered, 11 in_transit, 6 planned, 5 other |
| Emails | 32 | 10 (S01) + 10 (S02) + 12 (S03 complaints) |
| Payments | 265 | — |

**S03 delta:** +77 SOs, +316 MOs, +170 POs (incl. 6 expedited), +95 invoices,
+77 quotes, +97 shipments, +12 emails, +63 payments.

### S04 — Geo Expansion (Germany)  ✅ Implemented

**Period:** 2025-12-01 → 2025-12-31 (31 days), sim clock ends at 2026-01-03.

**Story:** Duck Inc expands into Germany.  12 new German customers, Lederhosen
+ Oktoberfest ducks promoted (4× weighted), Christmas seasonal push (Santa,
Snowman, Reindeer, Elf, Gingerbread — 3× weighted) in both FR and DE markets.
Cross-border shipments visible in logistics data.  Supply chain runs normally
(PVC restored post-S03) — contrast with November dip.

**Design:**

- 12 German customers via `create_customer_batch(12, country="DE",
  payment_terms_choices=[45, 60])`.
- Two parallel daily order streams: French (Christmas pool) + German
  (German + Christmas pool) with separate weekly volume ramps.
- FR weekly: W1 (2,3), W2 (2,4), W3 (3,5), W4 (3,4), W5 (2,3).
- DE weekly: W1 (1,2), W2 (2,3), W3 (2,4), W4 (2,3), W5 (1,2).
- German orders placed at 11:00 (FR at 10:00) for timestamp differentiation.
- Materials restock normally throughout (restored supply chain).
- Post-loop: 8 welcome/onboarding emails to DE customers (mix of German
  and English), 8 Christmas inquiry emails (FR+DE), 10 standalone quotes
  (5 DE, 5 FR — ~30% rejected).
- 2-day settle.
- Returns `s04_so_ids`, `de_customer_ids`, `customer_ids` (merged),
  `german_skus`, `christmas_skus` in ctx.

**Actual volumes after s01 + s02 + s03 + s04 (latest run):**

| Entity | Count | Status breakdown |
|--------|-------|------------------|
| Customers | 42 | 30 FR + 12 DE |
| Sales Orders | 625 | 493 completed, 132 confirmed |
| Production Orders | 2 287 | ~1 700 completed, ~508 waiting, rest other |
| Purchase Orders | 780 | ~730 received, ~50 ordered |
| Invoices | 493 | 357 paid, ~30 issued, ~102 overdue, rest other |
| Quotes | 650 | ~625 accepted, ~15 sent, ~10 rejected |
| Shipments | 500 | ~480 delivered, rest in_transit/planned |
| Emails | 48 | 10 (S01) + 10 (S02) + 12 (S03) + 16 (S04) |
| Payments | 357 | — |

**S04 delta:** +171 SOs (100 FR + 71 DE), +636 MOs, +208 POs, +123 invoices,
+181 quotes, +124 shipments, +16 emails, +92 payments, +12 DE customers.

### S05 — Price Revision  ✅ Implemented

**Period:** 2026-01-01 → 2026-01-15 (15 days), sim clock ends at 2026-01-17.

**Story:** Duck Inc raises prices by 8 % on all finished goods effective
1 January 2026.  Pre-existing quotes still in the pipeline carry old (lower)
prices — some get accepted, creating a visible margin dip.  New quotes at the
new prices see a 40 % rejection rate (vs. normal 30 %).  Order volume drops in
Week 1 ("price shock"), then partially recovers in Week 2.  Customer complaint
emails about the increase add to the narrative.

**Design:**

- Phase 0: `UPDATE items SET unit_price = ROUND(unit_price * 1.08, 2)
  WHERE type = 'finished_good'` — bulk 8 % increase on all 37 FGs.
- Accept ~65 % of pre-existing `sent` quotes at their frozen old prices → SOs
  at old prices (margin dip visible in analytics).  Remaining ~35 % rejected.
- 6 price-announcement emails to random customers (FR + DE, mix of languages).
- Two parallel order streams (FR + DE) with reduced weekly volumes:
  - FR: W1 (1,2), W2 (2,3), W3 (2,3).
  - DE: W1 (0,1), W2 (1,2), W3 (1,2).
- SKU pool: core (1×) + Christmas (1×, de-weighted from S04's 3×) + German (2×
  for DE stream).  Qty per line: (5,20) — lower than baseline.
- Post-loop: 16 new quotes at new prices (8 FR + 8 DE) with 40 % rejection
  rate — reasons cite the price increase explicitly.
- 10 customer complaint emails about the increase (FR + DE, referencing recent
  SOs where possible).
- 1-day settle.
- Returns `s05_so_ids`, `old_prices`, `price_increase_pct`,
  `s05_sent_quotes` in ctx.

**Actual volumes after s01 + s02 + s03 + s04 + s05 (latest run):**

| Entity | Count | Status breakdown |
|--------|-------|------------------|
| Customers | 42 | 30 FR + 12 DE |
| Sales Orders | 675 | 550 completed, 125 confirmed |
| Production Orders | 2 429 | ~1 970 completed, ~371 waiting, rest other |
| Purchase Orders | 880 | ~830 received, ~50 ordered |
| Invoices | 550 | 403 paid, ~34 issued, ~112 overdue, rest other |
| Quotes | 711 | ~675 accepted, ~16 sent, ~20 rejected |
| Shipments | 558 | ~546 delivered, rest in_transit/planned |
| Emails | 64 | 10 (S01) + 10 (S02) + 12 (S03) + 16 (S04) + 16 (S05) |
| Payments | 403 | — |

**S05 delta:** +50 SOs (5 old-price + 31 FR + 14 DE), +142 MOs, +100 POs,
+57 invoices, +61 quotes (16 new-price + rest from SO flow), +58 shipments,
+16 emails (6 announcements + 10 complaints), +46 payments.

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

| Entity | Target | After s01 | After s02 |
|--------|--------|-----------|-----------|
| Customers | 60–80 | 30 | 30 |
| Items | 50 | 50 (stable) | 50 |
| Sales Orders | 500–700 | 176 | 377 |
| Production Orders | 1 000–1 500 | 531 | 1 335 |
| Purchase Orders | 350–500 | 269 | 402 |
| Invoices | 400–600 | 160 | 275 |
| Quotes | 250–400 | 191 | 392 |
| Shipments | 400–600 | 161 | 279 |
| Emails | 40–60 | 10 | 20 |

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
