# Stock Movement Tracking

> **Status: IMPLEMENTED.**
> The `stock_movements` table and all logging are live.
> Every stock addition (production, purchase, initial setup) and deduction
> (shipment dispatch, production ingredient consumption) is recorded.

## Problem Statement

The current system has a **visibility gap** between production intent and actual fulfillment:

### Current Issues

1. **Misleading Gantt Charts**: Sales orders show linked production orders, but the finished goods may come from completely different production runs
2. **Zombie Production Orders**: Orders can be fulfilled from existing stock while their production orders remain stuck "waiting" forever (e.g., SO-1172 ships while MO-0297/MO-0298 wait indefinitely for Black Dye)
3. **No Audit Trail**: When stock is depleted, there's no way to trace which shipment consumed which production output
4. **FIFO Confusion**: The system uses FIFO (first-in-first-out) for stock deduction, but this relationship is invisible

### Example from Real Data

```
SO-1172 (Sept 14)
├─ Creates: MO-0297 (waiting - no Black Dye)
├─ Creates: MO-0298 (waiting - no Black Dye)
└─ Ships: SHIP-1012 (Sept 25) ✓

Wait, how did it ship if production is blocked?

Reality: SHIP-1012 consumed stock from:
  - STK-0468 (10 units from MO-0224 for SO-1143)
  - STK-0469 (10 units from MO-0229 for SO-1145)
```

Without tracking, this looks broken. With tracking, it's perfectly clear.

---

## Solution: Stock Movement Tracking

Track **every stock transaction** with full lineage: what came in, what went out, and which specific stock records were affected.

### Key Principles

1. **Atomic Movements**: Every stock change is logged as a movement record
2. **Reference Tracking**: Every movement links to its source (production order, purchase order, shipment, etc.)
3. **FIFO Enforcement**: Stock deduction uses oldest stock first, and movements record this
4. **Stock Record Granularity**: Maintain separate stock records for each production/receipt batch
5. **No Serial Numbers**: Track at the batch/lot level, not individual items (overkill for rubber ducks)

---

## Database Schema

### New Table: `stock_movements`

```sql
CREATE TABLE IF NOT EXISTS stock_movements (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    item_id TEXT NOT NULL,
    movement_type TEXT NOT NULL,  -- 'production_in', 'purchase_in', 'shipment_out', 'production_consume', 'adjustment'
    qty INTEGER NOT NULL,          -- Positive for additions, negative for deductions
    stock_id TEXT NOT NULL,        -- Which stock record was affected
    reference_type TEXT,           -- 'production_order', 'purchase_order', 'shipment', 'adjustment'
    reference_id TEXT,             -- MO-0320, PO-0123, SHIP-1014, etc.
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_stock_movements_stock ON stock_movements(stock_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_reference ON stock_movements(reference_type, reference_id);
```

### Modified Approach: Stock Records Stay Separate

**Keep current schema**: Each production completion or purchase receipt creates a **new** `stock` record. Don't merge into existing records.

**Why**: Preserves batch identity for traceability

```sql
-- Current stock table (no changes needed)
CREATE TABLE IF NOT EXISTS stock (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    warehouse TEXT NOT NULL,
    location TEXT NOT NULL,
    on_hand INTEGER NOT NULL
);
```

---

## Implementation

### 1. Production Completion (ADD Stock)

**Location**: `services/production.py` → `complete_order()`

`complete_order()` already fetches `sim_time` above the stock insert. Add
the movement INSERT immediately after the existing stock INSERT.

**Current Code** (lines ~256-257):
```python
stock_id = generate_id(conn, "STK", "stock")
conn.execute("INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)", (stock_id, order["item_id"], warehouse, location, qty_produced))
conn.commit()
```

**New Code**:
```python
stock_id = generate_id(conn, "STK", "stock")
conn.execute("INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)", (stock_id, order["item_id"], warehouse, location, qty_produced))

# Log the stock movement
movement_id = generate_id(conn, "MOV", "stock_movements")
conn.execute(
    "INSERT INTO stock_movements (id, timestamp, item_id, movement_type, qty, stock_id, reference_type, reference_id) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    (movement_id, sim_time, order["item_id"], "production_in", qty_produced, stock_id, "production_order", production_order_id)
)
conn.commit()
```

**Also Update**: `services/simulation.py` → `advance_time()` — Side-effect 2
has **two** code paths that insert stock directly (Phase A: operation-tick
completion, Phase B: safety-net force-completion). Both must log a movement
after their `INSERT INTO stock`.

### 2. Purchase Receipt (ADD Stock)

**Location**: `services/purchase.py` → `receive()`

**Current Code** (lines ~62-63):
```python
stock_id = generate_id(conn, "STK", "stock")
conn.execute("INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)", (stock_id, po["item_id"], warehouse, location, po["qty"]))
conn.commit()
```

**New Code**:
```python
stock_id = generate_id(conn, "STK", "stock")
conn.execute("INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)", (stock_id, po["item_id"], warehouse, location, po["qty"]))

# Log the stock movement
movement_id = generate_id(conn, "MOV", "stock_movements")
conn.execute(
    "INSERT INTO stock_movements (id, timestamp, item_id, movement_type, qty, stock_id, reference_type, reference_id) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    (movement_id, sim_time, po["item_id"], "purchase_in", po["qty"], stock_id, "purchase_order", purchase_order_id)
)
conn.commit()
```

### 3. Stock Deduction (REMOVE Stock)

**Location**: `services/inventory.py` → `deduct_stock()`

**Current Signature**: `deduct_stock(item_id: str, qty: int, conn=None) -> Dict[str, Any]`

The function uses FIFO across stock rows (oldest `id` first). It **deletes**
rows that reach zero on-hand and returns `deducted_from` (list of
`{stock_id, warehouse, location, qty_taken}`).

**New Signature** (add reference tracking):
```python
def deduct_stock(item_id: str, qty: int, conn=None,
                 reference_type: str = None, reference_id: str = None) -> Dict[str, Any]:
```

Inside the FIFO loop, after each UPDATE/DELETE, insert a movement:
```python
        # Log the stock movement (negative qty for deduction)
        movement_id = generate_id(conn_or_c, "MOV", "stock_movements")
        conn_or_c.execute(
            "INSERT INTO stock_movements (id, timestamp, item_id, movement_type, qty, stock_id, reference_type, reference_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (movement_id, sim_time, item_id, "shipment_out", -take, row["id"], reference_type, reference_id)
        )
```

> **Note**: The `movement_type` should be context-aware: use `"shipment_out"`
> when the reference is a shipment and `"production_consume"` when materials
> are consumed by a production order. A simple mapping from `reference_type` works.

### 4. Update Logistics Service (Shipment Dispatch)

**Location**: `services/logistics.py` → `dispatch_shipment()`

**Current Code** (line ~90):
```python
for line in lines:
    inventory_service.deduct_stock(line["item_id"], line["qty"], conn=conn)
```

**New Code**:
```python
for line in lines:
    inventory_service.deduct_stock(
        line["item_id"],
        line["qty"],
        conn=conn,
        reference_type="shipment",
        reference_id=shipment_id
    )
```

### 5. Update Production Service (Material Deduction)

**Location**: `services/production.py` → `start_order()`

**Current Code** (line ~231):
```python
for ing in ingredients:
    inventory_service.deduct_stock(ing["input_item_id"], ing["input_qty"], conn=conn)
```

**New Code**:
```python
for ing in ingredients:
    inventory_service.deduct_stock(
        ing["input_item_id"],
        ing["input_qty"],
        conn=conn,
        reference_type="production_order",
        reference_id=production_order_id
    )
```

### 6. Update Simulation Service (Auto-Complete)

**Location**: `services/simulation.py` → `advance_time()` — Side-effect 2

Both Phase A (operation-tick completion) and Phase B (safety-net) contain
a bare `INSERT INTO stock`. After each, add:

```python
movement_id = generate_id(conn, "MOV", "stock_movements")
conn.execute(
    "INSERT INTO stock_movements (id, timestamp, item_id, movement_type, qty, stock_id, reference_type, reference_id) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    (movement_id, new_time, mo["item_id"], "production_in", mo["output_qty"], stock_id, "production_order", mo["id"])
)
```

### 7. Update Scenario Base Setup (Initial Stock)

**Location**: `scenarios/base_setup.py`

After the loop that creates initial `stock` rows, add synthetic
`adjustment` movements so the backfill query (Phase 4) is not needed:

```python
movement_id = generate_id(conn, "MOV", "stock_movements")
conn.execute(
    "INSERT INTO stock_movements (id, timestamp, item_id, movement_type, qty, stock_id, reference_type, reference_id, notes) "
    "VALUES (?, ?, ?, 'adjustment', ?, ?, 'backfill', NULL, 'Initial stock from scenario setup')",
    (movement_id, scenario_start, item_id, qty, stock_id)
)
```

---

## Querying Stock Movements

### Trace Shipment Source

**"Where did the units in SHIP-1012 come from?"**

```sql
SELECT 
    sm.stock_id,
    sm.qty as qty_consumed,
    -- Find what produced this stock
    sm_in.reference_type as source_type,
    sm_in.reference_id as source_id,
    sm_in.timestamp as produced_at
FROM stock_movements sm
LEFT JOIN stock_movements sm_in 
    ON sm.stock_id = sm_in.stock_id 
    AND sm_in.movement_type IN ('production_in', 'purchase_in')
WHERE sm.reference_type = 'shipment'
  AND sm.reference_id = 'SHIP-1012'
ORDER BY sm.timestamp;
```

### Trace Production Destination

**"Where did the output from MO-0320 go?"**

```sql
SELECT 
    sm_out.reference_type as consumed_by_type,
    sm_out.reference_id as consumed_by_id,
    sm_out.qty as qty_consumed,
    sm_out.timestamp as consumed_at
FROM stock_movements sm_in
JOIN stock_movements sm_out ON sm_in.stock_id = sm_out.stock_id
WHERE sm_in.reference_type = 'production_order'
  AND sm_in.reference_id = 'MO-0320'
  AND sm_out.movement_type = 'shipment_out'
ORDER BY sm_out.timestamp;
```

### Full Sales Order Flow

**"Show complete flow for SO-1172"**

```sql
WITH so_production AS (
    -- Production orders created for this SO
    SELECT id, item_id, status, completed_at, qty_produced
    FROM production_orders
    WHERE sales_order_id = 'SO-1172'
),
so_shipments AS (
    -- Shipments for this SO
    SELECT s.id, s.dispatched_at, sl.item_id, sl.qty
    FROM sales_order_shipments sos
    JOIN shipments s ON sos.shipment_id = s.id
    JOIN shipment_lines sl ON s.id = sl.shipment_id
    WHERE sos.sales_order_id = 'SO-1172'
),
shipment_sources AS (
    -- Where shipment stock came from
    SELECT 
        ss.id as shipment_id,
        sm_in.reference_id as source_production_order,
        sm_in.timestamp as produced_at,
        -sm_out.qty as qty_used
    FROM so_shipments ss
    JOIN stock_movements sm_out 
        ON sm_out.reference_id = ss.id 
        AND sm_out.reference_type = 'shipment'
    JOIN stock_movements sm_in 
        ON sm_in.stock_id = sm_out.stock_id
        AND sm_in.movement_type = 'production_in'
)
SELECT 
    'Planned Production' as flow_type,
    sp.id as entity_id,
    sp.status,
    sp.completed_at as timestamp,
    sp.qty_produced as qty
FROM so_production sp
UNION ALL
SELECT 
    'Actual Source' as flow_type,
    ss.source_production_order as entity_id,
    'completed' as status,
    ss.produced_at as timestamp,
    ss.qty_used as qty
FROM shipment_sources ss
ORDER BY timestamp;
```

---

## Benefits

### 1. **Accurate Gantt Charts**

Display two types of connections:
- **Planned** (dotted): SO → production orders created for it
- **Actual** (solid): production → stock → shipment

### 2. **Debugging Production Issues**

Easily identify:
- Zombie production orders (created but never used)
- Material shortages causing delays
- Stock cannibalization (one order using another's stock)

### 3. **Performance Metrics**

Calculate:
- **Stock age**: How long between production and consumption
- **Fulfillment accuracy**: % of orders shipped from their own production
- **Waste detection**: Production that was never shipped

### 4. **Audit Compliance**

Full traceability for:
- Quality issues: "Which shipments received items from batch STK-0468?"
- Recall scenarios: "Trace all units from production run MO-0224"
- Financial audits: "Verify COGS calculation with actual stock flows"

---

## Migration Strategy

### Phase 1: Add Schema (Non-Breaking)

```sql
-- Add the table (safe, doesn't affect existing code)
CREATE TABLE IF NOT EXISTS stock_movements ( ... );
CREATE INDEX ... ;
```

### Phase 2: Update Stock Addition Points

1. `services/production.py` → `complete_order()`
2. `services/purchase.py` → `receive()`
3. `services/simulation.py` → `advance_time()` (both Phase A and Phase B)
4. `scenarios/base_setup.py` → initial stock rows

After this phase: New stock additions are tracked, but deductions aren't.

### Phase 3: Update Stock Deduction

1. Modify `services/inventory.py` → `deduct_stock()` signature (add `reference_type`, `reference_id`)
2. Update all callers:
   - `services/logistics.py` → `dispatch_shipment()`
   - `services/production.py` → `start_order()`

After this phase: Full tracking active.

### Phase 4: Regenerate Scenario

Run `python -m scenarios --only s01` to regenerate the demo database with
full movement data from the start. No manual backfill needed.

---

## Future Enhancements

### 1. **Stock Aging Reports**

```sql
SELECT 
    i.sku,
    s.id as stock_id,
    s.on_hand,
    sm.timestamp as received_at,
    julianday('now') - julianday(sm.timestamp) as age_days
FROM stock s
JOIN items i ON s.item_id = i.id
JOIN stock_movements sm ON s.id = sm.stock_id AND sm.movement_type IN ('production_in', 'purchase_in')
WHERE s.on_hand > 0
ORDER BY age_days DESC;
```

### 2. **Smart Stock Reservation**

Instead of hard FIFO, reserve specific stock for orders:

```sql
CREATE TABLE IF NOT EXISTS stock_reservations (
    id TEXT PRIMARY KEY,
    stock_id TEXT NOT NULL,
    sales_order_id TEXT NOT NULL,
    qty_reserved INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
```

### 3. **Lot/Batch Numbers**

Add optional `lot_number` to stock records for products requiring batch tracking (food, pharma, etc.)

---

## Testing Strategy

### Unit Tests

1. **Test: Stock Addition Creates Movement**
   - Complete production order
   - Verify stock record created
   - Verify movement record created with correct reference

2. **Test: Stock Deduction Creates Movements (FIFO)**
   - Create 3 stock records
   - Deduct quantity spanning 2 records
   - Verify 2 movement records created
   - Verify oldest stock depleted first

3. **Test: Shipment Traceability**
   - Create production order → stock
   - Ship from that stock
   - Query movements to trace shipment → stock → production

### Integration Tests

1. **Test: Full Order Lifecycle**
   - Create SO → production → shipment
   - Verify complete movement chain
   - Verify FIFO consumption

2. **Test: Cross-Order Fulfillment**
   - Create SO-A with production
   - Create SO-B without production
   - Ship SO-B from SO-A's stock
   - Verify movements show cross-order fulfillment

---

## Rollout Checklist

- [x] Add `stock_movements` table + indexes to `schema.sql`
- [x] Update `services/inventory.py` → `deduct_stock()` — add `reference_type`/`reference_id` params + movement INSERT
- [x] Update `services/production.py` → `complete_order()` — movement INSERT after stock INSERT
- [x] Update `services/production.py` → `start_order()` — pass reference context to `deduct_stock()`
- [x] Update `services/purchase.py` → `receive()` — movement INSERT after stock INSERT
- [x] Update `services/simulation.py` → `advance_time()` — movement INSERT in Phase A and Phase B
- [x] Update `services/logistics.py` → `dispatch_shipment()` — pass reference context to `deduct_stock()`
- [x] Update `scenarios/base_setup.py` → initial stock — log adjustment movements
- [x] Regenerate with `python -m scenarios --only s01` and verify movements
- [ ] Create helper queries in `services/inventory.py` (trace shipment, trace production)
- [ ] Update Gantt chart visualization to show actual flows (planned vs actual lines)
- [ ] Document in API/MCP tools if needed

---

## Conclusion

Stock movement tracking bridges the gap between **intent** (production planned for an order) and **reality** (where stock actually came from). This is essential for:

1. **Transparency**: Understand actual fulfillment flows
2. **Debugging**: Identify why orders are delayed or stuck
3. **Optimization**: Find inefficiencies in production scheduling
4. **Compliance**: Full audit trail for quality and financial purposes

The implementation is straightforward and non-invasive, adding logging at key transaction points without disrupting existing logic.
