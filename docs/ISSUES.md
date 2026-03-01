# Known coding issue in the codebase

Keep descriptions concise with reference to the code.

Update with new issues when dicovered in the code.

Severity: **Critical** > High > Medium > Low.

Keep numbers for ease of reference, but they have not other purpose

When issue is fixed, delete it (after potential update in CODING.md if it's a coding rule violation). Do not keep a record of fixed issues in this file.

---

## 9. Quantity Representation

### 9a · Use integer quantities with explicit unit-of-measure — Medium

All `qty` columns are `REAL`, which invites floating-point rounding issues
(e.g. `0.1 + 0.2 ≠ 0.3`, inexact `== 0` checks).  The `uom` column already
exists on `items` but is cosmetic — nothing enforces that `200` means "200 g".

**Suggested fix:** Switch `qty` / `output_qty` / `input_qty` / `qty_produced` /
`reorder_qty` columns to `INTEGER`, storing quantities in the item’s smallest
unit (grams, millilitres, pieces, etc.).  The `uom` on `items` becomes the
authoritative base unit.

This touches schema, seed data, all services that read/write quantities,
PDF rendering, and the UI display layer (format `1500` as `"1.5 kg"` or
`"1500 mL"` depending on `uom`).

