# Production Logic

How manufacturing orders (MOs) move through the system.

---

## Data Model

| Table | Purpose |
|---|---|
| `recipes` | Defines how to produce a finished item (output item, qty, production time) |
| `recipe_ingredients` | Bill of materials — input items and quantities per recipe |
| `recipe_operations` | Ordered steps to execute (name, duration, work center) |
| `work_centers` | Shared resources with a finite `max_concurrent` capacity |
| `production_orders` | MO header — links a recipe to a sales order |
| `production_operations` | Runtime copy of recipe operations for one MO, with actual timestamps |
| `production_wait_log` | Event-sourced history of every wait period (material or work-center) |

## Status Lifecycle

```
planned ─► waiting ─► ready ─► in_progress ─► completed
               ▲          │
               └──────────┘  (materials consumed → shortfall detected)
```

| Status | Meaning |
|---|---|
| `waiting` | Missing at least one ingredient; MO cannot start |
| `ready` | All materials available; can be started |
| `in_progress` | Materials deducted, operations are running |
| `completed` | All operations done, finished goods added to stock |

## Creating an MO (`create_order`)

1. Load the recipe and its ingredients.
2. Check stock availability for each ingredient.
3. If any ingredient is short → status = `waiting`; open a `production_wait_log` row with `reason_type = 'material'` referencing the primary shortage SKU.
4. If all available → status = `ready`.
5. Copy `recipe_operations` into `production_operations` (all `pending`).
6. Compute `eta_finish` / `eta_ship` from recipe `production_time_hours`.

One MO is created per batch of `output_qty`. If a sales order line needs more than one batch, multiple MOs are created.

## Starting an MO (`start_order`)

Called on MOs in `ready` status.

1. Re-check ingredient availability (stock may have changed since creation).
2. If shortfall found → revert to `waiting`, open material wait log, return early.
3. Deduct ingredients from stock (`inventory_service.deduct_stock`).
4. Close any open wait-log rows.
5. Set status = `in_progress`, record `started_at`.
6. Mark the first operation as `in_progress`.

## Operation Advancement (`advance_operations`)

Called by the simulation tick for every in-progress MO. Walks operations in `sequence_order`:

1. Compute each operation's expected start/end relative to `started_at` and cumulative `duration_hours`.
2. If `sim_time ≥ op_end` → mark `completed` with actual timestamps; close any open work-center wait for that op.
3. If `sim_time ≥ op_start` → check work-center capacity:
   - Count currently in-progress operations at that work center (excluding this MO).
   - If `used ≥ max_concurrent` → **blocked**. Open a `production_wait_log` row with `reason_type = 'work_center'`, set `blocked_reason` / `blocked_at` on the operation. All subsequent operations stay `pending`.
   - Otherwise → mark `in_progress`, close any prior work-center wait, reserve the slot.
4. If `sim_time < op_start` → stays `pending`.
5. Update `current_operation` on the MO header.

Returns `all_done = true` when every operation is completed.

## Completing an MO (`complete_order`)

1. Finalize any non-completed operations (spread timestamps proportionally across MO duration).
2. Close all remaining open wait-log rows.
3. Set status = `completed`, record `completed_at` and `qty_produced`.
4. Insert finished goods into `stock`.

## Manual Operation Completion (`complete_operation`)

Completes the current in-progress operation and advances to the next pending one. Does **not** auto-complete the MO — `complete_order` must be called separately to specify quantity and stock location.

## Wait-Reason Tracking

Wait periods are event-sourced in `production_wait_log`:

| Column | Description |
|---|---|
| `reason_type` | `material` or `work_center` |
| `reason_ref` | What is being waited for — ingredient SKU or work-center name |
| `started_at` | When the wait began |
| `resolved_at` | When it ended (`NULL` = still waiting) |
| `production_operation_id` | Set for work-center waits (ties to the blocked operation); `NULL` for material waits (MO-level) |

This design preserves full history — if an MO waited 5 days for PVC pellets, then started, we still see that wait in the timeline even after resolution.

Helpers:
- `_open_wait()` — inserts a new open row.
- `_close_open_waits()` — sets `resolved_at` on all open rows for an MO (or a specific operation).

## Readiness Promotion (`update_readiness`)

Periodically checks all `waiting` MOs. For each one, re-checks raw on-hand stock for every ingredient. If all available → promotes to `ready` and closes open material waits.

Uses raw stock (not reserved) to avoid circular deadlocks where every waiting MO's demand blocks every other.

## Simulation Side-Effects

When `advance_time(side_effects=True)` is called (typically once per simulated day):

1. **Tick operations** — calls `advance_operations` for every in-progress MO.
2. **Auto-complete** — if all operations are done, completes the MO and stocks the output.
3. **Safety net** — force-completes any in-progress MO past its `eta_finish` (handles edge cases like missing operation rows).
4. **Promote readiness** — runs `update_readiness` to move waiting → ready when materials become available (e.g. after a PO delivery or another MO's completion freed up stock).

## Timeline Visualization

Both sales orders and production orders expose a `/timeline` API endpoint that returns the full lifecycle as structured JSON. The frontend renders this as an SVG Gantt chart (`TimelineGantt` component) with:

- Color-coded bars per status
- Wait overlays (amber for material, red for work-center)
- Hover tooltips with dates and durations
- Click-through navigation to related entities
