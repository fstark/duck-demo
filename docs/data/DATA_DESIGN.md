# Data Import — Technical Design

This document is the implementation blueprint for the data import feature described in [DATA.md](DATA.md). It covers the data model, service architecture, MCP tools, app-only MCP tools, LLM prompts, and the interactive MCP app.

See [DEMO_FLOW.md](DEMO_FLOW.md) for the end-to-end user-facing flow of Demo A.

---

## 1. Data Model

### 1.1 Design Principles

- Staging data is **fully isolated** from operational tables. No partially-imported rows leak into `customers`, `sales_orders`, etc.
- All intermediate state (raw extraction, mapping plan, transformed values, issues) is stored in the staging tables — not held in memory between tool calls.
- Every import job is **replayable**: given the same raw data and the same user decisions, the output is deterministic.
- Staging tables are **cleared on data reset** (`admin_reset_database`), same as all other tables.

### 1.2 New Tables

#### import_jobs

One row per import operation. Tracks the overall pipeline state.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | e.g. `IMP-001` |
| entity_type | TEXT | Detected target: `customer`, `item`, `sales_order`, `supplier`, etc. NULL until detection runs. |
| source_filename | TEXT | Original filename (for display only) |
| source_format | TEXT | `csv`, `xlsx`, `json`, `image`, `pdf`, `text` |
| source_content | TEXT | Raw file content (text) or base64 (binary). Stored so the job is self-contained. |
| hint | TEXT | Optional user-provided description of the data |
| status | TEXT NOT NULL | Pipeline state (see below) |
| row_count | INTEGER | Number of extracted data rows |
| columns_detected | TEXT | JSON array of original column names |
| mapping_plan | TEXT | JSON array of `{source, target, transform, confidence}` objects |
| issues_summary | TEXT | JSON object: `{ready: N, needs_review: N, rejected: N}` |
| created_at | TEXT NOT NULL | |
| executed_at | TEXT | Timestamp of execution |

**Status lifecycle:**

```
staging → validated → ready_to_execute → executed
                                       → rolled_back
```

- `staging` — transient state during `upload()`. File parsed, rows extracted. Not visible to the user.
- `validated` — `upload()` complete. Mapping generated, transforms applied, entity resolution done, issues flagged. The MCP app renders from this state.
- `ready_to_execute` — all issues resolved (or accepted by the user via the MCP app)
- `executed` — records created in operational tables
- `rolled_back` — execution undone

#### import_rows

One row per data row from the source file. Carries the full transformation pipeline per row.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | e.g. `IMP-001-R01` |
| job_id | TEXT NOT NULL | FK → `import_jobs.id` |
| source_row | INTEGER NOT NULL | 1-based row number from original file |
| raw_data | TEXT NOT NULL | JSON object: column names → raw string values as extracted |
| mapped_data | TEXT | JSON object: target field names → transformed values |
| resolved_refs | TEXT | JSON object: field → `{match_id, match_name, confidence, reason}` |
| status | TEXT NOT NULL | `pending`, `ready`, `needs_review`, `rejected`, `merged`, `imported` |
| issues | TEXT | JSON array of `{severity, field, message, auto_fixed, suggestion}` |
| merged_into | TEXT | If merged, the `id` of the surviving row |
| created_entity_type | TEXT | Entity type created (after execution) |
| created_entity_id | TEXT | ID of created/updated record (after execution) |

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS idx_import_rows_job ON import_rows(job_id);
CREATE INDEX IF NOT EXISTS idx_import_rows_status ON import_rows(status);
```

### 1.3 Schema SQL

```sql
CREATE TABLE IF NOT EXISTS import_jobs (
    id TEXT PRIMARY KEY,
    entity_type TEXT,
    source_filename TEXT,
    source_format TEXT,
    source_content TEXT,
    hint TEXT,
    status TEXT NOT NULL DEFAULT 'staging',
    row_count INTEGER,
    columns_detected TEXT,
    mapping_plan TEXT,
    issues_summary TEXT,
    created_at TEXT NOT NULL,
    executed_at TEXT
);

CREATE TABLE IF NOT EXISTS import_rows (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    raw_data TEXT NOT NULL,
    mapped_data TEXT,
    resolved_refs TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    issues TEXT,
    merged_into TEXT,
    created_entity_type TEXT,
    created_entity_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_import_rows_job ON import_rows(job_id);
CREATE INDEX IF NOT EXISTS idx_import_rows_status ON import_rows(status);
```

---

## 2. Entity Type Registry

The service needs to know, for each importable entity type, what fields exist, which are required, and what validation rules apply. This avoids hardcoding per-entity logic.

```python
ENTITY_SCHEMAS = {
    "customer": {
        "table": "customers",
        "fields": {
            "name":          {"required": True,  "type": "text"},
            "company":       {"required": False, "type": "text"},
            "email":         {"required": False, "type": "email"},
            "phone":         {"required": False, "type": "phone"},
            "address_line1": {"required": False, "type": "text"},
            "address_line2": {"required": False, "type": "text"},
            "city":          {"required": False, "type": "text"},
            "postal_code":   {"required": False, "type": "text"},
            "country":       {"required": False, "type": "country_code"},
            "tax_id":        {"required": False, "type": "text"},
            "payment_terms": {"required": False, "type": "integer"},
            "currency":      {"required": False, "type": "currency_code"},
            "notes":         {"required": False, "type": "text"},
        },
        "dedup_keys": ["email", "tax_id"],
        "fuzzy_keys": ["name", "company", "city"],
        "service_create": "customer_service.create_customer",
    },
    # Future: "item", "supplier", "sales_order", etc.
}
```

This registry is:
- Passed to the LLM as context during mapping (so it knows what fields exist)
- Used by the validation step (required checks, type checks)
- Used by entity resolution (which fields to match on)
- Used by execution (which service method to call)

Starting with `customer` only. Each new entity type is a new entry in this dict — no new code paths.

---

## 3. Service Layer

### 3.1 `services/data_import.py` — `DataImportService`

Singleton: `data_import_service = DataImportService()`

Stateless, all state in the database.

#### Core Methods

| Method | Input | Does | Returns |
|--------|-------|------|---------|
| `upload(source, hint)` | File URL or content | Parse file, detect format, extract rows, detect entity type, generate mapping, apply transforms, validate, resolve entities, group issues — **all in one call** | Full staging state (mapping, rows, issues, batch questions) for the MCP app |
| `fix(job_id, instruction)` | Job + free-text instruction | Backend LLM interprets instruction against current staging state, applies changes, re-validates, regroups issues | Updated staging state for the MCP app |
| `execute(job_id)` | Job ID | Call service layer for each ready row, record created IDs | Execution result |
| `rollback(job_id)` | Job ID | Delete created records by stored IDs | Rollback result |

`upload()` does the work of what was previously five separate steps. This is the "Extract" in the ETL pattern — one tool call, all server-side, no agent round-trips.

`fix()` is called by the MCP app directly via an app-only MCP tool (`data_import_fix`) — not by the agent. It takes a free-text instruction like "merge the duplicates, use the longer name" and uses Prompt 4 to interpret it against the actual row data. After applying the fix, it re-validates and returns the full updated state so the MCP app can re-render.

`execute()` and `rollback()` are also called via app-only MCP tools from the MCP app, not by the agent.

#### Internal Methods (called within `upload()` and `fix()`)

| Method | Purpose |
|--------|---------|
| `_parse_file(content, filename)` | Detect format, extract rows as list of dicts |
| `_detect_entity(columns, sample_rows)` | LLM call → entity type |
| `_generate_mapping(columns, sample_rows, entity_schema)` | LLM call → mapping plan |
| `_apply_transforms(job_id)` | Apply mapping + transforms to all rows, write `mapped_data` |
| `_validate_rows(job_id)` | Schema validation, write issues |
| `_resolve_entities(job_id)` | Fuzzy matching against existing records, write `resolved_refs` |
| `_merge_rows(job_id, primary_row, absorbed_rows, instruction)` | Combine rows via backend LLM |
| `_group_issues(job_id)` | Group similar issues into batch questions (e.g. 15 missing phones → one decision) |
| `_build_staging_state(job_id)` | Build the full JSON state object that the MCP app renders from |

### 3.2 File Parsing — `_parse_file`

Strategy: detect format from filename extension + content sniffing, then delegate.

| Format | Library | Notes |
|--------|---------|-------|
| CSV / TSV | `csv` stdlib | Sniff delimiter via `csv.Sniffer`. Try UTF-8 first, fall back to latin-1. |
| Excel | `openpyxl` | Read first sheet by default. Skip merged-cell regions, detect header row (first row with >50% non-empty cells). |
| JSON / JSONL | `json` stdlib | If array of objects → rows. If nested → flatten with dot notation. |
| Image / PDF | MyForterro vision model | Send to LLM with extraction prompt: "Extract all tabular data as JSON array of objects." |
| Plain text | LLM | Send to LLM: "Parse this text into structured records." |

Output: `(rows: list[dict], format_info: str)` where each row is `{column_name: raw_string_value}`.

### 3.3 LLM Calls

All LLM calls go through `myforterro.chat_completion()`. Three distinct prompt types:

#### Prompt 1 — Entity Detection

Input: column names + 3 sample rows.
Output: entity type string.

```
You are a data classification expert for an ERP system.
Given these column headers and sample data, determine which ERP entity this represents.

Possible entities: customer, item, supplier, sales_order

Column headers: {columns}
Sample rows: {sample_rows}

Respond with ONLY a JSON object: {"entity_type": "...", "confidence": 0.95, "reason": "..."}
```

#### Prompt 2 — Column Mapping

Input: column names, sample values, target entity schema.
Output: mapping plan.

```
You are a data mapping expert for an ERP system.
Map each source column to the most appropriate target field.

Source columns with sample values:
{columns_with_samples}

Target entity: {entity_type}
Available target fields:
{entity_schema_fields}

For each source column, respond with a JSON array:
[{"source": "...", "target": "...", "transform": "...", "confidence": 0.0-1.0}]

Rules:
- "transform" describes what conversion is needed (e.g. "ISO country code", "parse integer from text", "none")
- "confidence" reflects how certain you are about the mapping
- If a column has no good match, set target to null
```

#### Prompt 3 — Value Transform (batched)

Input: all raw values for all columns that need LLM-based transforms, across all rows.
Output: all transformed values in one shot.

**One LLM call for the entire transform step** — not per-value or per-row. Batching is not just faster, it's *better*: the LLM sees all values for a column at once and applies consistent logic (e.g. "these are all German payment terms → parse the same way"). Per-value calls would lose that cross-row context.

Simple transforms (lowercase, country code lookup, phone normalisation) are handled in Python code and never hit the LLM. Only ambiguous or language-dependent transforms go through this prompt.

```
You are a data transformation expert. Transform the following raw values
for import into an ERP system.

For each entry, apply the specified transform and return the cleaned value.

Transforms to apply:
{transforms_array}

Example entry:
{"row": 1, "source_column": "Zahlungsziel", "target_field": "payment_terms",
 "target_type": "integer", "transform": "parse integer from text",
 "raw_value": "30 Tage", "row_context": {"Firma": "DuckFan Paris", "Land": "france"}}

Respond with ONLY a JSON array, one object per input entry:
[{"row": 1, "source_column": "Zahlungsziel", "value": 30, "notes": "parsed '30 Tage' as 30 days"}]
```

For large files that exceed context limits, chunk into batches of ~50 rows per call. Demo-scale data (dozens of rows) fits in a single call.

#### Prompt 4 — Fix Instruction Interpretation

Input: current staging state (rows, issues, batch questions) + user's free-text instruction.
Output: a list of actions to apply to the staging data.

This is the backend LLM call made during `fix()`. It's called by the MCP app via an app-only MCP tool — the agent is not involved. The LLM sees the full staging context and interprets the user's natural language instruction against it.

```
You are a data import assistant. The user is reviewing staged import data
and has given an instruction to fix issues.

Current staging state:
{staging_state_json}

Current batch question: {batch_question}

User instruction: {instruction}

Based on the instruction, determine what changes to make to the staging data.
Respond with ONLY a JSON object:
{
  "actions": [
    {"type": "merge", "rows": [1, 4], "merged_values": {field: value, ...}},
    {"type": "set_value", "row": 2, "field": "name", "value": "QuackShop London"},
    {"type": "reject", "rows": [5]},
    {"type": "keep", "rows": [3]}
  ],
  "reasoning": "brief explanation of interpretation"
}
```

For simple, deterministic fixes (reject all, keep all, set a specific value), the service can bypass the LLM and apply Python logic directly. The LLM is only invoked when the instruction requires interpretation (e.g. "use the longer name", "merge and keep both emails").

### 3.4 Entity Resolution — `_resolve_entities`

Three-tier matching, executed in order (stop at first confident match):

1. **Exact key match** — Compare normalised `dedup_keys` (email, tax_id) against existing records. Confidence: 1.0.
2. **Fuzzy name match** — Trigram similarity on `fuzzy_keys` using Python `difflib.SequenceMatcher`. Threshold: 0.7. Confidence: similarity score.
3. **Combined score** — If multiple fields partially match (e.g. similar company + same city), combine scores with weights.

No embedding-based semantic search in v1 — `SequenceMatcher` is sufficient for the demo data volume and keeps dependencies minimal.

If a match is found with confidence ≥ 0.9, mark as `ready` (auto-resolved).
If 0.6 ≤ confidence < 0.9, mark as `needs_review` with a `possible_duplicate` issue.
If confidence < 0.6, treat as new record.

---

## 4. MCP Tool

One tool. The agent calls it and the MCP app takes over from there.

### 4.1 `data_import_upload`

```python
@mcp.tool(name="data_import_upload", meta={
    "tags": ["data_import"],
    "ui": {
        "resourceUri": "ui://data-import/result",
        "visibility": ["model", "app"]
    }
})
def data_import_upload(
    source: str,
    hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Upload a file for import into the ERP.

    The file is parsed, the entity type is auto-detected, columns are mapped,
    transforms are applied, validation and entity resolution are run — all in
    one call. The result appears in the interactive import panel where you can
    review and fix issues before importing.

    Parameters:
        source: File path URL (file:///...) or inline content (text/base64)
        hint: Optional description of the data ("customer list from old CRM")

    Returns:
        Full staging state rendered in the interactive import panel.
    """
```

That's it. No `data_import_validate`, no `data_import_fix_issue`, no `data_import_preview`. Those operations happen inside the MCP app via app-only MCP tools (see §5).

`data_import_execute` and `data_import_rollback` are app-only MCP tools called by the MCP app via `app.callServerTool()`, not by the agent.

### 4.2 Tool Registration

In `mcp_tools/data_import_tools.py`, following the standard pattern:

```python
def register(mcp):
    @mcp.tool(...)
    def data_import_upload(source, hint=None):
        result = data_import_service.upload(source, hint)
        return result
```

Single tool, single registration. Registered via `mcp_tools/__init__.py`.

### 4.3 Read-Only Tools for Context

The import agent also has read access to existing ERP data (useful if the agent needs to answer questions about the import, though most resolution happens server-side):

- `crm_search_customers` — search existing customers
- `catalog_search_items` — search existing items

These are already tagged `shared` and need no changes.

---

## 5. App-Only MCP Tools

The MCP app communicates with the backend via `app.callServerTool()` — the standard MCP Apps mechanism (postMessage JSON-RPC through the host). These are MCP tools with `visibility: ["app"]`, meaning only MCP apps can call them — the agent never sees them. This follows the same pattern as `generic_confirm_action` in the existing codebase.

### 5.1 Tools

#### `data_import_fix`

Called by the MCP app when the user types in the Fix field.

```python
@mcp.tool(name="data_import_fix", meta={
    "tags": [],  # Not exposed to agents
    "ui": {"visibility": ["app"]}
})
def data_import_fix(job_id: str, instruction: str) -> dict:
    """
    Interpret a free-text fix instruction and apply it to the staging data.

    The backend LLM interprets the instruction against the current staging
    state, applies changes, re-validates, and returns the updated state.

    Args:
        job_id: Import job ID (e.g. "IMP-001")
        instruction: Free-text fix instruction (e.g. "merge the duplicates, use the longer name")

    Returns:
        Updated staging state (same shape as data_import_upload response).
    """
    return data_import_service.fix(job_id=job_id, instruction=instruction)
```

#### `data_import_execute`

Called by the MCP app when the user clicks "Import".

```python
@mcp.tool(name="data_import_execute", meta={
    "tags": [],
    "ui": {"visibility": ["app"]}
})
def data_import_execute(job_id: str) -> dict:
    """
    Execute the import — create records in the ERP.

    Args:
        job_id: Import job ID

    Returns:
        Execution summary with created entity IDs.
    """
    return data_import_service.execute(job_id=job_id)
```

#### `data_import_get_state`

Called by the MCP app to refresh the current staging state (e.g. after reconnect).

```python
@mcp.tool(name="data_import_get_state", meta={
    "tags": [],
    "ui": {"visibility": ["app"]}
})
def data_import_get_state(job_id: str) -> dict:
    """
    Get the current staging state for an import job.

    Args:
        job_id: Import job ID

    Returns:
        Full staging state (mapping, rows, issues, batch questions).
    """
    return data_import_service.get_state(job_id=job_id)
```

### 5.2 Registration

All app-only tools are registered in `mcp_tools/data_import_tools.py` alongside `data_import_upload`. Registered via `mcp_tools/__init__.py`.

---

## 6. MCP App — `data-import.html`

One interactive HTML page in `mcp_apps_ui/`, registered as a resource in `server.py`. This is the entire Transform + Load UI.

### 6.1 Resource URI

`ui://data-import/result` — renders after `data_import_upload` returns.

### 6.2 Layout

The app has three sections that update dynamically based on the staging state:

**Header section:**
- Job summary: filename, entity type, row count
- Status badge: "Reviewing" / "Ready to import" / "Imported"

**Data section:**
- Column mapping table: source → target, confidence badges, transform descriptions
- Data grid: all rows with status badges (`ready` / `needs_review` / `auto_fixed` / `rejected`)
- Auto-fix log: collapsible list of automatic corrections applied ("'france' → FR", "'45 jours' → 45 days")

**Interaction section:**
- Batch question area: displays the current grouped question (if any)
- **Fix** text input field: free-text input for the user's instruction
- **Fix** submit button: sends the instruction via `app.callServerTool({name: "data_import_fix", ...})`
- **Import** button: enabled only when no errors remain. Calls `app.callServerTool({name: "data_import_execute", ...})`

After execution, the data section updates to show the created entity IDs with links.

### 6.3 Communication Pattern

```
MCP App                    Host (postMessage)           MCP Server
  │                              │                          │
  │  (initial render from        │                          │
  │   structured content data)   │                          │
  │                              │                          │
  │──callServerTool─────────────>│──data_import_fix────────>│
  │  (data_import_fix)           │                          │  ← backend LLM interprets
  │<──── updated staging state──│<───── tool result ───────│
  │                              │                          │
  │  (re-render data grid,       │                          │
  │   show next batch question)  │                          │
  │                              │                          │
  │──callServerTool─────────────>│──data_import_execute────>│
  │  (data_import_execute)       │                          │  ← service creates records
  │<──── execution result───────│<───── tool result ───────│
  │                              │                          │
  │  (show created entities)     │                          │
```

The MCP app is a self-contained HTML/JS iframe. All communication uses `app.callServerTool()` (postMessage JSON-RPC through the host), which forwards tool calls to the MCP server. The agent is not involved after the initial `data_import_upload` call.

### 6.4 Existing Pattern

This follows the same architecture as other interactive MCP apps in the codebase:

- `tariff-picker.html` — user selects tariff codes, app calls `app.callServerTool()` to submit
- `generic-confirm.html` — user confirms an action, app calls `generic_confirm_action` via `app.callServerTool()`
- `qc-inspection.html` — displays AI inspection results, submits disposition via `app.callServerTool()`

The key difference: `data-import.html` has a free-text input field (the Fix field), which is new. But the communication pattern (`app.callServerTool()` → MCP server → re-render) is identical.

---

## 7. Agent Prompt

The import agent is a **dedicated agent** — separate from the sales and production agents. Its job is trivially simple.

### 7.1 System Prompt

```
You are a data import assistant for Duck Inc's ERP system.

When the user wants to import data from a file, call `data_import_upload`
with the file source. The interactive import panel will take over from there —
the user will review, fix issues, and execute the import directly in the panel.

Do not fabricate file paths, data, or mappings. If unsure about the file
location, ask the user.

You handle data import only. If the user asks about orders, production,
or anything else, say it's outside your scope.
```

No workflow orchestration rules, no `next_step` contract, no multi-step sequencing. The agent calls one tool and summarises what happened.

### 7.2 Tool Visibility

| Tool | Available to Import Agent |
|------|--------------------------|
| `data_import_upload` | Yes |
| `crm_search_customers` | Yes (read-only) |
| `catalog_search_items` | Yes (read-only) |
| All other tools | No |

---

## 8. File Structure

New files to create:

```
services/data_import.py          — DataImportService
mcp_tools/data_import_tools.py   — MCP tools (data_import_upload + app-only fix/execute/get_state)
mcp_apps_ui/data-import.html     — interactive staging/import app
```

Files to modify:

```
schema.sql                       — add import_jobs + import_rows tables
services/__init__.py             — register data_import_service
mcp_tools/__init__.py            — register data_import_tools
server.py                        — register ui://data-import resource
config.py                        — add DATA_IMPORT_MODEL constant
```

---

## 9. Dependencies

### Python packages

| Package | Purpose | Already in requirements.txt? |
|---------|---------|------------------------------|
| `csv` | CSV parsing | stdlib |
| `json` | JSON parsing | stdlib |
| `difflib` | Fuzzy string matching | stdlib |
| `openpyxl` | Excel (.xlsx) reading | **No — add** |
| `chardet` | Encoding detection | **No — add** |

No heavy dependencies. `pdfplumber` is listed in DATA.md but can be deferred — for v1, PDF import goes through the vision model (same as image import), which handles both scanned and text-based PDFs.

### Config additions

```python
# config.py
DATA_IMPORT_MODEL = os.getenv("DATA_IMPORT_MODEL", "claude-4.6-opus")
```

---

## 10. ID Generation

Import job IDs: `IMP-{sequential}` (same pattern as `CUST-`, `SO-`, `MO-`, etc.)

Import row IDs: `{job_id}-R{sequential}` (e.g. `IMP-001-R01`, `IMP-001-R02`)

Use the existing `_next_id()` helper pattern from other services.

---

## 11. Activity Log Integration

Import execution and rollback produce activity log entries. Since these are triggered via app-only MCP tools (not agent-facing tools), they are logged directly by the service methods:

```python
# In data_import_service.execute():
activity_service.log("data_import", "import.executed", details={...})

# In data_import_service.rollback():
activity_service.log("data_import", "import.rolled_back", details={...})
```

Individual entity creation (e.g. `customer_service.create_customer`) already logs its own activity — no double-logging needed.

---

## 12. Rollback Strategy

`execute()` stores every created entity ID in `import_rows.created_entity_id`. `rollback()` iterates these in reverse order and deletes.

This is simple and correct for the demo because:
- Import only creates records (no updates in v1)
- No downstream cascade to worry about (a freshly imported customer has no orders yet)
- `DELETE FROM customers WHERE id = ?` is sufficient

If update support is added later, rollback would need to store the original values. Not needed now — avoid premature complexity.
