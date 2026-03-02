# Work Centers — Capacity Constraints for Production

## Overview

Production orders currently run fully in parallel with no resource contention.
This feature adds **work centers** — shared production resources with finite
capacity (max concurrent operations).  When a work center is full, operations
that need it queue until a slot frees up, creating realistic bottlenecks.

### Work Center Definitions

| Work Center | Operations mapped | Slots | Notes |
|-------------|-------------------|-------|-------|
| `MOLDING`   | Mold injection | 3 | Bottleneck at entry — every recipe needs this |
| `PAINTING`  | All `Paint *`, `Base coat` | 4 | Largest bottleneck — most recipes have 1–3 paint steps |
| `CURING`    | Cooling, Curing process | 2 | Passive wait time |
| `ASSEMBLY`  | Assemble parts, Attach horn | 2 | Product-specific manual work |
| `QC`        | Quality check | 2 | Inspection step |
| `PACKAGING` | Pack into box/boxes | 3 | Rarely a bottleneck |

---

## Files to Change

### 1. `schema.sql` — Add `work_centers` table and `work_center` columns

#### 1a. Add `work_center TEXT` column to `production_operations`

Between `duration_hours` and `status`:

```sql
-- BEFORE:
CREATE TABLE IF NOT EXISTS production_operations (
    id TEXT PRIMARY KEY,
    production_order_id TEXT NOT NULL,
    recipe_operation_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    operation_name TEXT NOT NULL,
    duration_hours REAL NOT NULL,
    status TEXT DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT
);

-- AFTER:
CREATE TABLE IF NOT EXISTS production_operations (
    id TEXT PRIMARY KEY,
    production_order_id TEXT NOT NULL,
    recipe_operation_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    operation_name TEXT NOT NULL,
    duration_hours REAL NOT NULL,
    work_center TEXT,
    status TEXT DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT
);
```

#### 1b. Add `work_center TEXT` column to `recipe_operations`

Between `duration_hours` and `notes`:

```sql
-- BEFORE:
CREATE TABLE IF NOT EXISTS recipe_operations (
    id TEXT PRIMARY KEY,
    recipe_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    operation_name TEXT NOT NULL,
    duration_hours REAL NOT NULL,
    notes TEXT
);

-- AFTER:
CREATE TABLE IF NOT EXISTS recipe_operations (
    id TEXT PRIMARY KEY,
    recipe_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    operation_name TEXT NOT NULL,
    duration_hours REAL NOT NULL,
    work_center TEXT,
    notes TEXT
);
```

#### 1c. Add `work_centers` table

Insert before the `-- Recipe operations (production steps)` comment:

```sql
-- Work centers define shared production resources with finite capacity
CREATE TABLE IF NOT EXISTS work_centers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    max_concurrent INTEGER NOT NULL DEFAULT 1,
    description TEXT
);
```

#### 1d. Add index for work center queries

After the existing `idx_po_ops` index:

```sql
CREATE INDEX IF NOT EXISTS idx_po_ops_wc ON production_operations(work_center, status);
```

---

### 2. `config.py` — Add work center capacity defaults

Append at end of file:

```python
# Work center capacity (max concurrent operations per center)
WORK_CENTER_CAPACITY = {
    "MOLDING": 3,
    "PAINTING": 4,
    "CURING": 2,
    "ASSEMBLY": 2,
    "QC": 2,
    "PACKAGING": 3,
}
```

---

### 3. `scenarios/base_setup.py` — Tag operations with work centers

#### 3a. Update `_std_recipe()` operations

Change from `(name, hours)` tuples to `(name, hours, work_center)`:

```python
# BEFORE:
    operations = [
        ("Mold injection", round(0.5 + size_cm * 0.05, 2)),
        ("Cooling", 0.5),
    ]
    for item_id_dye, qty, _uom in dyes:
        colour = item_id_dye.replace("ITEM-", "").replace("-DYE", "").replace("-", " ").title()
        operations.append((f"Paint {colour.lower()}", round(0.3 + qty / 300, 2)))
    operations.extend(extra_ops or [])
    operations.append(("Quality check", 0.25))
    operations.append(("Pack into box", 0.25))

# AFTER:
    operations = [
        ("Mold injection", round(0.5 + size_cm * 0.05, 2), "MOLDING"),
        ("Cooling", 0.5, "CURING"),
    ]
    for item_id_dye, qty, _uom in dyes:
        colour = item_id_dye.replace("ITEM-", "").replace("-DYE", "").replace("-", " ").title()
        operations.append((f"Paint {colour.lower()}", round(0.3 + qty / 300, 2), "PAINTING"))
    operations.extend(extra_ops or [])
    operations.append(("Quality check", 0.25, "QC"))
    operations.append(("Pack into box", 0.25, "PACKAGING"))
```

#### 3b. Update all 6 hand-crafted recipes

Elvis:
```python
    "operations": [
        ("Mold injection", 1.5, "MOLDING"),
        ("Cooling", 0.5, "CURING"),
        ("Paint hair black", 0.75, "PAINTING"),
        ("Paint details yellow", 0.5, "PAINTING"),
        ("Pack into box", 0.25, "PACKAGING"),
    ],
```

Classic:
```python
    "operations": [
        ("Mold injection", 1.0, "MOLDING"),
        ("Paint yellow", 0.75, "PAINTING"),
        ("Quality check", 0.5, "QC"),
        ("Pack into boxes", 0.25, "PACKAGING"),
    ],
```

Robot:
```python
    "operations": [
        ("Mold injection", 2.0, "MOLDING"),
        ("Curing process", 1.0, "CURING"),
        ("Base coat", 1.5, "PAINTING"),
        ("Paint robot details", 1.0, "PAINTING"),
        ("Assemble parts", 0.5, "ASSEMBLY"),
        ("Quality check", 0.25, "QC"),
        ("Pack into box", 0.25, "PACKAGING"),
    ],
```

Pirate:
```python
    "operations": [
        ("Mold injection", 1.5, "MOLDING"),
        ("Cooling", 0.5, "CURING"),
        ("Paint base yellow", 0.75, "PAINTING"),
        ("Paint pirate details", 0.75, "PAINTING"),
        ("Quality check", 0.25, "QC"),
        ("Pack into box", 0.25, "PACKAGING"),
    ],
```

Ninja:
```python
    "operations": [
        ("Mold injection", 1.25, "MOLDING"),
        ("Cooling", 0.5, "CURING"),
        ("Paint ninja outfit", 1.0, "PAINTING"),
        ("Quality check", 0.75, "QC"),
        ("Pack into box", 0.25, "PACKAGING"),
    ],
```

Unicorn:
```python
    "operations": [
        ("Mold injection", 1.75, "MOLDING"),
        ("Cooling", 0.75, "CURING"),
        ("Paint rainbow colors", 1.5, "PAINTING"),
        ("Attach horn", 0.5, "ASSEMBLY"),
        ("Quality check", 0.25, "QC"),
        ("Pack into box", 0.25, "PACKAGING"),
    ],
```

#### 3c. Update the INSERT loop

```python
# BEFORE:
            for seq, (op_name, dur) in enumerate(rdef["operations"], start=1):
                op_counter += 1
                conn.execute(
                    "INSERT INTO recipe_operations (id, recipe_id, sequence_order, operation_name, duration_hours) VALUES (?,?,?,?,?)",
                    (f"OP-{op_counter:04d}", rcp_id, seq, op_name, dur),
                )

# AFTER:
            for seq, (op_name, dur, wc) in enumerate(rdef["operations"], start=1):
                op_counter += 1
                conn.execute(
                    "INSERT INTO recipe_operations (id, recipe_id, sequence_order, operation_name, duration_hours, work_center) VALUES (?,?,?,?,?,?)",
                    (f"OP-{op_counter:04d}", rcp_id, seq, op_name, dur, wc),
                )
```

#### 3d. Seed work center rows

Inside `populate()`, after inserting recipes and before `# ---- Initial raw material stock ----`:

```python
        # ---- Work centers ----
        for wc_name, max_conc in config.WORK_CENTER_CAPACITY.items():
            conn.execute(
                "INSERT INTO work_centers (id, name, max_concurrent, description) VALUES (?,?,?,?)",
                (f"WC-{wc_name}", wc_name, max_conc, f"{wc_name.title()} work center"),
            )
        logger.info("Inserted %d work centers", len(config.WORK_CENTER_CAPACITY))
```

---

### 4. `services/production.py` — Copy `work_center` in `create_order()` and add capacity logic

#### 4a. Update `create_order()` INSERT

```python
# BEFORE:
        for op in recipe_data["operations"]:
            pop_id = generate_id(conn, "POP", "production_operations")
            conn.execute("INSERT INTO production_operations (id, production_order_id, recipe_operation_id, sequence_order, operation_name, duration_hours, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (pop_id, order_id, op["id"], op["sequence_order"], op["operation_name"], op["duration_hours"], "pending"))

# AFTER:
        for op in recipe_data["operations"]:
            pop_id = generate_id(conn, "POP", "production_operations")
            conn.execute(
                "INSERT INTO production_operations "
                "(id, production_order_id, recipe_operation_id, sequence_order, "
                "operation_name, duration_hours, work_center, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (pop_id, order_id, op["id"], op["sequence_order"],
                 op["operation_name"], op["duration_hours"],
                 op.get("work_center"), "pending"),
            )
```

#### 4b. Update `advance_operations()` — add capacity checking

Replace the `_inner` function body:

```python
    def _inner(c):
        mo = c.execute(
            "SELECT started_at FROM production_orders WHERE id = ?",
            (production_order_id,),
        ).fetchone()
        if not mo or not mo["started_at"]:
            return {"all_done": False, "current_operation": None}

        mo_start = datetime.fromisoformat(mo["started_at"])
        now = datetime.fromisoformat(sim_time)

        ops = dict_rows(c.execute(
            "SELECT id, sequence_order, operation_name, duration_hours, "
            "work_center, status "
            "FROM production_operations WHERE production_order_id = ? "
            "ORDER BY sequence_order",
            (production_order_id,),
        ))
        if not ops:
            return {"all_done": True, "current_operation": None}

        # Pre-fetch work center capacity limits
        wc_rows = c.execute(
            "SELECT name, max_concurrent FROM work_centers"
        ).fetchall()
        wc_capacity = {r["name"]: r["max_concurrent"] for r in wc_rows}

        # Count currently in-progress ops per work center (excluding this MO,
        # since we'll recompute its state)
        wc_usage_rows = c.execute(
            "SELECT work_center, COUNT(*) as cnt "
            "FROM production_operations "
            "WHERE status = 'in_progress' AND work_center IS NOT NULL "
            "AND production_order_id != ? "
            "GROUP BY work_center",
            (production_order_id,),
        ).fetchall()
        wc_used = {r["work_center"]: r["cnt"] for r in wc_usage_rows}

        cursor = mo_start
        current_operation = None
        all_done = True
        blocked = False  # once blocked, all subsequent ops stay pending

        for op in ops:
            if blocked:
                all_done = False
                if current_operation is None:
                    current_operation = op["operation_name"]
                continue

            op_start = cursor
            op_end = cursor + timedelta(hours=op["duration_hours"])

            if now >= op_end:
                # This operation should be completed
                if op["status"] != "completed":
                    c.execute(
                        "UPDATE production_operations SET status = 'completed', "
                        "started_at = ?, completed_at = ? WHERE id = ?",
                        (op_start.isoformat(), op_end.isoformat(), op["id"]),
                    )
                    # Free up work center slot
                    wc = op.get("work_center")
                    if wc and wc in wc_used:
                        wc_used[wc] = max(0, wc_used[wc] - 1)
            elif now >= op_start:
                # Check work center capacity before allowing in_progress
                wc = op.get("work_center")
                if wc and wc in wc_capacity:
                    used = wc_used.get(wc, 0)
                    if used >= wc_capacity[wc]:
                        # Work center full — this op must wait
                        blocked = True
                        all_done = False
                        current_operation = op["operation_name"]
                        # Revert to pending if it was somehow in_progress
                        if op["status"] == "in_progress":
                            c.execute(
                                "UPDATE production_operations "
                                "SET status = 'pending', started_at = NULL "
                                "WHERE id = ?",
                                (op["id"],),
                            )
                        continue

                if op["status"] != "in_progress":
                    c.execute(
                        "UPDATE production_operations SET status = 'in_progress', "
                        "started_at = ? WHERE id = ?",
                        (op_start.isoformat(), op["id"]),
                    )
                # Reserve the slot
                if wc:
                    wc_used[wc] = wc_used.get(wc, 0) + 1
                current_operation = op["operation_name"]
                all_done = False
            else:
                # Future operation — stays pending
                all_done = False
                if current_operation is None:
                    current_operation = op["operation_name"]

            cursor = op_end

        # Update current_operation on the MO header
        c.execute(
            "UPDATE production_orders SET current_operation = ? WHERE id = ?",
            (current_operation, production_order_id),
        )
        return {"all_done": all_done, "current_operation": current_operation}
```

---

### 5. `services/simulation.py` — Process MOs in FIFO order

In `advance_time()` side-effect #2, add `ORDER BY po.started_at` to the
in-progress MO query so older MOs get priority for work center slots:

```python
# BEFORE:
        all_in_progress = conn.execute(
            "SELECT po.id, po.item_id, r.output_qty "
            "FROM production_orders po "
            "JOIN recipes r ON po.recipe_id = r.id "
            "WHERE po.status = 'in_progress'",
        ).fetchall()

# AFTER:
        all_in_progress = conn.execute(
            "SELECT po.id, po.item_id, r.output_qty "
            "FROM production_orders po "
            "JOIN recipes r ON po.recipe_id = r.id "
            "WHERE po.status = 'in_progress' "
            "ORDER BY po.started_at",
        ).fetchall()
```

---

## After Applying

Re-seed:

```bash
source venv/bin/activate
python -m scenarios --only s01
```

## Verification

- Completed MOs: all operations should be `completed` with timestamps
- In-progress MOs during a demand spike: some operations should show as
  `pending` (queued behind work center capacity), not all `in_progress`
- Query work center usage:
  ```sql
  SELECT work_center, status, COUNT(*) as cnt
  FROM production_operations
  WHERE work_center IS NOT NULL
  GROUP BY work_center, status
  ORDER BY work_center, status;
  ```
