# AI-Assisted Shipping QC Concept

## Scope

This document defines the high-level process and demo data strategy.

It intentionally does not define MCP tool contracts or database schema.

---

## QC Agent Process

1. A production order can be marked with inspection_required.
2. When that production order is completed, its output is not moved into normal warehouse availability.
3. The output stays in a QC hold state.
4. QC operator goes to the hold location, takes a picture of a batch, and provides:
   - production_order_id
   - image_url
5. Backend analyzes the image in the context of that production order.
6. Backend returns a decision and executes downstream actions.

Decision outcomes:
- pass: release held quantity for normal fulfillment
- partial_scrap: scrap part of held quantity and release the rest
- full_scrap: scrap all held quantity
- manual_review: keep on hold until explicit decision

If scrap causes shortage against committed demand, replacement production orders are created with batch-size rules.

---

## Scheduling and Inventory Behavior

Important rule for this concept:
- There is no separate physical inspection stack in the model.

Behavioral equivalent:
- Inspection-required completed production orders must stay out of normal scheduling and fulfillment flow until inspection is done.

Operationally this means:
- Not available to shipment allocation
- Not available to auto-dispatch
- Not counted as free finished goods
- Still visible in a hold queue for QC processing

---

## Underlying Demo Data Needed

At high level, the demo needs these data concepts:

1. Production order inspection flag
- inspection_required on production order

2. Hold state tracking
- whether completed output is pending inspection, released, or blocked
- held quantities by item

3. Image evidence linkage
- image_url associated with production_order_id and hold batch/line

4. Inspection result record
- decision, confidence summary, timestamp, and reason

5. Disposition quantities
- qty_released, qty_scrapped, qty_pending

6. Replenishment linkage
- relation from scrapped quantities to replacement production orders

Quantity integrity rule:
- qty_released + qty_scrapped + qty_pending = qty_on_hold

---

## Scenario Strategy For Reliable Demo Data

Goal:
- Ensure there are exactly 3 completed production orders requiring inspection on the last day of the scenario, for:
  - ELVIS-DUCK-20CM
  - MARILYN-DUCK-20CM
  - ZOMBIE-DUCK-15CM

Recommended approach:

1. Add a deterministic end-of-scenario step
- After normal scenario flow, run a dedicated tail step that creates inspection candidates.

2. Create dedicated demand for the 3 target SKUs
- Create sales orders that force production for those items.
- Mark resulting production orders with inspection_required.

3. Advance simulation just enough to complete production
- Advance time with side effects until those production orders are completed.

4. Stop before shipping/invoicing consumes them
- Do not run fulfillment actions after this tail step.
- Keep these outputs in inspection hold state.

Note:
- The freeze is a safety guard for deterministic demos before QC-hold exclusion is fully enforced.
- Once allocation/dispatch logic reliably excludes QC-hold quantities, fulfillment can continue and the 3 inspection orders will remain protected.

5. Validate hard conditions at scenario end
- Exactly 3 production orders flagged inspection_required
- All 3 in completed status
- All 3 pending inspection (not released, not shipped)

This gives deterministic demo readiness without relying on random order mix.

---

## Alternative Scenario Strategy

If integrating into daily flow is too fragile:

1. Append a final fixture-like block at scenario end.
2. Create 3 production orders directly for the target recipes.
3. Mark them inspection_required immediately.
4. Advance simulation to complete them.
5. Place them in pending inspection hold.

This is less realistic than organic sales flow, but much more stable for demos.

---

## Locked Decisions For Next Iteration

1. Where to set inspection_required
- Scenario generation only.

2. Inspection granularity
- Produced batch line.

3. Disposition execution
- After image inspection, show MCP UI so user chooses next action.

4. Replacement trigger policy
- Create replacement immediately on scrap.

5. End-of-scenario contract
- Guarantee exactly 3 pending inspections.

---

## Acceptance Criteria For Scenario Output

End-of-scenario checks must pass for the demo dataset to be valid:

1. Exactly 3 production orders are flagged inspection_required.
2. Those 3 orders are completed.
3. Those 3 orders are still pending inspection (not released to normal fulfillment).
4. The 3 target SKUs are present in this pending-inspection set:
  - ELVIS-DUCK-20CM
  - MARILYN-DUCK-20CM
  - ZOMBIE-DUCK-15CM
5. No more and no less than 3 pending inspections are present at scenario end.

---

## UI Note

Existing UI should support the following for the QC demo:

1. Show the 3 production orders waiting for QC.
2. For inspected orders, show the attached image and the decision taken.
3. If a replacement order is created, make that relationship visible from the inspected order.

---

## LLM Result Checklist (Image Analysis)

This is what the model should return from an image when paired with production_order_id.

Product correctness:
- expected product match or mismatch
- confidence of identification

Quality defects:
- paint defects
- shape defects
- assembly defects
- packaging defects

Completeness defects:
- missing installed parts
- suspected missing parts with confidence

Severity:
- critical
- major
- minor

Evidence:
- finding-to-image mapping
- optional location hints in image
- per-finding confidence

Uncertainty:
- low-visibility or low-confidence flags
