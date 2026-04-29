# Data Import — Technical Design

This document is the implementation blueprint for the data import feature described in [DATA.md](DATA.md). It covers the data model, service architecture, MCP tools, LLM prompts, and the `next_step` orchestration contract.

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
staging → mapped → validated → ready_to_execute → executed
                                                 → rolled_back
```

- `staging` — file parsed, rows extracted, entity type and columns detected
- `mapped` — column→field mapping plan generated
- `validated` — transforms applied, validation run, entity resolution done, issues flagged
- `ready_to_execute` — all issues resolved (or accepted), preview generated
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

Stateless, all state in the database. Methods correspond 1:1 to MCP tools.

#### Core Methods

| Method | Input | Does | Returns |
|--------|-------|------|---------|
| `upload(source, hint)` | File URL or content | Parse file, detect format, extract rows, detect entity type, generate mapping via LLM | Job summary + mapping plan |
| `validate(job_id)` | Job ID | Apply transforms, run schema validation, run entity resolution, flag issues | Issue summary |
| `fix_issue(job_id, issue_type, rows, action, preferences)` | Job + issue details | Apply merge/correction, re-validate affected rows | Updated status |
| `preview(job_id)` | Job ID | Build create/update/skip summary from current staging state | Preview object |
| `execute(job_id)` | Job ID | Call service layer for each ready row, record created IDs | Execution result |
| `rollback(job_id)` | Job ID | Delete created records by stored IDs | Rollback result |

#### Internal Methods (not exposed via MCP)

| Method | Purpose |
|--------|---------|
| `_parse_file(content, filename)` | Detect format, extract rows as list of dicts |
| `_detect_entity(columns, sample_rows)` | LLM call → entity type |
| `_generate_mapping(columns, sample_rows, entity_schema)` | LLM call → mapping plan |
| `_apply_transforms(job_id)` | Apply mapping + transforms to all rows, write `mapped_data` |
| `_validate_rows(job_id)` | Schema validation, write issues |
| `_resolve_entities(job_id)` | Fuzzy matching against existing records, write `resolved_refs` |
| `_merge_rows(job_id, primary_row, absorbed_rows, preferences)` | Combine rows, mark absorbed as `merged` |

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

#### Prompt 3 — Value Transform

Input: raw value, source column, target field, transform description.
Output: transformed value.

This is called **per-row per-column** only for columns that need LLM-based transforms (not for simple ones like lowercase). Simple transforms (country lookup, phone normalisation) are handled in Python code — the LLM is the fallback for ambiguous cases.

```
Transform this value for import into an ERP system.
Source column: {source_column}
Target field: {target_field} ({field_type})
Transform needed: {transform_description}
Raw value: {raw_value}
Context (other values in this row): {row_context}

Respond with ONLY a JSON object: {"value": ..., "notes": "..."}
```

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

## 4. MCP Tools

### 4.1 Tool Definitions

All tools are tagged `data_import` for the dedicated import agent. They are not exposed to the sales or production agents.

#### `data_import_upload`

```python
@mcp.tool(name="data_import_upload", meta={
    "tags": ["data_import"],
    "ui": {
        "resourceUri": "ui://data-import-mapping/result",
        "visibility": ["model", "app"]
    }
})
def data_import_upload(
    source: str,
    hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Upload a file for import into the ERP.

    The file is parsed, the entity type is auto-detected, and a column mapping
    is generated. Review the mapping in the response, then confirm or adjust.

    Parameters:
        source: File path URL (file:///...) or inline content (text/base64)
        hint: Optional description of the data ("customer list from old CRM")

    Returns:
        Job summary with detected entity type, column mapping, and preview rows.
    """
```

#### `data_import_validate`

```python
@mcp.tool(name="data_import_validate", meta={
    "tags": ["data_import"],
    "ui": {
        "resourceUri": "ui://data-import-issues/result",
        "visibility": ["model", "app"]
    }
})
def data_import_validate(job_id: str) -> Dict[str, Any]:
    """
    Validate all rows in a staging import job.

    Applies transforms, checks required fields, detects duplicates,
    and resolves references to existing ERP records.

    Parameters:
        job_id: The import job ID (e.g. 'IMP-001')

    Returns:
        Validation summary with issue counts and details.
    """
```

#### `data_import_fix_issue`

```python
@mcp.tool(name="data_import_fix_issue", meta={"tags": ["data_import"]})
def data_import_fix_issue(
    job_id: str,
    issue_type: str,
    rows: List[int],
    action: str,
    merge_preferences: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fix a flagged issue in a staging import job.

    Parameters:
        job_id: The import job ID
        issue_type: Type of issue ('possible_duplicate', 'missing_field', etc.)
        rows: Source row numbers affected
        action: Resolution action ('merge', 'keep_both', 'set_value', 'reject')
        merge_preferences: For merges, natural language instructions
                          ("use the longer name", "keep both emails")

    Returns:
        Updated row status.
    """
```

#### `data_import_preview`

```python
@mcp.tool(name="data_import_preview", meta={
    "tags": ["data_import"],
    "ui": {
        "resourceUri": "ui://data-import-preview/result",
        "visibility": ["model", "app"]
    }
})
def data_import_preview(job_id: str) -> Dict[str, Any]:
    """
    Show a preview of what the import will create or update.

    Parameters:
        job_id: The import job ID

    Returns:
        Preview with records to create, update, and skip.
    """
```

#### `data_import_execute`

```python
@mcp.tool(name="data_import_execute", meta={
    "tags": ["data_import"],
    "ui": {
        "resourceUri": "ui://data-import-result/result",
        "visibility": ["model", "app"]
    }
})
def data_import_execute(job_id: str) -> Dict[str, Any]:
    """
    Execute the import — create records in the ERP.

    Uses the standard service layer (same as crm_create_customer, etc.)
    so all business rules, validation, and activity logging apply.

    Parameters:
        job_id: The import job ID

    Returns:
        Execution result with created entity IDs.
    """
```

#### `data_import_rollback`

```python
@mcp.tool(name="data_import_rollback", meta={"tags": ["data_import"]})
def data_import_rollback(job_id: str) -> Dict[str, Any]:
    """
    Undo an executed import by deleting all created records.

    Parameters:
        job_id: The import job ID (must be in 'executed' status)

    Returns:
        Rollback summary.
    """
```

### 4.2 Tool Registration

In `mcp_tools/data_import_tools.py`, following the standard pattern:

```python
def register(mcp):
    # ... all @mcp.tool definitions above
```

Registered via `mcp_tools/__init__.py`:

```python
from mcp_tools import data_import_tools
# in register_all_tools():
data_import_tools.register(mcp)
```

### 4.3 Read-Only Tools for Entity Resolution

The import agent also needs read access to existing ERP data for fuzzy matching. Rather than duplicating tools, expose a small subset of existing tools to the import agent:

- `crm_search_customers` — search existing customers
- `catalog_search_items` — search existing items
- `inventory_list_items` — list items by type

These are already tagged `shared` and need no changes.

---

## 5. The `next_step` Orchestration Contract

Every import tool response includes a `next_step` field. This is the mechanism that keeps the agent on track across multiple tool calls (see [DEMO_FLOW.md](DEMO_FLOW.md) for the full rationale).

### 5.1 Contract Shape

```python
next_step: Optional[dict] = {
    "tool": str,              # MCP tool name to call next
    "arguments": dict,        # arguments for that tool
    "awaits": Optional[str],  # null = call immediately; "user_confirmation" / "user_decision" = wait
    "description": str,       # human-readable instruction for the agent
    "options": list[str],     # optional: suggested user responses (for decisions)
}
```

### 5.2 Rules

| `next_step` value | Agent behaviour |
|--------------------|----------------|
| `null` | Workflow complete. Summarise result to user. |
| `awaits` is `null` | Call `tool` immediately with `arguments`. Do not talk to user first. |
| `awaits` is set | Present `message` to user. Wait for response. Then call `tool`. |

### 5.3 Pipeline Wiring

Each service method builds its own `next_step` based on the new job status:

| After method | Job status | `next_step` |
|-------------|------------|-------------|
| `upload()` | `mapped` | `{tool: "data_import_validate", awaits: "user_confirmation"}` — user reviews mapping first |
| `validate()` — no issues | `ready_to_execute` | `{tool: "data_import_preview", awaits: null}` — auto-advance |
| `validate()` — has issues | `validated` | `{tool: "data_import_fix_issue", awaits: "user_decision"}` — user resolves |
| `fix_issue()` — issues remain | `validated` | `{tool: "data_import_fix_issue", awaits: "user_decision"}` — next issue |
| `fix_issue()` — all resolved | `validated` | `{tool: "data_import_preview", awaits: null}` — auto-advance |
| `preview()` | `ready_to_execute` | `{tool: "data_import_execute", awaits: "user_confirmation"}` — user confirms |
| `execute()` | `executed` | `null` — done |
| `rollback()` | `rolled_back` | `null` — done |

### 5.4 Collapsible Design

The pipeline is wired so steps can be **collapsed server-side** without changing the agent prompt or the `next_step` contract. For example, `upload()` could internally call `_apply_transforms` + `_validate_rows` + `_resolve_entities` and return directly in `validated` status — the `next_step` would then point to `data_import_fix_issue` (if issues) or `data_import_preview` (if clean).

Start with separate steps (easier to debug), collapse later for a snappier demo.

---

## 6. MCP Apps

Four small HTML pages in `mcp_apps_ui/`, registered as resources in `server.py`.

### 6.1 Resource URIs

| MCP App | Resource URI | Renders After |
|---------|-------------|---------------|
| `data-import-mapping.html` | `ui://data-import-mapping/result` | `data_import_upload` |
| `data-import-issues.html` | `ui://data-import-issues/result` | `data_import_validate` |
| `data-import-preview.html` | `ui://data-import-preview/result` | `data_import_preview` |
| `data-import-result.html` | `ui://data-import-result/result` | `data_import_execute` |

All are read-only. No interactive controls. Data is passed via the structured content of the tool response.

### 6.2 `data-import-mapping.html`

Displays:
- Source column → target field table
- Confidence badge per row (green ≥ 0.85, yellow ≥ 0.70, red < 0.70)
- Transform description
- Sample values (first 2–3 rows)

### 6.3 `data-import-issues.html`

Displays:
- Summary bar: ready / needs review / rejected counts
- Issue list grouped by severity (error → warning → info)
- Per-row status badge
- Duplicate highlight (side-by-side comparison of matched rows)

### 6.4 `data-import-preview.html`

Displays:
- Records to create (table with all fields)
- Records to update (with diff: old value → new value)
- Skipped/rejected count

### 6.5 `data-import-result.html`

Displays:
- Created entity list (ID, name, type)
- Links to entity detail pages (via `ui_url`)
- Error list (if any rows failed)

---

## 7. Agent Prompt

The import agent is a **dedicated agent** — separate from the sales and production agents. It has access only to `data_import_*` tools plus read-only lookups.

### 7.1 System Prompt

```
You are a data import assistant for Duck Inc's ERP system.

You help users import data from external files (CSV, Excel, JSON, images, PDFs)
into the ERP. You detect the data format, map columns to ERP fields, validate
the data, resolve duplicates, and execute the import.

CRITICAL OPERATING RULES:

1) Tool-driven workflow:
   - Start every import with `data_import_upload`.
   - After EVERY tool response, check the `next_step` field:
     - If `next_step` is null → workflow complete, summarise the result.
     - If `next_step.awaits` is null → immediately call `next_step.tool`
       with `next_step.arguments`. Do NOT talk to the user first.
     - If `next_step.awaits` is set → present the `message` to the user,
       wait for their response, then call the indicated tool.
   - NEVER skip a step or decide on your own which tool to call next.
   - ALWAYS relay the `message` field from each tool response to the user.

2) Do not fabricate data:
   - Never invent mappings, entity IDs, or field values.
   - If unsure, ask the user.

3) Stay focused:
   - You handle data import only. If the user asks about orders, production,
     or anything else, say it's outside your scope.

4) User decisions:
   - When presenting issues (duplicates, missing fields), clearly state the
     options and wait for the user's choice.
   - For merge decisions, ask which values to keep if not obvious.
```

### 7.2 Tool Visibility

| Tool | Available to Import Agent |
|------|--------------------------|
| `data_import_upload` | Yes |
| `data_import_validate` | Yes |
| `data_import_fix_issue` | Yes |
| `data_import_preview` | Yes |
| `data_import_execute` | Yes |
| `data_import_rollback` | Yes |
| `crm_search_customers` | Yes (read-only, for entity resolution display) |
| `catalog_search_items` | Yes (read-only) |
| All other tools | No |

---

## 8. File Structure

New files to create:

```
services/data_import.py          — DataImportService
mcp_tools/data_import_tools.py   — MCP tool definitions
api_routes/data_import_routes.py — REST endpoints (thin wrappers)
mcp_apps_ui/data-import-mapping.html
mcp_apps_ui/data-import-issues.html
mcp_apps_ui/data-import-preview.html
mcp_apps_ui/data-import-result.html
```

Files to modify:

```
schema.sql                       — add import_jobs + import_rows tables
services/__init__.py             — register data_import_service
mcp_tools/__init__.py            — register data_import_tools
api_routes/__init__.py           — register data_import_routes
server.py                        — register ui:// resources for MCP apps
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

Import execution produces activity log entries via the existing `TOOL_ACTION_MAP` in `_common.py`:

```python
TOOL_ACTION_MAP["data_import_execute"] = ("data_import", "import.executed")
TOOL_ACTION_MAP["data_import_rollback"] = ("data_import", "import.rolled_back")
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
