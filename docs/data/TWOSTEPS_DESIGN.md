# Two-Step Data Import — Design

## Summary

The data import is split into two sequential phases, each rendered as a separate MCP App:

| Phase | App Resource | Purpose |
|-------|-------------|---------|
| **1. Column Mapping** | `ui://data-import/mapping` | Validate and configure how source columns map to target fields |
| **2. Row Work** | `ui://data-import/rows` | Review, fix, and import individual rows |

The transition from Phase 1 → Phase 2 is deterministic and app-driven (not controlled by the chat LLM).

---

## Phase 1: Column Mapping App

### Layout

```
┌─────────────────────────────────────────────────────┐
│  Entity: Customer (95% confidence)                  │
├─────────────────────────────────────────────────────┤
│  SOURCE COLUMN    │ TARGET FIELD  │ TRANSFORM  │ ☐  │
│  ─────────────────┼───────────────┼────────────┼──  │
│  Customer Name    │ name ▼        │ none       │ ☑  │
│  Country          │ country ▼     │ ISO code   │ ☑  │
│  Ignore Me        │ —             │ —          │ ☐  │
├─────────────────────────────────────────────────────┤
│  Global instructions:                               │
│  ┌───────────────────────────────────────────────┐  │
│  │ All dates are DD/MM/YYYY                      │  │
│  └───────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────┤
│  SAMPLE PREVIEW (read-only, 5 rows)                 │
│  ┌───────────────────────────────────────────────┐  │
│  │ Raw: "France"  →  Mapped: "FR"                │  │
│  │ Raw: "USA"     →  Mapped: "US"                │  │
│  │ ...                                           │  │
│  └───────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────┤
│                              [ Confirm Mapping ]    │
└─────────────────────────────────────────────────────┘
```

### User Actions

| Action | Effect |
|--------|--------|
| Exclude column (checkbox) | Column greyed out, will not be imported |
| Change target field (dropdown) | Reassign to a different destination field |
| Edit transform (text/dropdown) | e.g. "ISO country code", "parse date DD/MM/YYYY", "none" |
| Global instructions (free-text) | Applied to all rows during Phase 2 |
| **Confirm Mapping** | Persists plan, triggers Phase 2 |

### Sample Preview

- Displays 5 representative rows (raw value → transformed value for each mapped column).
- Transforms are applied during upload for the initial preview (LLM call on 5 rows).
- Selection strategy: LLM picks 5 row indices that show data variety (different countries, edge values, missing fields). Falls back to first 5 rows if dataset ≤ 5 rows or LLM unavailable.
- Updates **asynchronously** on mapping change: the app calls `app.callServerTool("data_import_preview_sample", {...})`, keeps the UI interactive, and refreshes the table when the Promise resolves (subtle loading indicator, no blocking).

### Confirm Behaviour

1. Final mapping plan + global instructions persisted on the import job.
2. All rows are re-transformed using the confirmed mapping.
3. App triggers Phase 2 (see App Transition below).

---

## Phase 2: Row Work App

Same as the existing data-import app:

- Paginated list of rows showing raw → mapped values.
- Issues highlighted, batch questions grouped.
- Free-text fix instructions interpreted by LLM.
- Import execution button.

Additions:
- **Global instructions banner** (read-only) — shows the instructions from Phase 1, automatically factored into LLM fix interpretation.
- Only **mapped target columns** are displayed (excluded source columns are not shown).

---

## App Transition

### Architecture

Two separate MCP Apps, two `ui://` resources. Phase 1 programmatically spawns Phase 2 — the chat LLM does not decide when to transition.

### Mechanism

```
Agent calls data_import_upload
  → Tool result carries ui://data-import/mapping
  → VS Code renders Phase 1 app

User confirms mapping in Phase 1
  → App calls app.callServerTool("data_import_confirm_mapping", {...})
  → Tool result carries ui://data-import/rows
  → VS Code renders Phase 2 app below Phase 1
```

---

## Job Lifecycle

```
upload → mapping_review → mapping_confirmed → staging → validated → executed
            (Phase 1)                          (Phase 2)
```

| Status | Meaning |
|--------|---------||
| `mapping_review` | File parsed, mapping proposed, awaiting user confirmation |
| `mapping_confirmed` | Mapping locked, transforms applied to all rows |
| `staging` | Rows ready for review/fix |
| `validated` | All rows validated, ready to execute |
| `executed` | Records created in ERP |

---

## MCP Tools

| Tool | Visibility | Phase | Purpose |
|------|-----------|-------|---------|
| `data_import_upload` | model + app | — | Parse file, detect entity, propose mapping, transform 5 sample rows → opens Phase 1 |
| `data_import_preview_sample` | app only | 1 | Re-transform 5 sample rows with current mapping (async preview) |
| `data_import_confirm_mapping` | app only | 1→2 | Lock mapping, apply transforms, transition to Phase 2 |
| `data_import_get_state` | app only | 2 | Fetch current staging state |
| `data_import_fix` | app only | 2 | Apply free-text fix instruction |
| `data_import_execute` | app only | 2 | Create records in ERP |

---

## Decisions

| Question | Answer |
|----------|--------|
| Sample preview: client-side or server? | Server — transforms are LLM-based. Async call, non-blocking UI. |
| Back button from Phase 2 to Phase 1? | No. Mapping is final once confirmed. |
| Excluded columns visible in Phase 2? | No. Phase 2 shows only mapped target columns. |
| Who controls the transition? | Phase 1 app, not the chat LLM. |
| Where do target fields come from? | Derived from the entity’s schema definition. |
| Initial preview shows transforms? | Yes. Upload transforms the 5 sample rows so the preview is immediately useful. |
| Fallback if app-spawning doesn’t work? | None planned. Happy-path only; we’ll adapt if needed. |
