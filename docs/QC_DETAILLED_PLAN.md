# QC Detailled Implementation Plan

## Purpose

This document turns the high-level plan from `docs/QC_PLAN.md` into an execution playbook with:

- explicit implementation checklist items,
- concrete file-level touchpoints in the current codebase,
- step-by-step test additions,
- validation commands for each milestone.

It is designed so implementation can be done in small PRs without ambiguity.

---

## 0. Pre-Flight Checklist (Do This First)

- [ ] Re-read constraints and decisions:
  - [ ] `docs/QC_DESIGN.md`
  - [ ] `docs/QC.md`
  - [ ] `docs/CODING.md`
- [ ] Verify dev environment:
  - [ ] `source venv/bin/activate`
  - [ ] `pip install -r requirements.txt`
  - [ ] `cd ui && npm install && cd ..`
- [ ] Baseline test pass before changes:
  - [ ] `pytest -q`
- [ ] Baseline data generation works:
  - [ ] `python -m scenarios --only s01`
- [ ] Confirm no QC-specific tables currently exist in `schema.sql` (expected starting state).

---

## 1. Existing Code Map (Where To Implement)

### Core backend domain/services

- Production lifecycle and completion:
  - `services/production.py`
- Stock summary/availability and reservation math:
  - `services/inventory.py`
- Shipping eligibility behavior in scenario flows:
  - `services/fulfillment.py`
- Shared DB lifecycle:
  - `db.py`
- MyForterro API integration layer:
  - `services/myforterro.py`
- Constants and no-magic-values location codes:
  - `config.py`

### MCP tools and registration

- MCP tool module registration:
  - `mcp_tools/__init__.py`
- Tool logging/activity mapping and confirmation helpers:
  - `mcp_tools/_common.py`
- Confirmation dispatcher for mutating tools:
  - `mcp_tools/confirm_tools.py`
- Existing production tool style reference:
  - `mcp_tools/production_tools.py`

### REST routes and UI data flow

- REST route registration:
  - `api_routes/__init__.py`
- Production REST route style reference:
  - `api_routes/production_routes.py`
- MCP app resource registration:
  - `server.py`
- UI API client wiring:
  - `ui/src/api.ts`
- UI app routing/nav structure:
  - `ui/src/App.tsx`

### Scenario and simulation

- Main steady-state scenario loop:
  - `scenarios/s01_steady_state.py`
- Shared scenario helper primitives:
  - `scenarios/helpers.py`

### Test structure references

- REST contract style:
  - `tests/test_rest_production.py`
- MCP contract style:
  - `tests/test_mcp_production.py`
  - `tests/test_mcp_shared.py`
- Shared fixtures:
  - `tests/conftest.py`

---

## 2. Implementation Plan By Milestone

## Milestone A - Domain + Schema + Hold Routing

### Step A1 - Freeze Domain Contract in Code

Goal: Encode allowed states/actions centrally and use them consistently.

Implementation checklist:

- [ ] Add QC state/action constants (single source of truth). Use module:
  - [ ] `services/qc.py`
- [ ] **Service class structure**: follow the existing pattern — define `class QcService` with all QC methods as instance methods, and create a module-level singleton `qc_service = QcService()`. This is what gets imported everywhere.
- [ ] **ID generation prefixes**: use `generate_id(conn, PREFIX, table)` with these prefixes so IDs are human-readable and debuggable:
  | Table | Prefix | Example |
  |---|---|---|
  | `qc_hold_batches` | `QCB` | `QCB-0001` |
  | `qc_hold_batch_lines` | `QCBL` | `QCBL-0001` |
  | `qc_hold_images` | `QCIMG` | `QCIMG-0001` |
  | `qc_inspections` | `QCI` | `QCI-0001` |
  | `qc_inspection_findings` | `QCIF` | `QCIF-0001` |
  | `qc_dispositions` | `QCD` | `QCD-0001` |
  | `qc_replacements` | `QCRPL` | `QCRPL-0001` |
- [ ] Register `qc_service` singleton in `services/__init__.py` following the existing pattern (add `from services.qc import qc_service, QcService` and include both in `__all__`).
- [ ] Define allowed values:
  - [ ] `inspection_status`: `none`, `pending_inspection`, `inspected`, `partially_released`, `released`
  - [ ] hold batch `status`: `pending_images`, `ready_for_inspection`, `inspected`, `released`, `partially_released`, `closed`
  - [ ] hold line `line_status`: `pending_inspection`, `released`, `partially_released`, `scrapped`
  - [ ] disposition actions: `pass_release`, `partial_scrap`, `full_scrap`
- [ ] Add invariant helper:
  - [ ] `qty_released + qty_scrapped + qty_pending == qty_on_hold`
- [ ] Add transition validation helper(s), table-driven.

Tests to add:

- [ ] `tests/test_qc_domain_states.py`
  - [ ] valid transitions pass
  - [ ] invalid transitions raise explicit error
- [ ] `tests/test_qc_domain_invariants.py`
  - [ ] invariant holds on all action paths

Validation command:

- [ ] `pytest -q tests/test_qc_domain_states.py tests/test_qc_domain_invariants.py`

---

### Step A2 - Add Schema + Indexes + Config Constants

Goal: Create persistent model described in `docs/QC_DESIGN.md`.

Implementation checklist:

- [ ] Update `schema.sql`:
  - [ ] extend `production_orders` with:
    - `inspection_required INTEGER NOT NULL DEFAULT 0`
    - `inspection_status TEXT NOT NULL DEFAULT 'none'` (not NULL; `'none'` is the default for all rows)
  - [ ] create `qc_hold_batches`
  - [ ] create `qc_hold_batch_lines`
  - [ ] create `qc_hold_images`
  - [ ] create `qc_inspections`
  - [ ] create `qc_inspection_findings`
  - [ ] create `qc_dispositions`
  - [ ] create `qc_replacements`
  - [ ] add indexes listed in design
- [ ] Make `stock_movements.stock_id` nullable in `schema.sql`: change `stock_id TEXT NOT NULL` to `stock_id TEXT`. QC scrap movements have no associated `stock` row (scrap is disposed, not a stock location). All existing non-QC code always supplies a `stock_id`, so this change is backward-compatible.
- [ ] Extend stock movement allowed conventions in code paths to include:
  - [ ] `qc_hold_release`
  - [ ] `qc_scrap`
  - [ ] `qc_replacement_in`
- [ ] Add nullable tracing columns to `stock_movements`:
  - `qc_hold_batch_line_id TEXT` — references the hold line that triggered the movement
  - `qc_inspection_id TEXT` — references the inspection (for release/scrap movements)
  - Non-QC movements leave both columns NULL
- [ ] Add constants in `config.py` (no magic strings):
  - [ ] `LOC_SCRAP = "SCRAP"` — scrap location used for `qc_scrap` movements
  - [ ] `QC_INFERENCE_MODEL = "gpt-5.4"` — model name for chat completion calls; `run_inspection` must reference `config.QC_INFERENCE_MODEL`, never a literal string
  - [ ] optional QC hold location constants if needed by implementation
- [ ] Keep database evolution reset-only for MVP:
  - [ ] no migration/backfill framework work in this phase
  - [ ] defaults are enforced by `schema.sql` on reset/init
- [ ] Note on `qc_replacements.sales_order_id NOT NULL`: guard at service level — if `qc_hold_batches.sales_order_id IS NULL`, skip replacement creation entirely. Do not relax the schema constraint.

Tests to add:

- [ ] `tests/test_qc_schema.py`
  - [ ] all QC tables exist
  - [ ] all expected columns exist
  - [ ] indexes exist for key filter/join columns
- [ ] `tests/test_qc_schema_reset_only.py`
  - [ ] reset/init path creates QC schema with defaults (`inspection_required=0`, `inspection_status='none'`)

Validation command:

- [ ] `pytest -q tests/test_qc_schema.py tests/test_qc_schema_reset_only.py`

---

### Step A3 - Route Completion to QC Hold

Goal: For inspection-required MOs, completion creates hold rows and does not add FG stock.

Implementation checklist:

- [ ] Modify `services/production.py` in `complete_order(...)`:
  - [ ] branch on `production_orders.inspection_required`
  - [ ] if `inspection_required=1`:
    - [ ] create `qc_hold_batches` row with:
      - `sales_order_id = order["sales_order_id"]`
      - `item_id = order["item_id"]`
      - `status = 'pending_images'` (initial status)
      - `created_at = sim_time`
    - [ ] create `qc_hold_batch_lines` row with:
      - `qc_hold_batch_id = batch_id`
      - `item_id = order["item_id"]`
      - `qty_on_hold = qty_produced`
      - `qty_pending = qty_produced`
      - `qty_released = 0`, `qty_scrapped = 0`
      - `line_status = 'pending_inspection'` (initial status)
      - `created_at = sim_time`
    - [ ] set `inspection_status='pending_inspection'` on the production order
    - [ ] do not create `stock` row
    - [ ] do not write `production_in` movement for that qty
  - [ ] else preserve existing stock insertion path
- [ ] `complete_order` signature is **unchanged** — `warehouse` and `location` are still accepted as parameters. They are simply unused in the QC branch. Callers (including the scenario) must still pass them (use `config.WAREHOUSE_DEFAULT` and `config.LOC_FINISHED_GOODS`).
- [ ] Keep operation finalization and wait closure unchanged.

Tests to add:

- [ ] `tests/test_qc_production_completion.py`
  - [ ] QC-required completion creates hold rows only
  - [ ] non-QC completion still creates stock + production movement
  - [ ] production order status transitions remain valid

Validation command:

- [ ] `pytest -q tests/test_qc_production_completion.py tests/test_rest_production.py`

---

## Milestone B - Availability Rules + Inspection + Disposition + Replacement

### Step B1 - Exclude QC Hold Qty From Availability/Shipping

Goal: Pending QC qty cannot be allocated or shipped.

Implementation checklist:

- [ ] Update `services/inventory.py` availability summary logic:
  - [ ] **Note**: because Step A3 never inserts QC-held quantities into the `stock` table, `get_stock_summary` already naturally excludes them from `on_hand`. No changes are needed to account for QC hold in the on_hand calculation.
  - [ ] The only required change is to `_compute_reserved`: add a sub-query that also sums `qc_hold_batch_lines.qty_pending` for the item (where `line_status = 'pending_inspection'`), so that `available_total` and the UI stock display both correctly reflect pending-QC quantities as unavailable to allocate.
- [ ] Update `services/fulfillment.py` shipping checks:
  - [ ] **No changes required.** `ship_ready_orders` queries the `stock` table directly. QC-held quantities are never inserted into `stock` (Step A3), so they are already excluded from shipping eligibility automatically.
- [ ] If required, add helper query in QC domain service to compute held qty by item.

Tests to add:

- [ ] `tests/test_qc_allocation_exclusion.py`
  - [ ] inventory availability excludes pending QC hold
  - [ ] shipping blocked when only held qty exists
  - [ ] shipping allowed after release

Validation command:

- [ ] `pytest -q tests/test_qc_allocation_exclusion.py tests/test_rest_stock.py tests/test_rest_shipments.py`

---

### Step B2 - Implement Image Attach + Inspection Persistence

Goal: Persist image evidence and normalized inspection output.

Implementation checklist:

- [ ] Add QC service methods (new `services/qc.py` recommended):
  - [ ] `list_pending_batches(...)`
  - [ ] `get_batch(...)`
  - [ ] `attach_images(*, batch_id: str, image_urls: list[str], uploaded_by: str | None = None) -> dict`
    - Inserts one `qc_hold_images` row per URL.
    - After inserting, update `qc_hold_batches.status` to `'ready_for_inspection'` (from `'pending_images'`).
    - Returns the updated batch dict.
  - [ ] `run_inspection(*, batch_id: str) -> dict`
- [ ] `run_inspection(...)` responsibilities:
  - [ ] validate batch/production linkage
  - [ ] fail explicitly (`raise ValueError`) if batch has no images in `qc_hold_images`
  - [ ] resolve reference image: fetch `items.image` BLOB via `production_orders.item_id`; fail explicitly (`raise ValueError`) if the BLOB is NULL
  - [ ] base64-encode the BLOB and format as `"data:image/jpeg;base64,<encoded>"` for the chat message payload
  - [ ] invoke MyForterro inference through `services/myforterro.py` using `myforterro.chat_completion(...)`
  - [ ] use `model=config.QC_INFERENCE_MODEL` (never a literal string)
  - [ ] send exactly two images in a single chat completion request: first the reference image (as data URI), then the operator-submitted image URL from `qc_hold_images` (as a regular URL); both as `{"type": "image_url", "image_url": {"url": "..."}}` message parts
  - [ ] tenant-scoped auth headers are handled automatically by `myforterro.get_inference_client()`; do not add them manually
  - [ ] **Two-phase inspection INSERT**: because `qc_inspections.decision` is NOT NULL, INSERT the row first with `status='pending'` and `decision=''`, then call the inference API, then UPDATE with `status='completed'`, `decision=<result>`, and all other fields. On API failure, UPDATE with `status='failed'`. This keeps the schema constraint while supporting rollback semantics.
  - [ ] Set `qc_inspections.model_name = config.QC_INFERENCE_MODEL`
  - [ ] Set `qc_inspections.prompt_version = "v1"` (plain constant — no config entry needed)
  - [ ] parse the model's response content as JSON; raise explicitly on parse failure or if the response does not match the required schema (see Inference Response Schema below)
  - [ ] normalize findings into `qc_inspection_findings` rows
  - [ ] persist `qc_inspections` + `qc_inspection_findings`
  - [ ] set batch status to `'inspected'`
- [ ] Idempotency: enforce via a **partial unique index** added in `schema.sql`:
  ```sql
  CREATE UNIQUE INDEX idx_qc_inspection_batch_unique
      ON qc_inspections(qc_hold_batch_id) WHERE status != 'failed';
  ```
  Service logic: if a `completed` inspection exists for the batch, return it without re-running. If a `failed` inspection exists, DELETE it and re-run.
- [ ] **Inference Response Schema** — `run_inspection` must parse the model's JSON response into this structure and raise `ValueError` if `decision` is missing or not in the allowed set, or if `findings` is not a list:
  ```json
  {
    "decision": "pass | partial_scrap | full_scrap",
    "confidence_overall": 0.95,
    "decision_reason": "string",
    "findings": [
      {
        "type": "wrong_product | paint_defect | shape_defect | assembly_defect | packaging_defect | missing_part",
        "severity": "critical | major | minor",
        "confidence": 0.9,
        "description": "string",
        "image_ref": "string or null",
        "location_hint": "string or null"
      }
    ]
  }
  ```

Tests to add:

- [ ] `tests/test_qc_inspection_service.py`
  - [ ] valid model result persists inspection + findings
  - [ ] invalid model schema fails explicitly
  - [ ] idempotent duplicate call does not duplicate rows
  - [ ] verifies outbound inference payload uses `model=config.QC_INFERENCE_MODEL`
  - [ ] verifies outbound call includes exactly two image inputs in a single chat completion request

Validation command:

- [ ] `pytest -q tests/test_qc_inspection_service.py`

---

### Step B3 - Implement Disposition Engine (Transactional)

Goal: Apply pass/partial/full disposition with strict quantity integrity.

Implementation checklist:

- [ ] Add `apply_disposition(*, qc_inspection_id: str, action: str, approved_by: str | None = None, reason: str | None = None, qty_scrapped: int = 0) -> dict` in QC service:
  - [ ] `pass_release`: move `qty_pending` → `qty_released`; INSERT a `stock` row at `(config.WAREHOUSE_DEFAULT, config.LOC_FINISHED_GOODS)` and write a `qc_hold_release` movement referencing that `stock_id`; set `stock_movements.qc_hold_batch_line_id` and `qc_inspection_id` on the movement row
  - [ ] `partial_scrap`: `qty_scrapped` (from parameter) moves to `qty_scrapped`; remainder (`qty_pending - qty_scrapped`) moves to `qty_released`; write `qc_hold_release` movement (with stock row at `LOC_FINISHED_GOODS`) for released qty; write `qc_scrap` movement (with `stock_id=NULL`, `reference_type='qc_disposition'`) for scrap qty
  - [ ] `full_scrap`: move all `qty_pending` → `qty_scrapped`; write `qc_scrap` movement with `stock_id=NULL`
  - [ ] **Scrap movements do not create a stock row** — scrap is disposed inventory. Set `stock_id=NULL` (the schema is nullable after Step A2). Set `reference_type='qc_disposition'` and `reference_id=disposition_id`.
- [ ] Persist `qc_dispositions` audit record for every action.
- [ ] Update line and batch statuses based on post-action quantities.
- [ ] Update `production_orders.inspection_status` accordingly.
- [ ] Ensure all writes run in one transaction and rollback on any failure.
- [ ] Idempotency: `qc_dispositions` has a `UNIQUE(qc_inspection_id)` constraint (enforced in `schema.sql`). If a disposition already exists for this inspection, return it without re-applying. After any disposition, `qty_pending` is always zero — there is no second disposition on the same inspection.

Tests to add:

- [ ] `tests/test_qc_disposition_service.py`
  - [ ] quantity math correct for all 3 actions
  - [ ] movement types/qty signs correct
  - [ ] rollback on injected failure
  - [ ] repeated idempotent call does not double-apply

Validation command:

- [ ] `pytest -q tests/test_qc_disposition_service.py`

---

### Step B4 - Auto-Replacement MO Creation

Goal: Create replacement production when scrap creates shortage.

Implementation checklist:

- [ ] Implement shortage formula in QC service:
  - [ ] For MVP, `available_substitute_qty = 0` — always create a replacement when any qty is scrapped. Existing FG stock is deliberately not factored in; the scheduler will absorb it on the next planning cycle.
  - [ ] `qty_short = scrapped_qty` (formula simplifies directly)
  - [ ] `qty_replacement = ceil(qty_short / output_qty) * output_qty` (round up to batch size using `math.ceil`)
- [ ] Guard: if `qc_hold_batches.sales_order_id IS NULL`, skip replacement creation entirely.
- [ ] **Transaction boundary**: `production_service.create_order` internally calls `conn.commit()` via its own `db_conn()` block. Since `db_conn()` reuses the thread-local connection, calling it inside the disposition transaction would commit that inner work early and break atomicity. Use a two-phase approach:
  1. Inside the `with db_conn()` transaction: apply all disposition writes + INSERT the `qc_replacements` row with `replacement_production_order_id = ''` as a placeholder.
  2. `conn.commit()` to close the disposition atomic unit.
  3. Outside the transaction: call `production_service.create_order(recipe_id=..., sales_order_id=..., notes=f"QC replacement for {batch_id}")`.
  4. UPDATE `qc_replacements SET replacement_production_order_id = <new_mo_id> WHERE id = <repl_id>` in a separate small `db_conn()` block.
- [ ] Create replacement MO by calling `production_service.create_order(recipe_id=..., sales_order_id=..., notes=f"QC replacement for {batch_id}")` (see above for sequencing).
- [ ] Persist trace in `qc_replacements`.
- [ ] `qc_replacement_in` movement is written by the replacement MO's own completion path (Step A3), not by the QC disposition service.

Tests to add:

- [ ] `tests/test_qc_replacements.py`
  - [ ] no shortage -> no replacement
  - [ ] shortage exact multiple -> exact batch replacement
  - [ ] shortage partial batch -> rounded-up replacement
  - [ ] trace row links disposition + SO + replacement MO

Validation command:

- [ ] `pytest -q tests/test_qc_replacements.py`

---

## Milestone C - MCP + REST + UI Integration

### Step C1 - Add QC MCP Tools

Goal: Full QC flow available via MCP tools with existing confirmation UX pattern.

Implementation checklist:

- [ ] Create `mcp_tools/qc_tools.py` with these tools and their argument signatures:
  - [ ] `qc_list_pending_batches` — no required args; optional `status: str = 'pending_images'` filter
  - [ ] `qc_get_batch(batch_id: str)` — returns batch + lines + images + inspection summary
  - [ ] `qc_get_inspection(inspection_id: str)` — returns inspection + findings
  - [ ] `qc_attach_images(batch_id: str, image_urls: list[str], uploaded_by: str | None = None)` — mutating; returns updated batch
  - [ ] `qc_run_inspection(batch_id: str)` — mutating; returns inspection record
  - [ ] `qc_apply_disposition(qc_inspection_id: str, action: str, qty_scrapped: int = 0, approved_by: str | None = None, reason: str | None = None)` — mutating; returns `create_confirmation_response(...)`; `field_configs` should include: `qc_inspection_id` (text, readonly), `action` (options: `pass_release`/`partial_scrap`/`full_scrap`), `qty_scrapped` (number, required for `partial_scrap`), `approved_by` (text), `reason` (textarea). This tool is called by the **chat agent**, never by the UI.
- [ ] All mutating tools (`qc_attach_images`, `qc_run_inspection`, `qc_apply_disposition`) need `structured_output=False` (following the pattern in `mcp_tools/production_tools.py` for confirmation tools).
- [ ] Set MCP tool tags to `quality` for all QC tools.
- [ ] Register in `mcp_tools/__init__.py`.
- [ ] Add activity mapping in `mcp_tools/_common.py` for mutating QC tools:
  - [ ] Add to `TOOL_ACTION_MAP`:
    ```python
    "qc_attach_images":     ("quality", "qc.images_attached"),
    "qc_run_inspection":    ("quality", "qc.inspection_run"),
    "qc_apply_disposition": ("quality", "qc.disposition_applied"),
    ```
  - [ ] Add to `_ENTITY_ID_KEYS`: `"qc_hold_batch_id"`, `"qc_inspection_id"`, `"qc_disposition_id"`
  - [ ] Add to `_KEY_TO_TYPE`: `"qc_hold_batch_id": "qc_hold_batch"`, `"qc_inspection_id": "qc_inspection"`, `"qc_disposition_id": "qc_disposition"`
- [ ] For `qc_apply_disposition`, use the existing generic confirm flow:
  - [ ] tool returns `create_confirmation_response(...)`
  - [ ] add dispatcher branch in `mcp_tools/confirm_tools.py`:
    ```python
    elif original_tool == "qc_apply_disposition":
        return qc_service.apply_disposition(
            qc_inspection_id=arguments["qc_inspection_id"],
            action=arguments["action"],
            approved_by=arguments.get("approved_by"),
            reason=arguments.get("reason"),
            qty_scrapped=int(arguments.get("qty_scrapped") or 0),
        )
    ```
  - [ ] add `from services import qc_service` at the top of `confirm_tools.py` alongside the other service imports

Tests to add:

- [ ] `tests/test_mcp_qc.py`
  - [ ] read tools return expected shapes
  - [ ] mutation tools return confirmation payload where expected
  - [ ] confirm dispatcher executes disposition service correctly

Validation command:

- [ ] `pytest -q tests/test_mcp_qc.py`

---

### Step C2 - Add QC REST Routes For Read-Only UI Data

Goal: UI can display queue/detail/trace without direct mutations.

Implementation checklist:

- [ ] Create `api_routes/qc_routes.py` with read endpoints only:
  - [ ] `GET /api/qc/batches?status=...`
  - [ ] `GET /api/qc/batches/{id}`
  - [ ] `GET /api/qc/inspections/{id}`
- [ ] Register route module in `api_routes/__init__.py`.
- [ ] Keep mutation path in MCP tools only (no REST state mutation).

Tests to add:

- [ ] `tests/test_rest_qc.py`
  - [ ] queue endpoint returns pending list
  - [ ] detail endpoint returns lines/images/inspection/replacements
  - [ ] unknown IDs return 404 shape

Validation command:

- [ ] `pytest -q tests/test_rest_qc.py`

---

### Step C3 - Extend UI For QC Queue + Detail + Trace

Goal: Expose QC state in UI while keeping mutation through MCP app dialogs.

Implementation checklist:

- [ ] Extend API client in `ui/src/api.ts`:
  - [ ] add QC read API methods:
    ```typescript
    qcBatches: (status?: string) =>
      fetchJson<{ batches: QcHoldBatch[] }>(`/qc/batches${status ? `?status=${encodeURIComponent(status)}` : ''}`),
    qcBatch: (id: string) => fetchJson<QcHoldBatchDetail>(`/qc/batches/${encodeURIComponent(id)}`),
    qcInspection: (id: string) => fetchJson<QcInspection>(`/qc/inspections/${encodeURIComponent(id)}`),
    ```
- [ ] Add types in `ui/src/types.ts` for QC entities:
  ```typescript
  export type QcHoldBatch = {
    id: string; production_order_id: string; sales_order_id?: string
    item_id: string; status: string; created_at: string; released_at?: string
    replacement_triggered: number; item_sku?: string; item_name?: string
    qty_pending?: number; qty_released?: number; qty_scrapped?: number
  }
  export type QcHoldBatchDetail = QcHoldBatch & {
    lines: QcHoldBatchLine[]; images: QcHoldImage[]
    inspection?: QcInspection; replacements?: QcReplacement[]
  }
  export type QcHoldBatchLine = {
    id: string; item_id: string; qty_on_hold: number; qty_pending: number
    qty_released: number; qty_scrapped: number; line_status: string; created_at: string
  }
  export type QcHoldImage = { id: string; image_url: string; created_at: string; uploaded_by?: string }
  export type QcInspection = {
    id: string; qc_hold_batch_id: string; model_name: string; status: string
    decision: string; confidence_overall?: number; decision_reason?: string
    created_at: string; completed_at?: string; findings: QcInspectionFinding[]
  }
  export type QcInspectionFinding = {
    id: string; finding_type: string; severity: string; confidence?: number
    description?: string; image_ref?: string; location_hint?: string
  }
  export type QcReplacement = {
    id: string; sales_order_id: string; item_id: string; qty_short: number
    qty_replacement: number; replacement_production_order_id: string; created_at: string
  }
  ```
- [ ] Add pages:
  - [ ] `ui/src/pages/QcQueuePage.tsx`
  - [ ] `ui/src/pages/QcBatchDetailPage.tsx`
- [ ] Wire navigation and view states in `ui/src/App.tsx`:
  - [ ] Add `'qc-queue'` to the `ViewPage` type union.
  - [ ] Add `'qc-queue'` to the `allowed` array in `parseHash()`.
  - [ ] Add a new nav group `{ label: 'Quality', items: [{ page: 'qc-queue', label: 'QC Queue' }] }` to the `navGroups` array (add after the Supply Chain group).
  - [ ] Add import lines: `import { QcQueuePage } from './pages/QcQueuePage'` and `import { QcBatchDetailPage } from './pages/QcBatchDetailPage'`.
  - [ ] Add render branches: `{view.page === 'qc-queue' && !view.id && <QcQueuePage onSelect={(id) => setHash('qc-queue', id)} />}` and `{view.page === 'qc-queue' && view.id && <QcBatchDetailPage batchId={view.id} />}`.
- [ ] If adding tables, use sorting pattern from `docs/CODING.md` (`useTableSort`).
- [ ] **The UI is strictly read-only.** No buttons, forms, or handlers that trigger any state change. Disposition and all other QC mutations are initiated exclusively through the chat/MCP interface. The UI shows the current state of QC batches, inspections, and dispositions — it never causes them.

Tests to add:

- [ ] UI component tests for rendering queue/detail data (read-only shape checks).

Validation command:

- [ ] `cd ui && npm run lint`
- [ ] `cd ui && npm run build`

---

### Step C4 - Optional Dedicated QC MCP App Dialog

Goal: If generic confirm is too limited, add QC-specific dialog while preserving dispatcher pattern.

Implementation checklist:

- [ ] Follow existing MCP app build conventions (HTML entry + `MCP_APP_ENTRY` script):
  - [ ] add root UI entry file, for example `ui/qc-disposition.html`
  - [ ] add React implementation files under `ui/src/` (path chosen to match existing project structure)
  - [ ] add script `build:mcp-app:qc-disposition` in `ui/package.json`
  - [ ] include that script in `build:mcp-app` chain in `ui/package.json`
- [ ] Build static app asset to `mcp_apps_ui/`.
- [ ] Register resource URI in `server.py`.
- [ ] Point `qc_apply_disposition` tool metadata `resourceUri` to new app.

Validation command:

- [ ] `cd ui && npm run build:mcp-app`
- [ ] Run backend and verify `ui://...` resource resolves.

---

## Milestone D - Scenario Determinism + End-to-End Hardening

### Step D1 - Deterministic 3-Pending-QC Contract in Scenario

Goal: End of s01 has exactly three pending inspections for target SKUs.

Implementation checklist:

- [ ] Add deterministic injection logic in `scenarios/s01_steady_state.py`:
  - [ ] INSERT the three production orders directly with hardcoded IDs (do **not** call `generate_id`; the `9000` range is reserved and scenario execution never reaches it):
    - `MO-9000` → ELVIS-DUCK-20CM recipe + the SO created for it
    - `MO-9001` → MARILYN-DUCK-20CM recipe + the SO created for it
    - `MO-9002` → ZOMBIE-DUCK-15CM recipe + the SO created for it
  - [ ] For the three dedicated sales orders, use the most frequent customer already present in the generated dataset (or the first customer returned by `SELECT id FROM customers LIMIT 1` — any valid customer is sufficient; the SO is only needed as a non-NULL FK anchor).
  - [ ] Set `inspection_required=1` on all three at INSERT time
  - [ ] Advance simulation to complete all three MOs by calling `production_service.complete_order(production_order_id=..., qty_produced=<recipe output_qty>, warehouse=config.WAREHOUSE_DEFAULT, location=config.LOC_FINISHED_GOODS)` — Step A3 will route them to QC hold automatically (the warehouse/location args are accepted but ignored in the QC branch)
  - [ ] Do **not** run fulfillment or dispatch on these three MOs after completion
- [ ] Ensure the main loop continues naturally for realism.
- [ ] Add hard end-of-scenario assertions:
  - [ ] exactly 3 pending inspections
  - [ ] all completed
  - [ ] exact target SKU set
  - [ ] not consumed by shipment lines

Tests to add:

- [ ] `tests/test_qc_scenario_contract.py`
  - [ ] scenario end-state assertions
  - [ ] repeatability check (run twice, same contract)

Validation command:

- [ ] `python -m scenarios --only s01`
- [ ] `pytest -q tests/test_qc_scenario_contract.py`

---

### Step D2 - End-to-End Lifecycle Tests

Goal: Verify full QC lifecycle behavior from MO completion to release/scrap/replacement.

Implementation checklist:

- [ ] Create `tests/test_qc_e2e.py` with 3 happy paths:
  - [ ] pass_release flow
  - [ ] partial_scrap with replacement flow
  - [ ] full_scrap flow
- [ ] Add assertions on stock, movements, statuses, replacements, and activity logs.
- [ ] Add one regression test that non-QC MOs preserve existing behavior.

Validation command:

- [ ] `pytest -q tests/test_qc_e2e.py`
- [ ] `pytest -q`

---

## 3. PR Breakdown (Recommended)

### PR 1 (Foundation)

- [ ] A1 + A2 + A3
- [ ] tests: schema/domain/completion

### PR 2 (Core behavior)

- [ ] B1 + B2 + B3 + B4
- [ ] tests: availability/inspection/disposition/replacement

### PR 3 (Interfaces)

- [ ] C1 + C2 + C3 (+ C4 optional)
- [ ] tests: MCP and REST contract + UI tests

### PR 4 (Determinism and hardening)

- [ ] D1 + D2
- [ ] tests: scenario contract + full regression

---

## 4. Full Test Execution Checklist

Run in this order while implementing:

- [ ] `pytest -q tests/test_qc_domain_states.py tests/test_qc_domain_invariants.py`
- [ ] `pytest -q tests/test_qc_schema.py tests/test_qc_schema_reset_only.py`
- [ ] `pytest -q tests/test_qc_production_completion.py`
- [ ] `pytest -q tests/test_qc_allocation_exclusion.py`
- [ ] `pytest -q tests/test_qc_inspection_service.py`
- [ ] `pytest -q tests/test_qc_disposition_service.py`
- [ ] `pytest -q tests/test_qc_replacements.py`
- [ ] `pytest -q tests/test_mcp_qc.py tests/test_rest_qc.py`
- [ ] `pytest -q tests/test_qc_scenario_contract.py tests/test_qc_e2e.py`
- [ ] `pytest -q`

If UI was changed:

- [ ] `cd ui && npm run build`
- [ ] `cd ui && npm run build:mcp-app`

---

## 5. Definition Of Done (Implementation-Ready)

All boxes below must be true:

- [ ] QC-required MO completion never inserts directly into shippable stock.
- [ ] Pending QC qty is excluded from stock availability and shipment allocation.
- [ ] Inspection image evidence and findings persist with strict schema behavior.
- [ ] All 3 dispositions are transactional, auditable, and idempotent.
- [ ] Replacement orders are created correctly when shortages occur.
- [ ] MCP tools expose full QC flow and follow existing confirmation pattern.
- [ ] UI shows queue/detail/trace and does not mutate QC state via REST.
- [ ] Scenario s01 ends with exactly 3 pending inspections for target SKUs.
- [ ] New QC tests pass and existing regression tests remain green.

---

## 6. Notes And Constraints To Respect

- Keep constants in `config.py` (no magic strings/numbers).
- Prefer keyword-only arguments in new service functions.
- Do not use defensive fake data; fail explicitly when state is invalid.
- Keep quantity columns and computations as integers.
- Keep UI write actions routed through MCP tools, not UI-only mutation routes.
- QC image comparison must go through MyForterro AI inference API using chat completions on `config.QC_INFERENCE_MODEL` with two images per request.
- **Test isolation**: QC mutation tests (A3, B1, B2, B3, B4, D2) must use a **per-function-scoped DB fixture**. Add a `qc_db` fixture in `tests/conftest.py` (or a local `conftest.py` in a `tests/qc/` subfolder) that calls `db.init_db()` on a fresh `tmp_path` file and seeds only the minimal rows needed for that test. Do not rely on the session-scoped shared DB for any test that writes QC state. Read-only contract tests (C1 MCP shape tests, C2 REST tests) may use the session-scoped `mcp_app` / `rest_client` fixtures after adding QC seed rows to `tests/seed_test_data.py`.
- **Seed data additions for QC tests**: add to `tests/seed_test_data.py`:
  - One finished-good item with a non-NULL `image` BLOB (a 1-pixel JPEG bytes literal is sufficient — no external file needed).
  - A corresponding recipe with `output_qty` set.
  - One production order with `inspection_required=1`, `status='completed'`, linked to a sales order — used as the fixture MO for completion/inspection/disposition tests.
- **`vite.config.ts` is not changed for Step C4.** Only `package.json` needs a new `build:mcp-app:qc-disposition` script (`MCP_APP_ENTRY=qc-disposition.html vite build --mode mcp-app`) and inclusion in the `build:mcp-app` chain. The existing `MCP_APP_ENTRY` env-var mechanism in `vite.config.ts` already handles routing to any HTML entry point.
