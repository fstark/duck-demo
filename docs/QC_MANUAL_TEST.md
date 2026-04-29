# QC Feature — Manual Test Suite

Start the backend and frontend before running these tests:
```
./backend.sh   # port 8000
./frontend.sh  # port 5173 (or check output)
```

Demo data should already be loaded (`python -m scenarios --only s01`).
Three batches should exist: QCB-0001 (ELVIS-DUCK-20CM), QCB-0002 (MARILYN-DUCK-20CM), QCB-0003 (ZOMBIE-DUCK-15CM).

---

## Part 1 — UI Checks

### 1.1 Navigation

| Step | Expected |
|------|----------|
| Open the app in a browser | Home page loads |
| Look at the left sidebar | A **Quality** section is visible, containing one item: **QC Queue** |
| Click **QC Queue** | URL hash changes to `#/qc-queue` |

---

### 1.2 QC Queue list page

| Step | Expected |
|------|----------|
| Page loads | A card titled **"QC Hold Batches (3)"** is displayed |
| Status filter dropdown | Visible top-right, default value is **Pending Images** |
| Table columns | Batch ID · Production Order · SKU · Product · Qty Pending · Qty Released · Qty Scrapped · Status · Created |
| Status badge on all 3 rows | Yellow **"pending images"** badge |
| All 3 rows visible | QCB-0001 / ELVIS-DUCK-20CM, QCB-0002 / MARILYN-DUCK-20CM, QCB-0003 / ZOMBIE-DUCK-15CM |
| Click a column header (e.g. SKU) | Table re-sorts; arrow indicator appears on clicked column |
| Change status filter to **All** | Same 3 rows still shown (no other statuses exist yet) |
| Change status filter to **Released** | Empty state: "No batches with status 'released'." |
| Change status filter back to **Pending Images** | 3 rows reappear |

---

### 1.3 QC Batch detail page

| Step | Expected |
|------|----------|
| Click **QCB-0001** in the list | Navigates to the detail view; breadcrumb shows `← QC Queue / QCB-0001` |
| **QC Hold Batch** card | Shows Batch ID, Production Order (clickable link), Sales Order (clickable link), Item SKU + Name, Status badge, Created date, Released date (empty) |
| **Hold Quantities** card | Shows Qty on Hold, Qty Pending, Qty Released (0), Qty Scrapped (0) |
| **Images** card | Shows "No images attached yet." |
| **Inspection** card | Shows "No inspection run yet." |
| **Replacement Orders** card | Shows "No replacement orders." |
| Click the **Production Order** link | Navigates to the production order detail page |
| Use browser back or click **← QC Queue** | Returns to the QC Queue list |
| Click **QCB-0002** | Detail page loads for MARILYN-DUCK-20CM |

---

## Part 2 — Chat / MCP Prompt Sequence

Use these prompts in sequence in the MCP chat. You will need to supply real image URLs when prompted.

> **Note on images**: when a prompt says `[IMAGE_URL_1]` etc., replace with the actual URLs you have.
> Two URLs per batch is ideal — one "good" angle and one close-up.

---

### Step 1 — Discover the queue

```
Show me all QC hold batches that are waiting for images.
```

**Verify**: Agent calls `qc_list_pending_batches`, returns 3 batches with status `pending_images`.

---

### Step 2 — Attach images to batch 1

```
Attach these two images to QCB-0001:
- [IMAGE_URL_1]
- [IMAGE_URL_2]

I'm the QC operator, my ID is "qc-operator-1".
```

**Verify**:
- Agent calls `qc_attach_images`
- Returns updated batch with status `ready_for_inspection`
- Refresh the UI → **Images** card on QCB-0001 shows both URLs

---

### Step 3 — Run inspection on batch 1

```
Run the AI inspection on QCB-0001.
```

**Verify**:
- Agent calls `qc_run_inspection`
- Returns an inspection record with `status: completed`, a `decision` (pass / partial_scrap / full_scrap), `confidence_overall`, `decision_reason`, and a `findings` list
- Refresh UI → **Inspection** card on QCB-0001 is populated with the result

---

### Step 4 — Apply disposition on batch 1 (happy path — pass)

> Use this step if the inspection returned `decision: pass`.

```
The inspection on QCB-0001 looks good. Release all units to stock.
I approve this as "qc-operator-1".
```

**Verify**:
- Agent calls `qc_apply_disposition` with `action: pass_release`
- A **confirmation dialog** appears showing the inspection ID, batch ID, model decision, and selected action
- Confirm the action
- Refresh UI → batch status changes to **released**, Qty Released equals the original Qty on Hold
- **Replacement Orders** card still shows "No replacement orders"

---

### Step 4b — Apply disposition on batch 1 (scrap path)

> Use this step instead if you want to demo the scrap flow (or if the inspection returned a scrap decision).

```
The items in QCB-0001 are all defective — scrap the entire batch.
I approve this as "qc-operator-1". Note: mold contamination observed.
```

**Verify**:
- Agent calls `qc_apply_disposition` with `action: full_scrap`
- Confirmation dialog appears; confirm
- Refresh UI → batch status **closed**, Qty Scrapped = full quantity
- **Replacement Orders** card shows a new production order was created automatically

---

### Step 5 — Partial scrap on batch 2

```
Attach this image to QCB-0002: [IMAGE_URL_3]

Then run the inspection. Once done, I want to scrap 2 units and release the rest.
Approved by "qc-operator-1".
```

**Verify**:
- Agent chains: `qc_attach_images` → `qc_run_inspection` → `qc_apply_disposition` (partial_scrap, qty_scrapped=2)
- Confirmation dialog appears for the disposition; confirm
- Refresh UI → batch status **partially_released**
- Qty Released = original − 2, Qty Scrapped = 2
- Replacement Orders card shows 1 replacement MO for the 2 scrapped units

---

### Step 6 — Check the queue is draining

```
How many QC batches are still waiting for images?
```

**Verify**: Agent calls `qc_list_pending_batches`, returns 1 remaining (QCB-0003).

---

### Step 7 — Get full detail of a completed batch

```
Give me the full detail of QCB-0001 including inspection findings.
```

**Verify**: Agent calls `qc_get_batch`, returns batch with `lines`, `images`, `inspection` (with `findings`), and `replacements`.

---

### Step 8 — End-to-end check (batch 3, all in one prompt)

```
Process QCB-0003 end to end:
1. Attach image [IMAGE_URL_4]
2. Run the inspection
3. Whatever the model decides, apply the appropriate disposition. I approve as "qc-operator-1".
```

**Verify**:
- Agent chains all three tool calls with a confirmation step before the disposition
- Final batch status is not `pending_images`
- UI reflects the final state correctly

---

## Part 3 — Cross-feature Verification

After the above steps, verify these cross-cutting concerns:

| Check | How |
|-------|-----|
| Released stock is available | Ask: *"How much ELVIS-DUCK-20CM stock do we have available?"* — should show on_hand > 0 |
| Replacement MO is visible in production | Navigate to Production page, search for the replacement MO ID shown in the batch detail; verify it has `inspection_required = 0` |
| Activity log entries | Ask: *"Show me recent QC activity"* or check the Activity page for `quality` category entries |
| Scrapped units are NOT in allocatable stock | Ask: *"Check availability of [scrapped item SKU]"* — qty_scrapped should not count toward available |
