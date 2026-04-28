# QC Design

## MVP Decision Set

- No qc_hold_in movement type.
- No manual_review action.
- No exception_release action.
- No state mutation via UI-only endpoints; state changes go through MCP tools only.
- Inspection flag is set by scenario generation only.
- Granularity is produced batch line.
- Scenario contract must end with exactly 3 pending inspections.

## 1. Data Model Changes

This section defines the persistent model required for QC-hold, image inspection, disposition, and replacement traceability.

### 1.1 Design Principles

- Keep production order as the anchor entity.
- Track inspectable quantities at produced batch-line granularity.
- For inspection-required production orders, do not insert produced quantity into normal stock until disposition is applied.
- Enforce QC behavior through explicit hold/disposition states and allocation filters.
- Make every irreversible action auditable (scrap, release, replacement creation).
- Keep model deterministic for scenario generation and demo repeatability.

### 1.2 New Fields on Existing Tables

#### production_orders

Add:
- inspection_required INTEGER NOT NULL DEFAULT 0
- inspection_status TEXT NOT NULL DEFAULT 'none'

Valid inspection_status values:
- none
- pending_inspection
- inspected
- partially_released
- released

Notes:
- inspection_required is set by scenario generation (locked decision).
- inspection_status is derived by process events and used by UI queries.

#### stock_movements

No mandatory structural change required, but movement_type values must be extended by convention:
- qc_hold_release
- qc_scrap
- qc_replacement_in

Note:
- There is intentionally no qc_hold_in movement. For inspection_required orders, output is kept in QC hold records, not in stock, until release/scrap disposition.

Required additional columns for tracing:
- qc_hold_batch_line_id TEXT  — references the hold line that triggered the movement (NULL for non-QC movements)
- qc_inspection_id TEXT       — references the inspection run (NULL for non-QC movements)

Movement glossary:
- qc_hold_release: quantity approved by QC and inserted into normal available stock.
- qc_scrap: quantity rejected by QC and recorded as scrapped (not available for fulfillment).
- qc_replacement_in: quantity added by replacement production order created due to QC scrap shortage.

### 1.3 New Tables

### 1.3.1 Quick Human Purpose Summary

- qc_hold_batches: one QC container per flagged production order completion.
- qc_hold_batch_lines: quantity accounting lines inside a hold batch (pending/released/scrapped).
- qc_hold_images: image URLs attached by operator as inspection evidence.
- qc_inspections: one model-run result header per inspection action.
- qc_inspection_findings: normalized defects/findings from model output.
- qc_dispositions: final human-approved decision after inspection.
- qc_replacements: trace links from scrapped shortage to replacement MOs.

#### qc_hold_batches

Purpose:
- One hold batch per production order completion event requiring inspection.

Columns:
- id TEXT PRIMARY KEY
- production_order_id TEXT NOT NULL
- sales_order_id TEXT
- item_id TEXT NOT NULL
- status TEXT NOT NULL
- created_at TEXT NOT NULL
- released_at TEXT
- replacement_triggered INTEGER NOT NULL DEFAULT 0

Status values:
- pending_images
- ready_for_inspection
- inspected
- released
- partially_released
- closed

#### qc_hold_batch_lines

Purpose:
- Produced batch line granularity selected by business.
- Enables partial scrap and partial release accounting.

Columns:
- id TEXT PRIMARY KEY
- qc_hold_batch_id TEXT NOT NULL
- item_id TEXT NOT NULL
- qty_on_hold INTEGER NOT NULL
- qty_pending INTEGER NOT NULL
- qty_released INTEGER NOT NULL DEFAULT 0
- qty_scrapped INTEGER NOT NULL DEFAULT 0
- line_status TEXT NOT NULL
- created_at TEXT NOT NULL
- closed_at TEXT

Line status values:
- pending_inspection
- released
- partially_released
- scrapped

Integrity invariant:
- qty_released + qty_scrapped + qty_pending = qty_on_hold

#### qc_hold_images

Purpose:
- Attach evidence images to hold batches or specific hold lines.

Columns:
- id TEXT PRIMARY KEY
- qc_hold_batch_id TEXT NOT NULL
- qc_hold_batch_line_id TEXT
- image_url TEXT NOT NULL
- image_hash TEXT
- created_at TEXT NOT NULL
- uploaded_by TEXT

#### qc_inspections

Purpose:
- Inspection run metadata and final decision.

Columns:
- id TEXT PRIMARY KEY
- qc_hold_batch_id TEXT NOT NULL
- production_order_id TEXT NOT NULL
- model_name TEXT NOT NULL
- status TEXT NOT NULL
- decision TEXT NOT NULL
- confidence_overall REAL
- decision_reason TEXT
- prompt_version TEXT
- created_at TEXT NOT NULL
- completed_at TEXT

Status values:
- pending
- completed
- failed

Decision values:
- pass
- partial_scrap
- full_scrap

#### qc_inspection_findings

Purpose:
- Structured findings produced by model output normalization.

Columns:
- id TEXT PRIMARY KEY
- qc_inspection_id TEXT NOT NULL
- finding_type TEXT NOT NULL
- severity TEXT NOT NULL
- confidence REAL
- description TEXT
- image_ref TEXT
- location_hint TEXT
- created_at TEXT NOT NULL

finding_type values:
- wrong_product
- paint_defect
- shape_defect
- assembly_defect
- packaging_defect
- missing_part

severity values:
- critical
- major
- minor

#### qc_dispositions

Purpose:
- Human-approved action chosen from MCP UI after inspection.

Columns:
- id TEXT PRIMARY KEY
- qc_inspection_id TEXT NOT NULL
- qc_hold_batch_id TEXT NOT NULL
- action TEXT NOT NULL
- approved_by TEXT
- reason TEXT
- created_at TEXT NOT NULL

Action values:
- pass_release
- partial_scrap
- full_scrap

#### qc_replacements

Purpose:
- Link scrap-driven shortage to replacement production orders.

Columns:
- id TEXT PRIMARY KEY
- qc_disposition_id TEXT NOT NULL
- sales_order_id TEXT NOT NULL
- item_id TEXT NOT NULL
- qty_short INTEGER NOT NULL
- qty_replacement INTEGER NOT NULL
- replacement_production_order_id TEXT NOT NULL
- created_at TEXT NOT NULL

### 1.4 New Indexes

- idx_po_qc_required on production_orders(inspection_required, status)
- idx_qc_hold_batch_status on qc_hold_batches(status, created_at)
- idx_qc_hold_line_status on qc_hold_batch_lines(line_status)
- idx_qc_inspection_batch on qc_inspections(qc_hold_batch_id, created_at)
- idx_qc_replacements_so on qc_replacements(sales_order_id)

### 1.5 Referential Rules

- Deletion of production_orders should be restricted when related qc_* records exist.
- qc_hold_batch and qc_hold_batch_line records are immutable history after closed.
- Dispositions are append-only; no hard delete.

### 1.6 Migration Plan

- Add new columns/tables in schema.sql (fresh scenario rebuild model).
- Backfill existing production_orders with inspection_required=0 and inspection_status='none'.
- Add config constants:
  - LOC_SCRAP

---

## 2. Process Design

### 2.1 End-to-End Lifecycle

1. Production order is created and may be flagged inspection_required=1 by scenario logic.
2. Production completes.
3. If inspection_required=1:
- Output is placed into QC hold state and excluded from normal fulfillment.
- Output is not inserted into normal stock yet.
- Create qc_hold_batch and qc_hold_batch_line records.
4. Operator submits image_url with production_order_id.
5. Backend runs image inspection and stores qc_inspections + qc_inspection_findings.
6. MCP UI asks user to choose final disposition.
7. System applies stock/hold updates and records qc_dispositions.
8. If scrap creates shortage, replacement production order is created immediately and linked in qc_replacements.
9. UI shows final inspection + disposition + replacement relationship.

### 2.2 Stock and Allocation Rules

Rule A:
- Stock linked to active QC hold lines must be excluded from shipment allocation and dispatch checks.

Rule B:
- Only released quantities from QC can become shippable (and only then inserted into stock).

Rule C:
- Scrap quantity is recorded as disposed from hold and never inserted into available stock.

Rule D:
- Quantity invariant must hold per hold line after each action.

### 2.3 Disposition Processing

#### pass_release
- Move qty_pending to qty_released.
- Insert released quantity into stock and write qc_hold_release movement.
- Mark line released, batch released if all lines released.
- Update production_orders.inspection_status accordingly.

#### partial_scrap
- Split pending qty into released + scrapped according to UI input.
- Record qc_scrap movement and qc_hold_release movement.
- Insert only released quantity into stock.
- Mark line `partially_released`, batch `partially_released` if any pending qty remains after this action or all lines are now partially released.
- Create replacement immediately for net shortage.

#### full_scrap
- Move all qty_pending to qty_scrapped.
- Record qc_scrap movement.
- Create replacement immediately for full shortage.

### 2.4 Replacement Order Calculation

Inputs:
- scrapped_qty
- available_substitute_qty (if substitution is enabled)
- recipe output batch size for item

Formula:
- qty_short = max(0, scrapped_qty - available_substitute_qty)
- qty_replacement = ceil(qty_short / output_qty) * output_qty

**MVP simplification**: `available_substitute_qty = 0`. The formula therefore simplifies to `qty_short = scrapped_qty`. Existing FG stock is not deducted; the planner absorbs it on the next cycle.

Behavior:
- Create replacement MO immediately when qty_short > 0.
- Link MO ID in qc_replacements.

### 2.5 Failure and Retry Semantics

- Inspection submission is idempotent via a partial unique index on `qc_inspections(qc_hold_batch_id) WHERE status != 'failed'`. If a `completed` inspection exists for the batch, return it. If a `failed` inspection exists, DELETE it and re-run.
- Disposition is idempotent via a `UNIQUE(qc_inspection_id)` constraint on `qc_dispositions`. If a disposition already exists for the inspection, return it without re-applying.
- All disposition operations are transactional:
  - hold line update
  - stock movement writes
  - replacement creation
  - inspection/order status updates

---

## 3. Scenario Generation Design

### 3.1 Objective

Deterministically end a scenario with exactly 3 pending inspection production orders for:
- ELVIS-DUCK-20CM
- MARILYN-DUCK-20CM
- ZOMBIE-DUCK-15CM

### 3.2 Mid-Flow Injection Strategy (Preferred)

During normal scenario generation (not only at the end):

1. Insert three dedicated sales orders for the target SKUs at a chosen day/time in the normal loop.
2. Create production orders with fixed IDs:
- MO-9000 for ELVIS-DUCK-20CM
- MO-9001 for MARILYN-DUCK-20CM
- MO-9002 for ZOMBIE-DUCK-15CM
3. Set inspection_required=1 on those MOs.
4. Continue normal scenario generation (shipping, invoicing, etc.) for all other orders.
5. When these three MOs complete, route their output into qc_hold_batch/qc_hold_batch_line (not normal stock).
6. Keep running normal scenario events after injection so timeline stays realistic.

ID safety:
- Reserve 9000+ range for deterministic QC demo fixtures.
- Assert IDs do not already exist before insertion.

### 3.3 Deterministic Guard Rails

- Use fixed random seed in injection step.
- Use explicit target SKUs and explicit qty values.
- Use explicit while-loop completion checks with upper bound timeout.
- Assert MO-9000/MO-9001/MO-9002 are created successfully.

### 3.4 End-of-Scenario Assertions

Hard assertions (scenario fails if any condition false):

1. Count of production_orders where inspection_required=1 and inspection_status='pending_inspection' is exactly 3.
2. All 3 have status='completed'.
3. SKU set equals {ELVIS-DUCK-20CM, MARILYN-DUCK-20CM, ZOMBIE-DUCK-15CM}.
4. No shipment line references quantities originating from these 3 QC hold batches.

### 3.5 Alternative Fixture Strategy

If daily-flow integration is unstable:
- Keep scenario loop unchanged and run a post-loop fixture step.
- Directly create/complete the three target production orders with fixed IDs.
- Place them in QC hold.
- Run same assertions.

---

## 4. UI Design

Policy:
- No state mutation via UI-only endpoints.
- UI is read-only plus action initiation through MCP tools only.
- Any confirm button in MCP App UI must call an MCP tool, never write state directly.

### 4.1 Required Views

1. QC Queue View
- Show exactly the pending QC orders (3 in demo state).
- Columns: production_order_id, sku, qty_pending, created_at, hold_status.

2. Inspection Detail View
- Show attached image(s).
- Show normalized findings and final decision.
- Show disposition history.

3. Replacement Trace View
- If replacement order created, show replacement production_order_id and quantities.
- Enable click-through from inspected order to replacement order.

### 4.2 UX Flow

1. User opens QC queue.
2. Opens first hold batch.
3. Adds image URL.
4. Runs inspection.
5. Sees findings summary.
6. Chooses disposition in MCP UI that submits through MCP tool call.
7. Sees final state and replacement link (if created).

### 4.3 UI Data Needs

- pending inspection list endpoint/data feed
- hold batch detail with images
- inspection findings and confidence
- disposition action result
- replacement links

---

## 5. MCP Tool Design

Naming follows existing snake_case conventions.

### 5.1 Read Tools

#### qc_list_pending_batches

Purpose:
- List QC hold batches waiting for inspection.

Arguments:
- production_order_ids: Optional[List[str]]
- sales_order_ids: Optional[List[str]]
- item_ids: Optional[List[str]]
- status_values: Optional[List[str]]
- limit: int = 100

#### qc_get_batch

Purpose:
- Get one hold batch with lines, images, latest inspection, and replacement links.

Arguments:
- qc_hold_batch_id: str

#### qc_get_inspection

Purpose:
- Get one inspection run with findings.

Arguments:
- qc_inspection_id: str

### 5.2 Mutating Tools

#### qc_attach_images

Purpose:
- Attach image URLs to a hold batch/line.

Arguments:
- qc_hold_batch_id: str
- qc_hold_batch_line_ids: Optional[List[str]]
- image_urls: List[str]

#### qc_run_inspection

Purpose:
- Run model inference for a hold batch and persist normalized findings.

Arguments:
- qc_hold_batch_id: str
- production_order_id: str
- image_urls: Optional[List[str]]
- check_completeness: bool = True
- notes: Optional[str]

Returns:
- qc_inspection_id
- decision_recommendation
- finding_summary

#### qc_apply_disposition

Purpose:
- Apply user-selected action after inspection.

Arguments:
- qc_inspection_id: str
- action: str
- line_actions: Optional[List[Dict]]
- reason: Optional[str]

Notes:
- Should use MCP confirmation UI.
- Action is irreversible for scrap quantities.

### 5.3 Tool Interaction Pattern

1. List pending batches.
2. Attach images.
3. Run inspection.
4. Show findings.
5. Apply disposition via confirmed UI.
6. Return updated batch state with replacement link if any.

---

## 6. LLM Prompt Design For Image Analysis

### 6.1 Inputs

- production_order_id
- expected SKU/name
- expected visible components from recipe context
- inspected image URL(s) from operator
- strict output schema instruction

### 6.2 Output Schema (Strict JSON)

Top-level keys:
- product_match
- quality_defects
- completeness_defects
- severity_summary
- confidence_overall
- uncertainty_flags
- recommended_decision

Example normalized shape:
- product_match: {is_match: bool, confidence: float, rationale: str}
- quality_defects: [{type, severity, confidence, description, image_ref, location_hint}]
- completeness_defects: [{part_name, severity, confidence, description, image_ref}]
- recommended_decision: one of [pass, partial_scrap, full_scrap]

### 6.3 Prompt Constraints

- Return valid JSON only.
- Do not invent unseen parts.
- If uncertain due to image quality, raise uncertainty_flags and lower confidence.
- Keep explanations short and evidence-focused.

### 6.4 Prompt Template (Ready To Use)

System prompt:

You are a factory quality-control vision inspector.
You must compare the inspected product image(s) against the expected product specification and optional reference image.
Return strict JSON only, matching the schema exactly.
If uncertain, set uncertainty flags and reduce confidence.
Never output markdown.

User prompt template:

Inspection context:
- production_order_id: {{production_order_id}}
- expected_sku: {{expected_sku}}
- expected_product_name: {{expected_product_name}}
- expected_visible_parts: {{expected_visible_parts_json_array}}

Tasks:
1. Confirm whether inspected product matches expected product.
2. Detect quality defects (paint, shape, assembly, packaging).
3. Detect completeness defects (missing visible parts).
4. Assign severity per finding: critical|major|minor.
5. Return confidence per finding and overall confidence.
6. Recommend one decision: pass|partial_scrap|full_scrap.

Required JSON schema:
{
  "product_match": {
    "is_match": true,
    "confidence": 0.0,
    "rationale": ""
  },
  "quality_defects": [
    {
      "type": "paint_defect|shape_defect|assembly_defect|packaging_defect",
      "severity": "critical|major|minor",
      "confidence": 0.0,
      "description": "",
      "image_ref": "reference|inspect_1|inspect_2",
      "location_hint": ""
    }
  ],
  "completeness_defects": [
    {
      "part_name": "",
      "severity": "critical|major|minor",
      "confidence": 0.0,
      "description": "",
      "image_ref": "inspect_1|inspect_2"
    }
  ],
  "severity_summary": {
    "critical_count": 0,
    "major_count": 0,
    "minor_count": 0
  },
  "confidence_overall": 0.0,
  "uncertainty_flags": [""],
  "recommended_decision": "pass|partial_scrap|full_scrap"
}

Validation rules:
- confidence fields must be between 0 and 1.
- if image quality is insufficient, include uncertainty_flags and do not return pass when confidence_overall < 0.6.
- if product mismatch confidence >= 0.7, recommended_decision should not be pass.

### 6.5 Two-Image Support In Chat Completions

Yes, OpenAI-compatible chat completions support multiple images in one request for vision-capable models.

Pattern:
- include one reference image and one or more inspected images in the same user message content array.

Example payload structure:

messages = [
  {"role": "system", "content": "..."},
  {
    "role": "user",
    "content": [
      {"type": "text", "text": "Inspection context ..."},
      {"type": "image_url", "image_url": {"url": "{{reference_image_url}}"}},
      {"type": "image_url", "image_url": {"url": "{{inspect_image_url_1}}"}},
      {"type": "image_url", "image_url": {"url": "{{inspect_image_url_2}}"}}
    ]
  }
]

Notes:
- Ensure chosen model supports vision input.
- Keep image count small (1 reference + 1..2 inspected) for latency and determinism.

### 6.6 Decision Mapping Layer

Model recommendation is advisory.
Final action is selected by user through disposition UI, with server-side validation.

---

## 7. Service Layer Changes

### 7.1 New Service Module

Add services/qc.py for:
- hold batch creation on production completion
- image attachment
- inspection orchestration
- finding normalization
- disposition application
- replacement creation linkage

### 7.2 Integration Touchpoints

- services/production.py
- services/simulation.py
- services/fulfillment.py
- services/logistics.py
- services/inventory.py

Required behavior:
- production completion path must route inspection-required output to QC hold behavior.
- fulfillment allocation/dispatch paths must exclude QC-held quantities.

---

## 8. Testing Strategy

### 8.1 Unit Tests

- hold line quantity invariant checks
- replacement qty rounding
- idempotent disposition replay
- model output normalization and validation

### 8.2 Integration Tests

- end-to-end: produce -> hold -> inspect -> disposition -> replacement
- shipping exclusion: QC-held stock not dispatchable
- partial scrap updates and trace links

### 8.3 Scenario Contract Tests

- final scenario contains exactly 3 pending inspections for target SKUs
- all three are completed production orders
- none are shipped before inspection

---

## 9. Rollout Plan

### Phase 1

- Data model foundation
- QC hold creation
- Pending queue + image attach + inspection run
- Disposition actions: pass_release, partial_scrap, full_scrap

### Phase 2

- Full disposition actions (pass/partial/full scrap)
- Immediate replacement creation
- UI replacement linkage

### Phase 3

- Enhanced analytics and complaint feedback loop
- stricter confidence calibration and model tuning

---

## 10. Risks and Mitigations

1. Accidental shipment of QC-held stock
- Mitigation: enforce hold exclusion in all allocation/dispatch paths, with integration tests.

2. Duplicate side effects on retries
- Mitigation: idempotency keys and transactional disposition operations.

3. Non-deterministic demo data
- Mitigation: deterministic tail-step generation and hard assertions.

4. Low-quality images causing noisy findings
- Mitigation: uncertainty flags and user-driven final disposition.

---

## 11. Definition of Done

Implementation is considered done when:

1. Scenario run ends with exactly 3 pending inspections for Elvis, Marilyn, Zombie.
2. UI shows these 3 pending QC orders.
3. User can inspect one order by attaching image URL and running analysis.
4. UI shows image, findings, and selected disposition.
5. If scrap causes shortage, replacement order is automatically created and visible.
6. QC-held quantities are never shipped before release.
