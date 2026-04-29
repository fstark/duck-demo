# Data Import — Implementation Plan

Step-by-step implementation plan for the data import feature. Each step produces a working, testable increment. A fresh agent can follow this top-to-bottom and know exactly what to do.

**Reference documents:**
- [DATA.md](DATA.md) — vision & feature overview
- [DATA_DESIGN.md](DATA_DESIGN.md) — technical design (data model, prompts, REST API, MCP app)
- [DEMO_FLOW.md](DEMO_FLOW.md) — end-to-end demo walkthrough

**Coding rules:** Follow [docs/CODING.md](../CODING.md) strictly. Key points:
- No magic strings or numbers — constants go in `config.py`
- Services use keyword-only arguments
- All quantities are INTEGER
- No defensive `if` guards for impossible conditions
- Never `except: pass` — always capture and surface errors

---

## Step 0 — Dependencies & Config

### 0a. Add Python packages

Edit `requirements.txt` — add:
```
openpyxl
chardet
```

Run `pip install -r requirements.txt` inside the venv.

### 0b. Add config constants

Edit `config.py` — add:
```python
DATA_IMPORT_MODEL = os.getenv("DATA_IMPORT_MODEL", "claude-4.6-opus")
```

This is the model used for all 4 LLM prompts (entity detection, column mapping, value transform, fix interpretation). Same model as QC inspection.

### 0c. Verify

```bash
source venv/bin/activate
python -c "import openpyxl, chardet; print('OK')"
python -c "import config; print(config.DATA_IMPORT_MODEL)"
```

---

## Step 1 — Database Schema

### What to do

Edit `schema.sql` — append the two new tables at the end, before any final comments. Copy the exact SQL from [DATA_DESIGN.md § 1.3](DATA_DESIGN.md):

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

### Also: admin reset

Edit `services/admin.py` — in the `reset_database` function, add `import_jobs` and `import_rows` to the list of tables that get `DELETE FROM` on reset. Find the section that deletes from all tables and add these two (order: `import_rows` before `import_jobs` due to FK relationship).

### Verify

```bash
source venv/bin/activate
python -c "import db; db.init_db(); print('Schema OK')"
```

### Test

Add a schema test in `tests/test_data_import.py` (new file) to verify the tables exist:

```python
"""Data import contract tests."""
import pytest
import db

pytestmark = pytest.mark.rest


def test_import_tables_exist():
    """Schema creates import_jobs and import_rows tables."""
    with db.db_conn() as conn:
        for table in ("import_jobs", "import_rows"):
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            assert row is not None, f"Table {table} not found"
```

Run: `pytest tests/test_data_import.py -v`

---

## Step 2 — Service Skeleton + File Parsing

### What to do

Create `services/data_import.py` with the `DataImportService` class. In this step, implement only:

1. **Class structure** — follow the pattern in `services/qc.py`: class with methods, singleton at module level
2. **Entity type registry** — the `ENTITY_SCHEMAS` dict from [DATA_DESIGN.md § 2](DATA_DESIGN.md)
3. **`_parse_file()`** — CSV/JSON parsing only (no Excel/image yet)
4. **`upload()` skeleton** — parse file, store in `import_jobs` + `import_rows`, return staging state. Skip LLM calls for now (hardcode entity_type and mapping as `None`).
5. **`get_state()`** — read job + rows from DB, build staging state dict
6. **`_build_staging_state()`** — assemble the full JSON state the MCP app will consume

#### File reading from `file://` URLs

The `source` parameter is a `file://` URL. Strip the scheme and read the file:

```python
import urllib.parse

def _read_source(self, source: str) -> tuple[bytes, str]:
    """Read file content from source URL. Returns (content_bytes, filename)."""
    if source.startswith("file://"):
        path = urllib.parse.unquote(urllib.parse.urlparse(source).path)
        with open(path, "rb") as f:
            return f.read(), os.path.basename(path)
    # Inline content (base64 or text) — handle later
    raise ValueError(f"Unsupported source scheme: {source}")
```

#### CSV parsing with delimiter sniffing

```python
import csv
import io
import chardet

def _parse_file(self, content: bytes, filename: str) -> tuple[list[dict], str]:
    """Parse file into rows. Returns (rows, format_info)."""
    ext = os.path.splitext(filename)[1].lower()

    if ext in (".csv", ".tsv", ".txt"):
        # Detect encoding
        detected = chardet.detect(content)
        encoding = detected.get("encoding") or "utf-8"
        text = content.decode(encoding)

        # Sniff delimiter
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(text[:4096])
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        rows = [dict(row) for row in reader]
        format_info = f"csv ({dialect.delimiter!r}-separated, {encoding})"
        return rows, format_info

    if ext == ".json":
        import json as json_mod
        data = json_mod.loads(content)
        if isinstance(data, list):
            return data, "json (array of objects)"
        raise ValueError("JSON must be an array of objects")

    raise ValueError(f"Unsupported file extension: {ext}")
```

#### upload() skeleton (no LLM yet)

```python
def upload(self, *, source: str, hint: str | None = None) -> dict:
    content, filename = self._read_source(source)
    rows, format_info = self._parse_file(content, filename)

    with db_conn() as conn:
        job_id = generate_id(conn, "IMP", "import_jobs")
        now = _sim_now(conn)

        conn.execute(
            "INSERT INTO import_jobs (id, source_filename, source_format, source_content, hint, status, row_count, columns_detected, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, filename, format_info, content.decode("utf-8", errors="replace"),
             hint, "staging", len(rows),
             json.dumps(list(rows[0].keys()) if rows else []), now),
        )

        for i, row in enumerate(rows, 1):
            row_id = f"{job_id}-R{i:02d}"
            conn.execute(
                "INSERT INTO import_rows (id, job_id, source_row, raw_data, status) VALUES (?, ?, ?, ?, ?)",
                (row_id, job_id, i, json.dumps(row), "pending"),
            )

        conn.commit()

    # TODO: Step 3 will add LLM calls here (detect, map, transform, validate, resolve)

    return self._build_staging_state(job_id)
```

#### Register the service

Edit `services/__init__.py` — add:
```python
from services.data_import import data_import_service
```

### Test

Add tests to `tests/test_data_import.py`:

```python
import json
import os
import tempfile
from services.data_import import data_import_service


def test_upload_csv_parses_rows():
    """upload() parses a CSV file and stores rows in staging tables."""
    csv_content = "Name;City;Country\nAlice;Paris;FR\nBob;London;GB\n"
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        f.write(csv_content)
        path = f.name

    try:
        result = data_import_service.upload(source=f"file://{path}")
        assert result["row_count"] == 2
        assert result["status"] in ("staging", "validated")
        assert len(result["rows"]) == 2
        assert result["rows"][0]["raw_data"]["Name"] == "Alice"
    finally:
        os.unlink(path)


def test_upload_csv_detects_semicolon_delimiter():
    """Semicolon-separated CSV is parsed correctly."""
    csv_content = "A;B;C\n1;2;3\n"
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        f.write(csv_content)
        path = f.name

    try:
        result = data_import_service.upload(source=f"file://{path}")
        assert result["row_count"] == 1
        assert "A" in result["rows"][0]["raw_data"]
    finally:
        os.unlink(path)


def test_get_state_returns_same_as_upload():
    """get_state() returns the same shape as upload()."""
    csv_content = "X;Y\n1;2\n"
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        f.write(csv_content)
        path = f.name

    try:
        upload_result = data_import_service.upload(source=f"file://{path}")
        state_result = data_import_service.get_state(upload_result["job_id"])
        assert state_result["job_id"] == upload_result["job_id"]
        assert state_result["row_count"] == upload_result["row_count"]
    finally:
        os.unlink(path)
```

Run: `pytest tests/test_data_import.py -v`

---

## Step 3 — LLM Integration (Detect, Map, Transform)

### What to do

Add the three LLM calls to `upload()` so it completes the full Extract phase. All LLM calls go through `myforterro.chat_completion()`.

Import at the top of `services/data_import.py`:
```python
from services.myforterro import chat_completion
import config
```

#### 3a. `_detect_entity(columns, sample_rows)` → entity type string

Use Prompt 1 from [DATA_DESIGN.md § 3.3](DATA_DESIGN.md). Call `chat_completion(model=config.DATA_IMPORT_MODEL, messages=[...])`. Parse the JSON response. Store `entity_type` on the job.

#### 3b. `_generate_mapping(columns, sample_rows, entity_schema)` → mapping plan

Use Prompt 2. The entity schema comes from `ENTITY_SCHEMAS[entity_type]`. Store the mapping plan as JSON in `import_jobs.mapping_plan`.

#### 3c. `_apply_transforms(job_id)` → updates `import_rows.mapped_data`

Two-tier approach:
1. **Python transforms** (no LLM): country code normalisation, phone E.164, email lowercase, integer parsing for obvious patterns (e.g. just digits). Implement these as a `PYTHON_TRANSFORMS` dict mapping transform names to functions.
2. **LLM transforms**: for anything the Python layer can't handle, batch all values into Prompt 3 and call `chat_completion` once.

After transforms, write `mapped_data` JSON to each `import_row`.

#### 3d. Wire into `upload()`

After parsing and storing rows, call in sequence:
```python
entity_type = self._detect_entity(columns, sample_rows)
# update job entity_type
mapping = self._generate_mapping(columns, sample_rows, ENTITY_SCHEMAS[entity_type])
# update job mapping_plan
self._apply_transforms(job_id)
```

Then proceed to validation (Step 4). For now, set job status to `"validated"` after transforms.

### Test — with LLM mocks

Follow the exact pattern from `tests/test_mcp_tariff.py`. Mock `chat_completion` at the import path `services.data_import.chat_completion`.

```python
from unittest.mock import patch

# Reuse the _FakeResponse pattern from test_mcp_tariff.py
class _FakeMessage:
    def __init__(self, content): self.content = content

class _FakeChoice:
    def __init__(self, content): self.message = _FakeMessage(content)

class _FakeResponse:
    def __init__(self, content): self.choices = [_FakeChoice(content)]


# Mock for entity detection
_DETECT_RESPONSE = _FakeResponse('{"entity_type": "customer", "confidence": 0.95, "reason": "has company, name, email columns"}')

# Mock for column mapping
_MAP_RESPONSE = _FakeResponse(json.dumps([
    {"source": "Name", "target": "name", "transform": "none", "confidence": 0.95},
    {"source": "City", "target": "city", "transform": "none", "confidence": 0.97},
    {"source": "Country", "target": "country", "transform": "ISO 3166-1 alpha-2", "confidence": 0.88},
]))

# Mock for value transform (only if LLM transforms are needed)
_TRANSFORM_RESPONSE = _FakeResponse(json.dumps([
    {"row": 1, "source_column": "Country", "value": "FR", "notes": "already ISO"},
    {"row": 2, "source_column": "Country", "value": "GB", "notes": "already ISO"},
]))


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE, _TRANSFORM_RESPONSE])
def test_upload_with_llm_detect_and_map(_mock, tmp_path):
    """upload() calls LLM for entity detection and column mapping."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City;Country\nAlice;Paris;FR\nBob;London;GB\n")

    result = data_import_service.upload(source=f"file://{csv_file}")
    assert result["entity_type"] == "customer"
    assert result["mapping"] is not None
    assert len(result["mapping"]) == 3
    assert _mock.call_count >= 2  # at least detect + map
```

Add a separate test for Python-only transforms (no LLM mock needed):

```python
def test_python_transforms_country_code():
    """Python transforms normalise 'france' to 'FR' without LLM."""
    # Test the _python_transform helper directly
    from services.data_import import DataImportService
    svc = DataImportService()
    assert svc._python_transform("country_code", "france") == "FR"
    assert svc._python_transform("country_code", "FR") == "FR"
    assert svc._python_transform("country_code", "gb") == "GB"


def test_python_transforms_email_lowercase():
    """Python transforms lowercase emails."""
    from services.data_import import DataImportService
    svc = DataImportService()
    assert svc._python_transform("lowercase", "Alice@Test.COM") == "alice@test.com"
```

Run: `pytest tests/test_data_import.py -v`

---

## Step 4 — Validation & Entity Resolution

### What to do

Add `_validate_rows()` and `_resolve_entities()` to the service. These run at the end of `upload()` after transforms.

#### 4a. `_validate_rows(job_id)`

For each row:
1. Check required fields from `ENTITY_SCHEMAS[entity_type]["fields"]`
2. Check type constraints (email format, country code is 2 chars, integer fields are numeric)
3. Write issues to `import_rows.issues` as JSON array
4. Set row status: `ready` if no errors, `needs_review` if warnings, `rejected` if errors

#### 4b. `_resolve_entities(job_id)`

For each row, compare against existing records in the target table:
1. Exact match on `dedup_keys` (email, tax_id) → confidence 1.0
2. Fuzzy match on `fuzzy_keys` (name, company, city) via `difflib.SequenceMatcher` → confidence = similarity score
3. Store matches in `import_rows.resolved_refs` as JSON

Thresholds (from [DATA_DESIGN.md § 3.4](DATA_DESIGN.md)):
- confidence ≥ 0.9 → auto-resolved, mark as `ready`
- 0.6 ≤ confidence < 0.9 → `needs_review` + `possible_duplicate` issue
- confidence < 0.6 → new record, mark as `ready`

#### 4c. `_group_issues(job_id)` → batch questions

Group identical issues across rows (e.g. 15 rows missing phone → one batch question). Return a list of batch question objects:

```python
{
    "question": "Rows 1 and 4 may be the same customer (DuckFan Paris SARL). Merge or keep both?",
    "issue_type": "possible_duplicate",
    "rows": [1, 4],
    "suggestion": "merge",
}
```

Store the batch questions in the staging state returned by `_build_staging_state()`.

#### 4d. Update `upload()` pipeline

After `_apply_transforms`:
```python
self._validate_rows(job_id)
self._resolve_entities(job_id)
batch_questions = self._group_issues(job_id)
# Update job status to 'validated'
# Update issues_summary
```

### Test

```python
def test_validate_flags_missing_required_field():
    """Validation flags rows missing the required 'name' field."""
    # Create a CSV where one row has no name
    csv = "Company;Email\nTestCorp;test@example.com\n"
    # (Upload with mocked LLM that maps Company→company, Email→email — no name mapping)
    # Assert the row has status 'rejected' or 'needs_review' and an issue about missing 'name'


def test_resolve_entities_detects_duplicate():
    """Entity resolution flags a row matching an existing customer."""
    # The test DB has CUST-0101 (Alice Testworth, alice@testcorp.example)
    # Upload a CSV with "alice@testcorp.example" — should flag as possible_duplicate
    # Assert resolved_refs shows match to CUST-0101


def test_group_issues_batches_similar():
    """Multiple rows with same issue type get grouped into one batch question."""
    # Upload CSV with 3 rows all missing phone
    # Assert batch_questions has 1 entry covering all 3 rows
```

These tests need LLM mocks for the detect/map/transform steps. Use the same `side_effect` pattern from Step 3.

Run: `pytest tests/test_data_import.py -v`

---

## Step 5 — Fix Endpoint (Service + REST)

### What to do

#### 5a. `fix()` service method

```python
def fix(self, *, job_id: str, instruction: str) -> dict:
    """Interpret a free-text fix instruction and apply it."""
```

Logic:
1. Load current staging state with `_build_staging_state(job_id)`
2. Load the current batch question (first unresolved)
3. Call `chat_completion` with Prompt 4 from [DATA_DESIGN.md § 3.3](DATA_DESIGN.md)
4. Parse the response → list of actions
5. Apply each action:
   - `merge`: call `_merge_rows()`, mark absorbed rows as `merged`
   - `set_value`: update `mapped_data` for the target row
   - `reject`: set row status to `rejected`
   - `keep`: no change (acknowledge)
6. Re-validate affected rows (`_validate_rows` on specific rows)
7. Re-group issues (`_group_issues`)
8. Return updated staging state

For simple deterministic instructions (e.g. entire instruction is "reject" or "keep both"), bypass the LLM and apply directly in Python. Only call the LLM when interpretation is needed.

#### 5b. REST endpoints

Create `api_routes/data_import_routes.py`:

```python
"""REST endpoints for data import (MCP app → backend)."""

from api_routes._common import _json, cors_handler
from services.data_import import data_import_service


def register(mcp):
    """Register data import REST routes."""

    @mcp.custom_route("/api/data-import/{job_id}/fix", methods=["POST", "OPTIONS"])
    @cors_handler(["POST"])
    async def api_data_import_fix(request):
        job_id = request.path_params["job_id"]
        body = await request.json()
        instruction = body.get("instruction", "")
        result = data_import_service.fix(job_id=job_id, instruction=instruction)
        return _json(result)

    @mcp.custom_route("/api/data-import/{job_id}/execute", methods=["POST", "OPTIONS"])
    @cors_handler(["POST"])
    async def api_data_import_execute(request):
        job_id = request.path_params["job_id"]
        result = data_import_service.execute(job_id=job_id)
        return _json(result)

    @mcp.custom_route("/api/data-import/{job_id}/state", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_data_import_state(request):
        job_id = request.path_params["job_id"]
        result = data_import_service.get_state(job_id=job_id)
        return _json(result)
```

#### 5c. Register routes

Edit `api_routes/__init__.py` — import and register:
```python
from api_routes import data_import_routes
# in register_all_routes():
data_import_routes.register(mcp)
```

### Test

Service-level tests (mock LLM):

```python
@patch("services.data_import.chat_completion", side_effect=[
    _DETECT_RESPONSE, _MAP_RESPONSE, _TRANSFORM_RESPONSE,  # upload
    _FakeResponse(json.dumps({  # fix
        "actions": [{"type": "merge", "rows": [1, 2], "merged_values": {"name": "Alice", "city": "Paris"}}],
        "reasoning": "merged as requested",
    })),
])
def test_fix_merges_duplicate_rows(_mock, tmp_path):
    """fix() merges rows when instructed."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City\nAlice;Paris\nAlice;Paris\n")

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]

    fix_result = data_import_service.fix(job_id=job_id, instruction="merge the duplicates")
    # After merge, should have 1 active row, 1 merged
    active_rows = [r for r in fix_result["rows"] if r["status"] != "merged"]
    assert len(active_rows) == 1
```

REST-level tests:

```python
def test_fix_endpoint_returns_200(rest_client):
    """POST /api/data-import/{job_id}/fix returns 200."""
    # First create a job (needs setup — use a fixture or direct DB insert)
    # Then POST to /api/data-import/IMP-0001/fix with instruction
    # Assert 200 and response has 'rows' key


def test_state_endpoint_returns_200(rest_client):
    """GET /api/data-import/{job_id}/state returns 200."""
    # Assert 200 and response matches staging state shape


def test_state_endpoint_404_for_missing_job(rest_client):
    """GET /api/data-import/NOPE/state returns 404."""
    resp = rest_client.get("/api/data-import/NOPE/state")
    assert resp.status_code == 404
```

Run: `pytest tests/test_data_import.py -v`

---

## Step 6 — Execute & Rollback

### What to do

#### 6a. `execute(job_id)` service method

```python
def execute(self, *, job_id: str) -> dict:
    """Execute import — create records via service layer."""
```

Logic:
1. Load job, verify status is `validated` or `ready_to_execute`
2. For each row with status `ready`:
   - Look up the service method from `ENTITY_SCHEMAS[entity_type]["service_create"]`
   - Call it (e.g. `customer_service.create_customer(**mapped_data)`)
   - Store created entity ID in `import_rows.created_entity_id`
   - Set row status to `imported`
3. Update job status to `executed`, set `executed_at`
4. Log to activity: `activity_service.log_activity("mcp:data_import", "data_import", "import.executed", "import_job", job_id, details={...})`
5. Return execution summary

**Important:** Import the target service dynamically or via the registry. For v1, there's only `customer`, so a simple `if entity_type == "customer": customer_service.create_customer(...)` is fine. No need for dynamic dispatch yet.

#### 6b. `rollback(job_id)` service method

```python
def rollback(self, *, job_id: str) -> dict:
    """Undo an executed import by deleting created records."""
```

Logic:
1. Load job, verify status is `executed`
2. For each row with `created_entity_id`, `DELETE FROM {table} WHERE id = ?`
3. Reset row status to `ready`, clear `created_entity_id`
4. Update job status to `rolled_back`
5. Log to activity

### Test

```python
def test_execute_creates_customers(rest_client):
    """execute() creates customer records in the customers table."""
    # Setup: insert a validated import job + rows directly into DB
    # with mapped_data containing valid customer fields
    # Call execute()
    # Assert customers exist in customers table
    # Assert import_rows have created_entity_id set


def test_rollback_deletes_created_customers():
    """rollback() removes customers created by execute()."""
    # Setup: execute an import, then rollback
    # Assert customers no longer exist
    # Assert job status is 'rolled_back'


def test_execute_endpoint_returns_200(rest_client):
    """POST /api/data-import/{job_id}/execute returns 200."""
    # Test via REST endpoint
```

Run: `pytest tests/test_data_import.py -v`

---

## Step 7 — MCP Tool

### What to do

Create `mcp_tools/data_import_tools.py`:

```python
"""MCP tool for data import."""

from mcp_tools._common import log_tool
from services.data_import import data_import_service


def register(mcp):
    """Register data import tools."""

    @mcp.tool(
        name="data_import_upload",
        meta={
            "tags": ["data_import"],
            "ui": {
                "resourceUri": "ui://data-import/result",
                "visibility": ["model", "app"],
            },
        },
    )
    @log_tool("data_import_upload")
    def data_import_upload(
        source: str,
        hint: str | None = None,
    ) -> dict:
        """Upload a file for import into the ERP.

        The file is parsed, the entity type is auto-detected, columns are mapped,
        transforms are applied, validation and entity resolution are run — all in
        one call. The result appears in the interactive import panel where you can
        review and fix issues before importing.

        Parameters:
            source: File path URL (file:///...) or inline content
            hint: Optional description of the data
        """
        return data_import_service.upload(source=source, hint=hint)
```

#### Register the tool

Edit `mcp_tools/__init__.py`:
1. Add `from mcp_tools import data_import_tools` to the imports
2. Add `data_import_tools` to the `_MODULES` list

#### Register the MCP app resource

Edit `server.py` — add a resource registration:
```python
@mcp.resource("ui://data-import/result", mime_type="text/html;profile=mcp-app")
def get_data_import_ui() -> str:
    with open("mcp_apps_ui/data-import.html", "r") as f:
        return f.read()
```

### Test

```python
@pytest.mark.mcp
@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_mcp_data_import_upload(_mock, mcp_app, tmp_path):
    """MCP tool data_import_upload returns staging state."""
    csv_file = tmp_path / "customers.csv"
    csv_file.write_text("Name;Email\nTest;test@example.com\n")

    tool = mcp_app._tool_manager._tools["data_import_upload"]
    result = tool.fn(source=f"file://{csv_file}")
    assert "job_id" in result
    assert result["row_count"] == 1
```

Run: `pytest tests/test_data_import.py -v -m mcp`

---

## Step 8 — MCP App (HTML)

### What to do

Create `mcp_apps_ui/data-import.html`. This is a self-contained HTML+JS page (React, inline script — same pattern as `qc-inspection.html` and `tariff-picker.html`).

#### Data input

The app receives the initial structured content via `window.__MCP_STRUCTURED_CONTENT__` (set by the MCP client when rendering the tool response). The structured content is the staging state dict returned by `data_import_upload`.

#### Layout (three sections)

**Header:**
- Job ID, filename, entity type, row count
- Status badge (`Reviewing` / `Ready to import` / `Imported`)

**Data section:**
- Column mapping table: source → target, confidence badge (green ≥ 0.85, yellow ≥ 0.70, red < 0.70), transform description
- Data grid: rows with status badges. Each cell can have an annotation icon for auto-fixes.
- Auto-fix log (collapsible): list of automatic corrections

**Interaction section:**
- Batch question text (if any unresolved questions)
- Fix input field + Fix button
- Import button (disabled unless all rows are `ready` or `needs_review` with no errors)

#### Fetch calls

```javascript
// Fix button click
async function handleFix(instruction) {
    setLoading(true);
    const resp = await fetch(`/api/data-import/${jobId}/fix`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({instruction}),
    });
    const newState = await resp.json();
    setState(newState);  // re-render everything
    setLoading(false);
}

// Import button click
async function handleExecute() {
    setLoading(true);
    const resp = await fetch(`/api/data-import/${jobId}/execute`, {
        method: "POST",
    });
    const result = await resp.json();
    setState(result);  // show execution summary
    setLoading(false);
}
```

#### Styling

Follow the existing MCP app styles — minimal CSS, dark/light theme support via `prefers-color-scheme`, compact tables. Look at `qc-inspection.html` for the exact CSS patterns (badge styles, table layout, button styles, body margin reset).

**Important:** Include the body margin/padding reset that was added in the QC inspection fix (to avoid the 16×8 px iframe bug):
```css
body { margin: 0; padding: 8px; }
```

### Test

No automated test — the MCP app is a UI component. Manual test:
1. Start the server: `source venv/bin/activate && python server.py`
2. Use the MCP client to call `data_import_upload` with the sample CSV
3. Verify the panel renders correctly
4. Type a fix instruction, verify the panel updates
5. Click Import, verify the result summary

---

## Step 9 — Seed Data for Scenarios

### What to do

The data import feature doesn't need seed data in `scenarios/` since import jobs are created on demand. However, ensure the sample CSV from the demo can run through the full pipeline.

#### 9a. Add the sample CSV to test data

In `tests/test_data_import.py`, add a test that uses the actual demo CSV:

```python
DEMO_CSV = (
    "Kd-Nr;Firma;Ansprechpartner;E-Mail;Straße;PLZ;Ort;Land;Telefon;Zahlungsziel\n"
    "101;DuckFan Paris SARL;Jean Dupont;jean@duckfan-paris.example;12 Rue du Canard;75001;Paris;france;+33 1 23 45 67 89;30 Tage\n"
    "102;QuackShop London;;orders@quackshop.co.uk;42 Mallard Lane;SW1A 1AA;London;GB;+44 20 1234 5678;\n"
    "103;Enten-Welt GmbH;Hans Müller;hans@entenwelt.example;Entenstraße 7;10115;Berlin;DE;+49 30 9876543;60 Tage\n"
    "104;DuckFan Paris SARL;J. Dupont;j.dupont@duckfan-paris.example;12 Rue du Canard;75001;Paris;FR;;45 jours\n"
)


@patch("services.data_import.chat_completion", side_effect=[
    _DETECT_RESPONSE,
    _FakeResponse(json.dumps([
        {"source": "Kd-Nr", "target": "external_ref", "transform": "none", "confidence": 0.72},
        {"source": "Firma", "target": "company", "transform": "none", "confidence": 0.95},
        {"source": "Ansprechpartner", "target": "name", "transform": "none", "confidence": 0.91},
        {"source": "E-Mail", "target": "email", "transform": "lowercase", "confidence": 0.98},
        {"source": "Straße", "target": "address_line1", "transform": "none", "confidence": 0.94},
        {"source": "PLZ", "target": "postal_code", "transform": "none", "confidence": 0.96},
        {"source": "Ort", "target": "city", "transform": "none", "confidence": 0.97},
        {"source": "Land", "target": "country", "transform": "ISO 3166-1 alpha-2", "confidence": 0.88},
        {"source": "Telefon", "target": "phone", "transform": "none", "confidence": 0.85},
        {"source": "Zahlungsziel", "target": "payment_terms", "transform": "parse integer from text", "confidence": 0.79},
    ])),
    _FakeResponse(json.dumps([
        {"row": 1, "source_column": "Zahlungsziel", "value": 30, "notes": "30 Tage → 30"},
        {"row": 4, "source_column": "Zahlungsziel", "value": 45, "notes": "45 jours → 45"},
    ])),
])
def test_demo_csv_full_pipeline(_mock, tmp_path):
    """The demo German CSV goes through the full upload pipeline."""
    csv_file = tmp_path / "Kundenstammdatenübernahme_Altdatenbank.csv"
    csv_file.write_text(DEMO_CSV, encoding="utf-8")

    result = data_import_service.upload(source=f"file://{csv_file}")
    assert result["entity_type"] == "customer"
    assert result["row_count"] == 4
    # Should detect the duplicate (rows 1 and 4)
    batch_questions = result.get("batch_questions", [])
    dup_questions = [q for q in batch_questions if q.get("issue_type") == "possible_duplicate"]
    assert len(dup_questions) >= 1
```

### 9b. Add import tables to `tests/seed_test_data.py`

Add empty entries so the test DB has the tables ready:
```python
IMPORT_JOBS = []
IMPORT_ROWS = []
```

And add to `TABLE_DATA`:
```python
("import_jobs", IMPORT_JOBS),
("import_rows", IMPORT_ROWS),
```

Run: `pytest tests/test_data_import.py -v`

---

## Step 10 — Integration & Polish

### 10a. Activity log integration

In `services/data_import.py`, after `execute()` creates records:
```python
from services.activity import log_activity

log_activity(
    actor="mcp:data_import",
    category="data_import",
    action="import.executed",
    entity_type="import_job",
    entity_id=job_id,
    details={"created_count": len(created), "entity_type": entity_type},
)
```

Same for `rollback()`:
```python
log_activity(
    actor="mcp:data_import",
    category="data_import",
    action="import.rolled_back",
    entity_type="import_job",
    entity_id=job_id,
)
```

### 10b. Error handling

- `upload()` with invalid file path → return `{"error": "File not found: ..."}` (not an exception — surface the error)
- `fix()` with invalid job_id → raise `ValueError`, caught by REST route → 404
- `execute()` on non-validated job → raise `ValueError`
- LLM returns unparseable JSON → log warning, fall back to empty mapping / no transforms (degrade gracefully, don't crash)

### 10c. Edge cases in parsing

- Empty CSV (headers only, no data rows) → `row_count: 0`, no mapping attempt
- CSV with only 1 row → works fine (sample_rows has 1 entry)
- Non-UTF-8 encoding (e.g. latin-1 with French accents) → `chardet` detects, decode succeeds

### 10d. Final test run

```bash
source venv/bin/activate
pytest tests/test_data_import.py -v
pytest tests/ -v  # full suite — make sure nothing broke
```

---

## Test Strategy Summary

| What | How | LLM handling |
|------|-----|-------------|
| Schema exists | Direct SQL query | N/A |
| CSV parsing | Service call with temp files | No LLM involved |
| Delimiter sniffing | Service call with `;` and `,` files | No LLM involved |
| Entity detection + mapping | Service call, mock `chat_completion` | `@patch` with `_FakeResponse` |
| Python transforms | Call `_python_transform` directly | No LLM involved |
| LLM transforms | Service call, mock `chat_completion` | `@patch` with `_FakeResponse` |
| Validation | Service call (post-transform) | Mock LLM for upload pipeline |
| Entity resolution | Service call, assert against test DB customers | Mock LLM for upload pipeline |
| Fix instruction | Service call, mock `chat_completion` for Prompt 4 | `@patch` with `side_effect` list |
| Execute | Service call, assert customer records created | Mock LLM for upload pipeline |
| Rollback | Service call, assert records deleted | No LLM involved |
| REST endpoints | `rest_client.get/post`, assert status + shape | Mock LLM for upload pipeline |
| MCP tool | Direct tool function call | Mock LLM for upload pipeline |
| MCP app | Manual testing only | N/A |

**Mock pattern:** Always `@patch("services.data_import.chat_completion", ...)`. Use `side_effect=[resp1, resp2, ...]` when multiple LLM calls happen in sequence (upload calls detect + map + transform). Use `return_value=` when only one call is expected (fix).

**No live LLM calls in tests.** Every test that touches an LLM path uses mocks. The `_FakeResponse` / `_FakeChoice` / `_FakeMessage` classes follow the OpenAI response shape and are reused across all test functions.

---

## File Checklist

New files:
- [ ] `services/data_import.py`
- [ ] `mcp_tools/data_import_tools.py`
- [ ] `api_routes/data_import_routes.py`
- [ ] `mcp_apps_ui/data-import.html`
- [ ] `tests/test_data_import.py`

Modified files:
- [ ] `requirements.txt` — add `openpyxl`, `chardet`
- [ ] `config.py` — add `DATA_IMPORT_MODEL`
- [ ] `schema.sql` — add `import_jobs`, `import_rows` tables
- [ ] `services/__init__.py` — import `data_import_service`
- [ ] `services/admin.py` — add import tables to reset
- [ ] `mcp_tools/__init__.py` — add `data_import_tools` to `_MODULES`
- [ ] `api_routes/__init__.py` — register `data_import_routes`
- [ ] `server.py` — add `ui://data-import/result` resource
- [ ] `tests/seed_test_data.py` — add empty import table entries to `TABLE_DATA`

---

## Implementation Order & Dependencies

```
Step 0 (deps + config)
  │
  ▼
Step 1 (schema) ─────────────────────── can test immediately
  │
  ▼
Step 2 (service skeleton + parsing) ─── can test (no LLM)
  │
  ▼
Step 3 (LLM detect + map + transform) ─ can test (mocked LLM)
  │
  ▼
Step 4 (validate + entity resolution) ─ can test (mocked LLM)
  │
  ▼
Step 5 (fix endpoint) ──────────────── can test (mocked LLM + REST)
  │
  ▼
Step 6 (execute + rollback) ────────── can test (service + REST)
  │
  ▼
Step 7 (MCP tool) ──────────────────── can test (mocked LLM)
  │
  ▼
Step 8 (MCP app HTML) ──────────────── manual test only
  │
  ▼
Step 9 (seed data + demo CSV test) ── integration test
  │
  ▼
Step 10 (polish) ───────────────────── full test suite
```

Each step is independently testable. An agent should commit after each step passes tests.
