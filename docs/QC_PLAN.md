# QC Feature Implementation Plan

## 1. Goal

Implement the AI-assisted Quality Control (QC) flow so that inspection-required production output is held out of shippable stock until a QC disposition is applied.

This plan follows the current MVP decisions from `docs/QC_DESIGN.md`:

- No `qc_hold_in` stock movement.
- No `manual_review` action.
- No `exception_release` action.
- UI must not mutate state directly; mutations happen via MCP tools.
- `inspection_required` is set by scenario generation.
- Granularity is produced batch line.
- Scenario contract ends with exactly 3 pending inspections.

## 2. Scope and Non-Goals

In scope:

- Database model for hold, images, inspections, dispositions, and replacements.
- Production completion routing into QC hold for flagged orders.
- Inspection and disposition MCP tools.
- QC image comparison inference via MyForterro AI inference API (OpenAI-compatible chat completions) using model `gpt-5.4` with two images per request.
- QC-aware stock and allocation behavior.
- Deterministic scenario data with 3 pending inspections.
- Read-only UI views and MCP App action flow.
- End-to-end tests and contract tests.

Out of scope for MVP:

- Manual review state machine.
- Exception releases.
- UI-only state mutation endpoints.
- Fine-grained authz/authn (project is intentionally open).

## 3. Implementation Sequence

### Step 1: Finalize Domain Contract and Test Matrix

Implementation tasks:

- Freeze the canonical state machine for:
  - `production_orders.inspection_status`
  - `qc_hold_batches.status`
  - `qc_hold_batch_lines.line_status`
- Freeze allowed disposition actions: `pass_release`, `partial_scrap`, `full_scrap`.
- Freeze quantity invariant enforcement rule:
  - `qty_released + qty_scrapped + qty_pending = qty_on_hold`
- Define idempotency keys for inspection and disposition operations.
- Add this document to docs index references if needed.

Associated tests:

- Documentation validation checklist:
  - Allowed states/actions listed once and consistently across docs.
- State-transition unit tests (table-driven):
  - Valid transitions pass.
  - Invalid transitions raise domain error.
- Invariant test:
  - Every disposition path preserves line quantity invariant.

---

### Step 2: Schema Implementation (Reset-Only)

Implementation tasks:

- Update `schema.sql` with:
  - New fields on `production_orders`.
  - New `qc_*` tables.
  - New indexes.
- Extend stock movement conventions with:
  - `qc_hold_release`, `qc_scrap`, `qc_replacement_in`.
- Keep database evolution reset-only for MVP:
  - No migration/backfill framework work in this phase.
  - Defaults are enforced by `schema.sql` on reset/init.
- Add needed constants (for example scrap location constant in config if required).

Associated tests:

- Reset/init tests:
  - Fresh bootstrap creates all QC columns/tables/indexes with defaults.
- Schema integrity tests:
  - Required fields are non-null where expected.
  - Foreign key behavior matches restrictions.
- Smoke SQL tests:
  - Insert/select across all new QC tables.

---

### Step 3: Production Completion Routing to QC Hold

Implementation tasks:

- Update production completion flow so:
  - If `inspection_required = 1`, output is written to `qc_hold_batch_lines` pending quantities.
  - No normal stock insertion occurs at completion for that output.
  - `production_orders.inspection_status` becomes `pending_inspection`.
- Create `qc_hold_batches` and line records deterministically from completion event.
- Ensure standard non-QC orders keep current behavior.

Associated tests:

- Unit tests for completion branching:
  - QC-required order routes to hold only.
  - Non-QC order routes to stock only.
- Integration tests:
  - Completing MO creates expected hold batch + line records.
  - No stock increment for held quantities.
- Regression tests:
  - Existing production completion tests still pass for non-QC orders.

---

### Step 4: Allocation and Fulfillment Exclusion Rules

Implementation tasks:

- Update inventory/fulfillment calculations to exclude active QC hold quantities.
- Ensure shipment allocation and auto-dispatch cannot consume pending QC quantities.
- Release path must be the only mechanism that makes held quantity shippable.

Associated tests:

- Allocation unit tests:
  - Held qty is excluded from available-to-allocate.
- Fulfillment integration tests:
  - Orders cannot ship from pending inspection stock.
- Negative tests:
  - Attempting to dispatch with only QC-held quantity fails as expected.

---

### Step 5: QC Inspection Persistence and Normalization

Implementation tasks:

- Implement service logic to:
  - Attach image URLs to hold batches/lines.
  - Run inspection model call through MyForterro API chat completions with strict JSON schema.
  - Use `config.QC_INFERENCE_MODEL` (never a literal model name string) and send two images in one request (reference BLOB as base64 data URI + inspected batch image URL).
  - Route all inference calls through `services/myforterro.py` (no direct provider calls from QC domain service).
  - Persist `qc_inspections` and `qc_inspection_findings`.
- Normalize findings into canonical types/severity.
- Implement idempotent inspection submission: enforce via partial unique index `ON qc_inspections(qc_hold_batch_id) WHERE status != 'failed'`. Return existing completed inspection; delete and retry on failed.

Associated tests:

- Unit tests for parser/normalizer:
  - Valid model JSON maps to expected findings.
  - Invalid schema is rejected clearly.
- Idempotency tests:
  - Duplicate inspection call with same identity does not duplicate records.
- Service integration tests:
  - End-to-end image attach + run inspection persists expected data.
- Inference integration tests:
  - MyForterro call payload uses chat completions with model `gpt-5.4`.
  - Request includes exactly two images for comparison in the same completion call.

---

### Step 6: Disposition Application Engine

Implementation tasks:

- Implement disposition executor for:
  - `pass_release`
  - `partial_scrap`
  - `full_scrap`
- Ensure transactional updates include:
  - hold line quantities/status
  - stock movements
  - stock insertion for released qty only
  - production order inspection status
  - disposition audit row
- Implement idempotent disposition application via `UNIQUE(qc_inspection_id)` constraint on `qc_dispositions`. Return existing disposition if already applied; never re-apply.

Associated tests:

- Unit tests per action path:
  - Quantity transitions are correct.
  - Correct movement types are emitted.
- Transactionality tests:
  - Simulated failure rolls back all partial writes.
- Idempotency tests:
  - Repeated apply call does not double-release or double-scrap.

---

### Step 7: Replacement Order Logic

Implementation tasks:

- Implement shortage calculation:
  - `qty_short = scrapped_qty` (MVP: `available_substitute_qty = 0`; planner absorbs existing FG stock)
  - `qty_replacement = ceil(qty_short / output_qty) * output_qty`
- Auto-create replacement production order when `qty_short > 0`.
- Persist link in `qc_replacements`.
- Keep replacement creation inside disposition transaction boundary when possible.

Associated tests:

- Formula unit tests:
  - Rounding and boundary cases (`0`, exact multiples, partial batch).
- Integration tests:
  - Partial/full scrap creates replacement order when shortage exists.
  - No replacement order when shortage is zero.
- Traceability tests:
  - Replacement link points to correct disposition, sales order, and MO.

---

### Step 8: MCP Tools and Contract Tests

Implementation tasks:

- Implement read tools:
  - `qc_list_pending_batches`
  - `qc_get_batch`
  - `qc_get_inspection`
- Implement mutating tools:
  - `qc_attach_images`
  - `qc_run_inspection`
  - `qc_apply_disposition`
- Ensure mutating tools use existing confirmation pattern.
- Register tools in MCP tool exports/discovery.

Associated tests:

- Contract tests for each tool:
  - Required arguments validation.
  - Response shape validation.
  - Error shape validation for invalid states.
- Mutation behavior tests:
  - Tools produce expected DB changes.
- Authorization model sanity test:
  - No unexpected auth gate added in open demo mode.

---

### Step 9: UI and MCP App Integration

Implementation tasks:

- Build/extend read-only UI views:
  - QC queue (pending batches)
  - Inspection detail (images/findings/decision)
  - Replacement trace relationship
- Wire action buttons to MCP tools only (no direct write routes).
- Reuse existing MCP app confirmation dialogs for irreversible actions.

Associated tests:

- Component tests:
  - Queue/details render expected fields and statuses.
- UI integration tests:
  - User flow triggers MCP tools in the correct order.
- Safety tests:
  - No direct state mutation API calls from UI code path.

---

### Step 10: Scenario Determinism and Demo Contract

Implementation tasks:

- Add deterministic scenario injection for:
  - `MO-9000` (ELVIS-DUCK-20CM)
  - `MO-9001` (MARILYN-DUCK-20CM)
  - `MO-9002` (ZOMBIE-DUCK-15CM)
- Mark all three with `inspection_required = 1`.
- Ensure they complete into QC hold and remain pending inspection.
- Add hard end-of-scenario assertions.

Associated tests:

- Scenario tests:
  - Exactly 3 pending inspections at end.
  - SKU set matches expected trio.
  - All three are completed and pending inspection.
- Fulfillment-protection tests:
  - No shipment lines consume these held quantities.
- Repeatability tests:
  - Running scenario twice gives same QC end-state contract.

---

### Step 11: End-to-End and Regression Gate

Implementation tasks:

- Add one golden-path E2E test:
  - complete QC-required MO -> attach image -> inspect -> pass -> released stock available.
- Add one partial scrap E2E test with replacement creation.
- Add one full scrap E2E test.
- Add observability logs for key events (inspection run, disposition apply, replacement create).
- Add inference adapter assertions so QC E2E verifies MyForterro chat completion is invoked with `config.QC_INFERENCE_MODEL` and two images.

Associated tests:

- E2E test suite:
  - Full lifecycle coverage for each disposition.
- Regression suite:
  - Existing sales/production/shipping flows continue to pass.
- Performance sanity checks:
  - QC queue and batch detail queries remain within acceptable latency in demo dataset.

## 4. Suggested Test Layout

- `tests/test_qc_schema.py`
- `tests/test_qc_schema_reset_only.py`
- `tests/test_qc_domain_states.py`
- `tests/test_qc_domain_invariants.py`
- `tests/test_qc_production_completion.py`
- `tests/test_qc_allocation_exclusion.py`
- `tests/test_qc_inspection_service.py`
- `tests/test_qc_disposition_service.py`
- `tests/test_qc_replacements.py`
- `tests/test_mcp_qc.py`
- `tests/test_rest_qc.py`
- `tests/test_qc_scenario_contract.py`
- `tests/test_qc_e2e.py`

## 5. Exit Criteria (Definition of Done)

QC MVP is complete when all of the following are true:

1. QC-required production output is never shippable before disposition release.
2. All three disposition actions behave correctly and transactionally.
3. Replacement MOs are created correctly when scrap creates shortage.
4. MCP tools expose the full QC flow with stable contracts.
5. UI supports queue -> inspect -> disposition -> trace flow without direct mutation routes.
6. Scenario finishes with exactly 3 pending inspections for the target SKUs.
7. New QC tests and existing regression tests pass in CI.

## 6. Recommended Delivery Cadence

- Milestone A: Steps 1-3 (domain + schema + hold routing)
- Milestone B: Steps 4-7 (allocation + inspection + disposition + replacements)
- Milestone C: Steps 8-9 (MCP tools + UI integration)
- Milestone D: Steps 10-11 (scenario determinism + E2E hardening)

This cadence keeps risky data-model behavior early, then stabilizes interfaces, then hardens demo determinism.
