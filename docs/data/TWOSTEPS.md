# Two-Step Data Import

## Overview

Split the data import into two distinct phases, each with its own MCP App UI:

1. **Step 1 — Column Mapping**: Understand and validate the structure (columns, transforms, instructions).
2. **Step 2 — Row Work**: Process individual rows (current paginated list with suggestions).

Step 1's app triggers Step 2's app once the mapping is confirmed.

---

## Step 1: Column Mapping

### Goal

Give the user full visibility and control over *how* source columns map to target fields before any row-level work begins.

### UI Layout

| Section | Content |
|---------|---------|
| **Header** | Detected entity type + confidence badge |
| **Mapping table** | Source column → Target field → Transform — one row per column. Each row is editable: user can reassign target, change transform, or mark as "excluded". |
| **Global instructions** | Free-text area where the user can type overall instructions (e.g. "All dates are DD/MM/YYYY", "Ignore rows where status = inactive"). These instructions are passed to Step 2 for row-level interpretation. |
| **Sample preview** (read-only) | A table showing 5 representative rows with raw values *and* their mapped result given the current mapping. Updates live when the user changes a mapping. |

### Sample Row Selection

Extract 5 rows to display in the preview. Strategy (in priority order):

1. **LLM-chosen representative sample** — Ask the LLM to pick 5 row indices that best represent the variety in the dataset (different countries, edge values, missing fields, etc.).
2. **Fallback** — First 5 rows if LLM selection is unavailable or dataset is ≤ 5 rows.

### User Actions

- **Exclude column** — toggle a column out of the mapping (greyed out, not imported).
- **Change target field** — dropdown of available target fields for the detected entity (derived from the entity's schema definition).
- **Edit transform** — free-text or dropdown (e.g. "ISO country code", "parse date DD/MM/YYYY", "none").
- **Add global instructions** — free-text that will apply to all rows during Step 2.
- **Confirm mapping** → transitions to Step 2.

### Confirm Behaviour

When the user clicks "Confirm Mapping":

- The final mapping plan + global instructions are persisted on the job.
- Transforms are re-applied to all rows using the confirmed mapping.
- The UI transitions to the Step 2 app (same panel, new view — or the first app calls/opens the second).

---

## Step 2: Row Work

Identical to the current data-import app behaviour:

- Paginated list of rows (raw → mapped, issues, duplicates).
- Batch questions and free-text fix instructions.
- Import execution.

The only addition is that **global instructions** from Step 1 are visible (read-only banner) and automatically factored into LLM fix interpretation.

---

## App Transition

Step 1 and Step 2 are **two separate MCP Apps** (two distinct `ui://` resources):

- `ui://data-import/mapping` — Column Mapping app
- `ui://data-import/rows` — Row Work app

The transition is **not controlled by the chat LLM**. When the user confirms the mapping in App 1, App 1 itself triggers App 2 to appear below it in the conversation.

### Desired Mechanism

App 1 calls an app-only tool (e.g. `data_import_confirm_mapping`) via `app.callServerTool()`. That tool's result includes `_meta.ui.resourceUri = "ui://data-import/rows"`, which should cause VS Code to render App 2 below App 1 in the chat panel.

```
User uploads file → Agent calls data_import_upload
  → VS Code renders App 1 (column mapping)
  → User tweaks mapping, clicks "Confirm"
  → App 1 calls data_import_confirm_mapping (app-only tool)
  → Tool result carries ui://data-import/rows resource
  → VS Code renders App 2 (row work) below App 1
  → User works on rows, clicks "Import"
```

### Open: Is This Supported?

It is unclear whether VS Code's MCP app hosting currently supports an app-only tool call result spawning a *new* app panel below the calling app. We proceed with the happy-path assumption (tool result triggers a new app panel). No fallback planned — we'll adapt if it doesn't work.

---

## Job Lifecycle (updated)

```
upload → mapping_review (Step 1)
       → mapping_confirmed → staging (Step 2)
       → validated → executed
```

The `mapping_review` status is new — it means the file is parsed and a mapping is proposed but not yet user-confirmed.

---

## Open Questions

- ~~Should the sample preview update live (re-run transforms on 5 rows client-side) or require a server round-trip?~~ **Answer**: Server round-trip required (transforms are LLM-based). Preview updates asynchronously — user edits a mapping, the app calls `app.callServerTool("data_import_preview_sample", {...})` (which returns a Promise), keeps the UI interactive while the call is in-flight, and refreshes the sample rows when the Promise resolves. No blocking, no spinner — just a subtle loading indicator on the preview table until new data arrives.
- ~~Do we need a "back" button from Step 2 to Step 1 (re-edit mapping after seeing row issues)?~~ **Answer**: No. Once mapping is confirmed, it's final.
- ~~Should excluded columns still appear in the Step 2 row view (greyed out) for reference?~~ **Answer**: No. Step 2 only shows mapped target columns. (Future: Step 2 will show all columns from the destination table, not just those with a source mapping.)
