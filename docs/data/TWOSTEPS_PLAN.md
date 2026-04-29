# Two-Step Data Import — Implementation Plan

Reference: [TWOSTEPS_DESIGN.md](TWOSTEPS_DESIGN.md)

---

## 1. Database Schema Changes

### File: `schema.sql`

**`import_jobs` table — add columns:**

| Column | Type | Purpose |
|--------|------|---------|
| `global_instructions` | TEXT | Free-text instructions from Phase 1 (used during Phase 2 fix interpretation) |
| `sample_indices` | TEXT | JSON array of 5 row indices chosen for the preview |

**`import_jobs.status` — add value:**

- `'mapping_review'` — between upload and staging (mapping proposed, not yet confirmed)

Current flow: `staging → validated → executed`
New flow: `mapping_review → mapping_confirmed → staging → validated → executed`

(All three docs now use these canonical status names.)

No schema DDL change needed for status (it's a TEXT column), but update comments/documentation.

---

## 2. Service Layer Changes

### File: `services/data_import.py`

### 2.1 Split `upload()` into two phases

**Current `upload()` does everything:**
parse → detect entity → map columns → apply transforms → validate → resolve entities → return state

**New behaviour:**

| Method | Steps | Returns |
|--------|-------|---------|
| `upload(source, hint)` | parse → detect entity → map columns → select sample indices → transform 5 sample rows → preview | Mapping state (Phase 1 payload) |
| `confirm_mapping(job_id, mapping, global_instructions)` | persist final mapping + instructions → apply transforms to ALL rows → validate → resolve entities | Staging state (Phase 2 payload) |

### 2.2 New method: `preview_sample(job_id, mapping)`

- Takes the current (potentially edited) mapping from the UI.
- Applies transforms to the 5 sample rows only (not all rows).
- Returns the 5 rows with both raw and mapped values.
- Called async by Phase 1 app on every mapping edit.

### 2.3 New method: `_select_sample_indices(rows, columns)`

- LLM call: given all rows + column headers, pick 5 representative indices.
- Prompt: "Select 5 row indices (0-based) that best represent the variety in this dataset. Prefer rows with: different countries, edge values, missing fields, unusual formats."
- Fallback: `[0, 1, 2, 3, 4]` if LLM fails or dataset ≤ 5 rows.
- Store result in `import_jobs.sample_indices`.

### 2.4 Modify `_build_staging_state()` → two builders

| Builder | Used by | Content |
|---------|---------|---------|
| `_build_mapping_state(job_id)` | `upload()`, `preview_sample()` | Job metadata + columns + mapping + 5 sample rows (raw + mapped) |
| `_build_staging_state(job_id)` | `confirm_mapping()`, `get_state()`, `fix()` | Full row list + issues + batch questions (unchanged from today) |

### 2.5 Modify `confirm_mapping()`

- Accept `mapping: list[dict]` (user may have edited targets/transforms/exclusions).
- Accept `global_instructions: str`.
- Persist both to `import_jobs` (update `mapping_plan`, set `global_instructions`).
- Set status to `'mapping_confirmed'`.
- Run: apply transforms → validate → resolve entities (same pipeline as current upload tail).
- Return staging state for Phase 2.

### 2.6 Inject `global_instructions` into fix LLM prompt

In `fix()`, when calling LLM to interpret a freeform instruction, prepend `global_instructions` to the system prompt so fixes respect user's Phase 1 directives (e.g. "All dates are DD/MM/YYYY").

---

## 3. MCP Tool Changes

### File: `mcp_tools/data_import_tools.py`

### 3.1 Modify `data_import_upload`

- Keep visibility `["model", "app"]`.
- Change `resourceUri` to `"ui://data-import/mapping"` (Phase 1 app).
- No longer returns full staging state — returns mapping state instead.

### 3.2 New tool: `data_import_preview_sample`

| Field | Value |
|-------|-------|
| Name | `data_import_preview_sample` |
| Visibility | `["app"]` |
| Tags | `[]` |
| Parameters | `job_id: str`, `mapping: list[dict]` |
| Returns | 5 sample rows with raw + mapped values |
| UI | None (data-only, no new app) |

### 3.3 New tool: `data_import_confirm_mapping`

| Field | Value |
|-------|-------|
| Name | `data_import_confirm_mapping` |
| Visibility | `["app"]` |
| Tags | `[]` |
| Parameters | `job_id: str`, `mapping: list[dict]`, `global_instructions: str` |
| Returns | Full staging state |
| UI | `resourceUri: "ui://data-import/rows"` (Phase 2 app) |

### 3.4 Existing tools — no changes needed

- `data_import_fix` — unchanged (but service injects global_instructions into prompt).
- `data_import_execute` — unchanged.
- `data_import_get_state` — unchanged (returns Phase 2 state for confirmed jobs).

---

## 4. MCP Resource Registration

### File: `server.py`

### 4.1 Replace single resource with two

**Remove:**
```python
@mcp.resource("ui://data-import/result", mime_type="text/html;profile=mcp-app")
```

**Add:**
```python
@mcp.resource("ui://data-import/mapping", mime_type="text/html;profile=mcp-app")
def get_data_import_mapping_ui() -> str:
    # Serves mcp_apps_ui/data-import-mapping.html

@mcp.resource("ui://data-import/rows", mime_type="text/html;profile=mcp-app")
def get_data_import_rows_ui() -> str:
    # Serves mcp_apps_ui/data-import-rows.html
```

---

## 5. Frontend Changes

### File structure

**Current:**
- `ui/data-import.html` — single entry point
- `ui/src/mcp-apps/data-import-main.tsx` — mounts `DataImportViewer`
- `ui/src/mcp-apps/DataImportViewer.tsx` — monolithic component

**New:**
- `ui/data-import-mapping.html` — Phase 1 entry point
- `ui/data-import-rows.html` — Phase 2 entry point
- `ui/src/mcp-apps/data-import-mapping-main.tsx` — mounts `DataImportMappingApp`
- `ui/src/mcp-apps/data-import-rows-main.tsx` — mounts `DataImportRowsApp`
- `ui/src/mcp-apps/DataImportMappingApp.tsx` — **new** Phase 1 component
- `ui/src/mcp-apps/DataImportRowsApp.tsx` — **renamed/refactored** from `DataImportViewer.tsx`

### 5.1 `DataImportMappingApp.tsx` (new)

**Receives (via `useApp()` structured content):**
```ts
interface MappingState {
  job_id: string;
  entity_type: string;
  entity_confidence: number;
  columns_detected: string[];
  mapping: MappingEntry[];        // LLM-proposed
  sample_rows: SampleRow[];       // 5 rows with raw + transformed
  target_fields: TargetField[];   // derived from entity schema definition
}
```

**UI sections:**
1. Header — entity type + confidence badge
2. Mapping table — editable rows (source → target dropdown → transform input → exclude checkbox)
3. Global instructions — textarea
4. Sample preview — table showing 5 rows (raw | mapped), with loading indicator during refresh
5. Confirm button

**Behaviour:**
- On mapping edit → `app.callServerTool("data_import_preview_sample", {job_id, mapping})` (fire-and-forget Promise, update sample preview on resolve).
- On "Confirm Mapping" → `app.callServerTool("data_import_confirm_mapping", {job_id, mapping, global_instructions})` → Phase 2 app renders.

### 5.2 `DataImportRowsApp.tsx` (refactored from `DataImportViewer.tsx`)

- Receives staging state (same as today).
- Add read-only banner at top showing `global_instructions` (if non-empty).
- Remove any column-mapping UI that currently exists in the viewer (if any).
- Otherwise unchanged.

### 5.3 Vite build config

Add two new MCP app build entries to `package.json` scripts or the build process:

```bash
MCP_APP_ENTRY=data-import-mapping.html npm run build:mcp
MCP_APP_ENTRY=data-import-rows.html npm run build:mcp
```

Remove old `data-import.html` entry.

---

## 6. API Routes

### File: `api_routes/data_import_routes.py`

No mandatory changes. Optional: expose `global_instructions` and `sample_indices` in the job detail endpoint for debugging.

---

## 7. Tests

### File: `tests/test_data_import.py`

### 7.1 New test: `test_upload_returns_mapping_state`

- Mock LLM (detect + map + sample selection + transform sample).
- Call `upload(source)`.
- Assert job status is `'mapping_review'`.
- Assert response contains `mapping`, `sample_rows` (5 items with transformed values), `columns_detected`, `entity_type`, `target_fields`.
- Assert response does NOT contain full `rows` array or `batch_questions`.

### 7.2 New test: `test_preview_sample`

- Create job in `mapping_review` state (call `upload()` with mock).
- Call `preview_sample(job_id, modified_mapping)` with an altered mapping (e.g. swap a target field).
- Assert returned sample rows reflect the new mapping.
- Mock LLM transform call for sample-only batch.

### 7.3 New test: `test_preview_sample_with_excluded_column`

- Mark one column as excluded in the mapping passed to `preview_sample`.
- Assert that column is absent from `mapped_data` in sample rows.

### 7.4 New test: `test_confirm_mapping`

- Create job in `mapping_review` state.
- Call `confirm_mapping(job_id, mapping, global_instructions="All dates DD/MM/YYYY")`.
- Assert job status transitions to `'mapping_confirmed'` or `'staging'`.
- Assert `global_instructions` persisted on job.
- Assert all rows now have `mapped_data` (transforms applied).
- Assert validation ran (some rows may be `rejected` / `needs_review`).

### 7.5 New test: `test_confirm_mapping_with_edited_mapping`

- Modify the LLM-proposed mapping (change a target field, edit a transform).
- Call `confirm_mapping` with the modified mapping.
- Assert transforms use the user's version, not the original LLM proposal.

### 7.6 New test: `test_fix_uses_global_instructions`

- Create confirmed job with `global_instructions`.
- Call `fix(job_id, "fix the dates")`.
- Assert the LLM prompt for fix interpretation includes the global instructions text.
- (Verify via mock call args.)

### 7.7 New test: `test_sample_selection_fallback`

- Dataset with ≤ 5 rows.
- Assert `sample_indices` covers all rows (e.g. `[0, 1, 2, 3, 4]` or fewer).
- No LLM call for sample selection (fallback used).

### 7.8 Update existing tests

- Tests that call `upload()` and expect full staging state → update assertions to expect mapping state.
- Tests for `fix()` / `execute()` → add a `confirm_mapping()` step between upload and fix/execute.
- Update mock side_effect lists (upload now makes 4 LLM calls: detect + map + sample selection + transform 5 sample rows; confirm adds full-dataset transform).

---

## 8. Cleanup

- Delete `ui/src/mcp-apps/DataImportViewer.tsx` (replaced by two new files).
- Delete `ui/src/mcp-apps/data-import-main.tsx` (replaced by two new entry points).
- Delete `ui/data-import.html` (replaced by two new HTML files).
- Delete `mcp_apps_ui/data-import.html` (old compiled output).
- Remove `ui://data-import/result` resource from `server.py`.

---

## 9. Implementation Order

| Step | What | Dependencies |
|------|------|-------------|
| 1 | Schema: add columns to `import_jobs` | — |
| 2 | Service: split `upload()`, add `preview_sample()`, add `confirm_mapping()` | Step 1 |
| 3 | Service: inject `global_instructions` into fix prompt | Step 2 |
| 4 | Tools: modify `data_import_upload`, add new tools | Step 2 |
| 5 | Server: register two new resources | Step 4 |
| 6 | Tests: update existing + write new | Steps 2–4 |
| 7 | Frontend: `DataImportMappingApp.tsx` (Phase 1 UI) | Step 4 |
| 8 | Frontend: `DataImportRowsApp.tsx` (refactor from current viewer) | Step 5 |
| 9 | Vite: new build entries, HTML entry points | Step 7–8 |
| 10 | Cleanup: remove old files | Steps 7–9 |
| 11 | End-to-end manual test | All |
