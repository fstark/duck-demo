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

- [ ] Add QC state/action constants (single source of truth). Recommended new module:
  - [ ] `services/qc.py` (or `services/qc_domain.py`)
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
  - [ ] extend `production_orders` with `inspection_required` and `inspection_status`
  - [ ] create `qc_hold_batches`
  - [ ] create `qc_hold_batch_lines`
  - [ ] create `qc_hold_images`
  - [ ] create `qc_inspections`
  - [ ] create `qc_inspection_findings`
  - [ ] create `qc_dispositions`
  - [ ] create `qc_replacements`
  - [ ] add indexes listed in design
- [ ] Extend stock movement allowed conventions in code paths to include:
  - [ ] `qc_hold_release`
  - [ ] `qc_scrap`
  - [ ] `qc_replacement_in`
- [ ] Add constants in `config.py` (no magic strings):
  - [ ] scrap location constant (for example `LOC_SCRAP`)
  - [ ] optional QC hold location constants if needed by implementation
- [ ] Keep database evolution reset-only for MVP:
  - [ ] no migration/backfill framework work in this phase
  - [ ] defaults are enforced by `schema.sql` on reset/init

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
    - [ ] create `qc_hold_batches` row
    - [ ] create `qc_hold_batch_lines` row with `qty_on_hold=qty_pending=qty_produced`
    - [ ] set `inspection_status='pending_inspection'`
    - [ ] do not create `stock` row
    - [ ] do not write `production_in` movement for that qty
  - [ ] else preserve existing stock insertion path
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
  - [ ] subtract active QC hold pending quantities from available-to-allocate
- [ ] Update `services/fulfillment.py` shipping checks:
  - [ ] ensure raw `on_hand` checks do not accidentally include QC-held quantities
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
  - [ ] `attach_images(...)`
  - [ ] `run_inspection(...)`
- [ ] `run_inspection(...)` responsibilities:
  - [ ] validate batch/production linkage
  - [ ] resolve reference image from the product being built (image associated with `production_orders.item_id`)
  - [ ] fail explicitly if required reference image is missing
  - [ ] invoke MyForterro inference through `services/myforterro.py`
  - [ ] call OpenAI-compatible chat completions endpoint on MyForterro API
  - [ ] set `model='gpt-5.4'`
  - [ ] send two images in the same completion request (reference image + inspected image)
  - [ ] include tenant-scoped auth headers via MyForterro client wiring
  - [ ] strict JSON parsing and normalization
  - [ ] persist `qc_inspections` + `qc_inspection_findings`
  - [ ] set batch status to `inspected`
- [ ] Add idempotency keying strategy for repeated inspection submission.

Tests to add:

- [ ] `tests/test_qc_inspection_service.py`
  - [ ] valid model result persists inspection + findings
  - [ ] invalid model schema fails explicitly
  - [ ] idempotent duplicate call does not duplicate rows
  - [ ] verifies outbound inference payload uses `model='gpt-5.4'`
  - [ ] verifies outbound call includes exactly two image inputs in a single chat completion request

Validation command:

- [ ] `pytest -q tests/test_qc_inspection_service.py`

---

### Step B3 - Implement Disposition Engine (Transactional)

Goal: Apply pass/partial/full disposition with strict quantity integrity.

Implementation checklist:

- [ ] Add `apply_disposition(...)` in QC service:
  - [ ] `pass_release`: move pending to released, insert stock, write `qc_hold_release`
  - [ ] `partial_scrap`: split pending to released+scrapped, write `qc_hold_release` + `qc_scrap`
  - [ ] `full_scrap`: move all pending to scrapped, write `qc_scrap`
- [ ] Persist `qc_dispositions` audit record for every action.
- [ ] Update line and batch statuses based on post-action quantities.
- [ ] Update `production_orders.inspection_status` accordingly.
- [ ] Ensure all writes run in one transaction and rollback on any failure.
- [ ] Add disposition idempotency token support.

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
  - [ ] `qty_short = max(0, scrapped_qty - available_substitute_qty)`
  - [ ] `qty_replacement = ceil(qty_short / output_qty) * output_qty`
- [ ] Create replacement MO via production service path (or direct service call), linked to originating SO.
- [ ] Persist trace in `qc_replacements`.
- [ ] Optionally write `qc_replacement_in` movement only when replacement output later enters stock.

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

- [ ] Create `mcp_tools/qc_tools.py` with:
  - [ ] `qc_list_pending_batches`
  - [ ] `qc_get_batch`
  - [ ] `qc_get_inspection`
  - [ ] `qc_attach_images`
  - [ ] `qc_run_inspection`
  - [ ] `qc_apply_disposition`
- [ ] Set MCP tool tags to `quality` for all QC tools.
- [ ] Register in `mcp_tools/__init__.py`.
- [ ] Add activity mapping in `mcp_tools/_common.py` for mutating QC tools.
- [ ] For `qc_apply_disposition`, use the existing generic confirm flow:
  - [ ] tool returns `create_confirmation_response(...)`
  - [ ] add dispatcher branch in `mcp_tools/confirm_tools.py`

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
  - [ ] add QC read API methods
- [ ] Add types in `ui/src/types.ts` for QC batch/detail/inspection/replacement entities.
- [ ] Add pages:
  - [ ] `ui/src/pages/QcQueuePage.tsx`
  - [ ] `ui/src/pages/QcBatchDetailPage.tsx`
- [ ] Wire navigation and view states in `ui/src/App.tsx`.
- [ ] If adding tables, use sorting pattern from `docs/CODING.md` (`useTableSort`).
- [ ] For disposition action buttons, call MCP tool flow and generic confirmation UI; do not call direct write REST.

Tests to add:

- [ ] UI component tests for rendering queue/detail data.
- [ ] Integration/UI tests for click-flow that invokes MCP tool action (no direct mutation fetch).

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
  - [ ] create or reserve `MO-9000`, `MO-9001`, `MO-9002`
  - [ ] map to ELVIS/MARILYN/ZOMBIE target SKUs
  - [ ] set `inspection_required=1`
  - [ ] ensure they complete into QC hold
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
- QC image comparison must go through MyForterro AI inference API using chat completions on model `gpt-5.4` with two images per request.
