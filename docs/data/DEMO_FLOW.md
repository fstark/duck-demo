# Demo Flow — "The German Spreadsheet"

Customer import from a semicolon-separated CSV with German column headers, inconsistent formatting, and a near-duplicate row.

---

## The Agent Reliability Problem

Multi-step workflows are the #1 failure mode with LLM agents. After 4–5 tool calls the agent tends to:
- Summarise what it did and stop (forgetting there are remaining steps)
- Hallucinate the result of a step it skipped
- Re-explain the plan instead of executing the next step
- Drift into a tangent if a tool returns unexpected output

### How the existing codebase solves this

The **shipment workflow** (Prompt_sales.md rule 8) works reliably because each tool response contains an explicit **next action directive**:

```json
{
  "status": "needs_additional_step",
  "next_tool": "logistics_pick_tariff_for_shipment",
  "next_arguments": { "shipment_id": "SH-001", ... }
}
```

The agent doesn't have to remember a plan — the server tells it what to do next.

### Applying this to data import

Every tool in the import pipeline returns a `next_step` field that tells the agent exactly what to call next. The agent never has to recall "where it is" in a workflow — the response **is** the instruction.

This is the single most important design decision. Without it, the flow will break on step 3 or 4.

### Dedicated import agent

Data import uses its own agent with a purpose-built prompt. This agent knows nothing about sales, production, or logistics — it only handles imports. This eliminates an entire class of drift: the agent cannot wander into "let me also create a quote for these customers" territory because it has no tools for that.

The agent's tool set is limited to the `data_import_*` tools plus read-only catalog/CRM lookups (needed for entity resolution). No mutating business tools.

---

## Sample File

```csv
Kd-Nr;Firma;Ansprechpartner;E-Mail;Straße;PLZ;Ort;Land;Telefon;Zahlungsziel
101;DuckFan Paris SARL;Jean Dupont;jean@duckfan-paris.example;12 Rue du Canard;75001;Paris;france;+33 1 23 45 67 89;30 Tage
102;QuackShop London;;orders@quackshop.co.uk;42 Mallard Lane;SW1A 1AA;London;GB;+44 20 1234 5678;
103;Enten-Welt GmbH;Hans Müller;hans@entenwelt.example;Entenstraße 7;10115;Berlin;DE;+49 30 9876543;60 Tage
104;DuckFan Paris SARL;J. Dupont;j.dupont@duckfan-paris.example;12 Rue du Canard;75001;Paris;FR;;45 jours
```

Saved as `docs/data/DEMO_A/Kundenstammdatenübernahme_Altdatenbank.csv` — "customer master data takeover from legacy database". The kind of filename that makes a non-German speaker stare blankly and reach for the import wizard.

---

## Step-by-Step Flow

### Step 0 — User Message

The user pastes the file path in chat:

> Please import this customer list: file:///Users/demo/Downloads/Kundenstammdatenübernahme_Altdatenbank.csv

Nothing else. No hint about entity type, no column descriptions.

---

### Step 1 — `data_import_upload`

**Agent calls:**
```
data_import_upload(
    source="file:///Users/demo/Downloads/Kundenstammdatenübernahme_Altdatenbank.csv",
    hint=null
)
```

**Service does:**
1. Read file from local path
2. Detect format: CSV, delimiter `;`, encoding UTF-8
3. Parse into staging rows (raw string values)
4. Store in `import_jobs` + `import_rows` tables
5. Call the LLM with column names + first 3 rows → detect entity type = `customer`
6. Call the LLM with column names + sample values + customer schema → generate mapping plan

**Returns:**
```json
{
  "job_id": "IMP-001",
  "status": "mapped",
  "source_filename": "Kundenstammdatenübernahme_Altdatenbank.csv",
  "detected_format": "csv (semicolon-separated, UTF-8)",
  "detected_entity": "customer",
  "row_count": 4,
  "columns_detected": ["Kd-Nr","Firma","Ansprechpartner","E-Mail","Straße","PLZ","Ort","Land","Telefon","Zahlungsziel"],
  "mapping": [
    {"source": "Kd-Nr",           "target": "external_ref", "transform": "none",              "confidence": 0.72},
    {"source": "Firma",           "target": "company",      "transform": "none",              "confidence": 0.95},
    {"source": "Ansprechpartner", "target": "name",         "transform": "none",              "confidence": 0.91},
    {"source": "E-Mail",          "target": "email",        "transform": "lowercase",         "confidence": 0.98},
    {"source": "Straße",          "target": "address_line1","transform": "none",              "confidence": 0.94},
    {"source": "PLZ",             "target": "postal_code",  "transform": "zero-pad to 5",     "confidence": 0.96},
    {"source": "Ort",             "target": "city",         "transform": "none",              "confidence": 0.97},
    {"source": "Land",            "target": "country",      "transform": "ISO 3166-1 alpha-2","confidence": 0.88},
    {"source": "Telefon",         "target": "phone",        "transform": "E.164 normalise",   "confidence": 0.85},
    {"source": "Zahlungsziel",    "target": "payment_terms","transform": "parse int from text","confidence": 0.79}
  ],
  "message": "Uploaded 4 rows from Kundenstammdatenübernahme_Altdatenbank.csv. Detected as **customer** data with 10 columns mapped. Review the mapping and confirm, or ask me to change any column assignment.",
  "next_step": {
    "description": "Review the mapping above. Say 'looks good' to proceed, or tell me which columns to change.",
    "awaits": "user_confirmation",
    "on_confirm": {
      "tool": "data_import_validate",
      "arguments": { "job_id": "IMP-001" }
    }
  }
}
```

**MCP app:** `data-import-mapping` renders inline — a table showing each source column → target field with confidence badges.

**Agent says to user:**
> I've uploaded 4 rows from `Kundenstammdatenübernahme_Altdatenbank.csv` and detected them as **customer** records.
> Here's the mapping I've inferred: _(MCP app renders the mapping table)_
> Does this look right, or should I adjust any columns?

---

### Step 2 — User Confirms Mapping

> Looks good.

---

### Step 3 — `data_import_validate`

**Agent calls** (because `next_step.on_confirm` told it to):
```
data_import_validate(job_id="IMP-001")
```

**Service does:**
1. Apply transforms to all rows (country normalisation, phone formatting, payment terms parsing, etc.)
2. Run schema validation (required fields, types)
3. Run entity resolution against existing `customers` table (fuzzy match on name + email + company + address)
4. Flag issues

**Returns:**
```json
{
  "job_id": "IMP-001",
  "status": "validated",
  "summary": {
    "ready": 2,
    "needs_review": 2,
    "rejected": 0
  },
  "issues": [
    {
      "row": 2,
      "severity": "warning",
      "field": "name",
      "message": "Contact name is empty. Company name 'QuackShop London' will be used as fallback.",
      "auto_fixed": true
    },
    {
      "rows": [1, 4],
      "severity": "warning",
      "type": "possible_duplicate",
      "message": "Rows 1 and 4 may be the same customer: same company ('DuckFan Paris SARL'), same address, similar names ('Jean Dupont' vs 'J. Dupont'), different emails.",
      "suggestion": "merge",
      "merge_strategy": "Keep row 1 as primary. Add row 4's email (j.dupont@duckfan-paris.example) as alternate. Use row 4's payment_terms (45) if preferred."
    },
    {
      "row": 1,
      "severity": "info",
      "field": "country",
      "message": "'france' normalised to 'FR'",
      "auto_fixed": true
    },
    {
      "row": 4,
      "severity": "info",
      "field": "payment_terms",
      "message": "'45 jours' parsed as 45 days",
      "auto_fixed": true
    }
  ],
  "message": "Validation complete: **2 ready**, **2 need review** (possible duplicate), 0 rejected.\n\nRows 1 and 4 look like the same customer (DuckFan Paris SARL) — same company and address, names are 'Jean Dupont' vs 'J. Dupont'. Should I merge them into one customer, or keep both?",
  "next_step": {
    "description": "Resolve the duplicate: say 'merge' or 'keep both'. Then I'll show the final preview.",
    "awaits": "user_decision",
    "options": ["merge rows 1 and 4", "keep both"],
    "on_resolve": {
      "tool": "data_import_fix_issue",
      "template_arguments": { "job_id": "IMP-001", "issue_type": "possible_duplicate", "rows": [1, 4], "action": "{user_choice}" }
    },
    "after_resolve": {
      "tool": "data_import_preview",
      "arguments": { "job_id": "IMP-001" }
    }
  }
}
```

**MCP app:** `data-import-issues` renders — showing the 4 rows, status badges, and the duplicate highlight.

**Agent says to user:**
> Validation complete: 2 rows are ready, 2 need review.
> _(MCP app renders the issues view)_
>
> Rows 1 and 4 look like the same customer — "DuckFan Paris SARL", same address, names are "Jean Dupont" vs "J. Dupont" but different emails. Should I merge them into one customer or keep both?

---

### Step 4 — User Decides

> Merge them. Use the longer name and keep both emails.

---

### Step 5 — `data_import_fix_issue` + `data_import_preview`

**Agent calls** (following `next_step.on_resolve`):
```
data_import_fix_issue(
    job_id="IMP-001",
    issue_type="possible_duplicate",
    rows=[1, 4],
    action="merge",
    merge_preferences="Use 'Jean Dupont' as name, keep both emails"
)
```

**Service does:**
1. Merge rows 1+4 into a single staging row
2. Use name from row 1 ("Jean Dupont"), email from row 1, add row 4 email to notes
3. Use payment_terms from row 4 (45) since it's the more specific value
4. Mark row 4 as `merged_into_row_1`
5. Re-validate: all rows now `ready`

**Returns:**
```json
{
  "job_id": "IMP-001",
  "fixed": true,
  "message": "Rows 1 and 4 merged. Using 'Jean Dupont', email jean@duckfan-paris.example, payment terms 45 days. Second email noted.",
  "next_step": {
    "tool": "data_import_preview",
    "arguments": { "job_id": "IMP-001" }
  }
}
```

**Agent immediately calls** `data_import_preview` (no user interaction needed — `next_step` has no `awaits` field):

```
data_import_preview(job_id="IMP-001")
```

**Service does:**
1. Build final preview of records to create
2. Cross-check against existing customers one more time

**Returns:**
```json
{
  "job_id": "IMP-001",
  "status": "ready_to_execute",
  "preview": {
    "creates": [
      {
        "entity": "customer",
        "name": "Jean Dupont",
        "company": "DuckFan Paris SARL",
        "email": "jean@duckfan-paris.example",
        "city": "Paris",
        "country": "FR",
        "payment_terms": 45,
        "notes": "Alt. email: j.dupont@duckfan-paris.example"
      },
      {
        "entity": "customer",
        "name": "QuackShop London",
        "company": "QuackShop London",
        "email": "orders@quackshop.co.uk",
        "city": "London",
        "country": "GB",
        "payment_terms": 30
      },
      {
        "entity": "customer",
        "name": "Hans Müller",
        "company": "Enten-Welt GmbH",
        "email": "hans@entenwelt.example",
        "city": "Berlin",
        "country": "DE",
        "payment_terms": 60
      }
    ],
    "updates": [],
    "skipped": 0
  },
  "message": "Ready to import **3 new customers** (rows 1+4 merged). No existing customers will be updated.\n\nSay 'go' to create them.",
  "next_step": {
    "description": "Say 'go' to execute the import, or 'cancel' to discard.",
    "awaits": "user_confirmation",
    "on_confirm": {
      "tool": "data_import_execute",
      "arguments": { "job_id": "IMP-001" }
    }
  }
}
```

**MCP app:** `data-import-preview` renders — showing the 3 customers that will be created with all their fields.

**Agent says:**
> Here's what I'll create:
> _(MCP app renders the preview)_
>
> **3 new customers**: DuckFan Paris (merged), QuackShop London, and Enten-Welt GmbH. Ready to go?

---

### Step 6 — User Confirms

> Go.

---

### Step 7 — `data_import_execute`

**Agent calls:**
```
data_import_execute(job_id="IMP-001")
```

**Service does:**
1. For each ready row, call `customer_service.create_customer(...)` (the same service the `crm_create_customer` MCP tool uses)
2. Record the created customer IDs in `import_rows.created_entity_id`
3. Log to `activity_log`

**Returns:**
```json
{
  "job_id": "IMP-001",
  "status": "executed",
  "created": [
    { "source_row": 1, "entity": "customer", "customer_id": "CUST-045", "name": "Jean Dupont" },
    { "source_row": 2, "entity": "customer", "customer_id": "CUST-046", "name": "QuackShop London" },
    { "source_row": 3, "entity": "customer", "customer_id": "CUST-047", "name": "Hans Müller" }
  ],
  "message": "Import complete. Created **3 customers**: CUST-045 (DuckFan Paris), CUST-046 (QuackShop London), CUST-047 (Enten-Welt GmbH).",
  "next_step": null
}
```

**MCP app:** `data-import-result` renders — showing the 3 created customers with their IDs and a link to each.

**Agent says:**
> Done! Created 3 customers:
> _(MCP app renders the result summary)_
>
> - **CUST-045** — Jean Dupont (DuckFan Paris SARL), Paris
> - **CUST-046** — QuackShop London, London
> - **CUST-047** — Hans Müller (Enten-Welt GmbH), Berlin

---

## Tool Call Sequence Summary

```
User message
    │
    ▼
┌─────────────────────┐
│  data_import_upload  │  ← parses file, detects entity, generates mapping
└────────┬────────────┘
         │ returns mapping + next_step (awaits user)
         ▼
    User: "looks good"
         │
         ▼
┌──────────────────────────┐
│  data_import_validate    │  ← transforms, validates, entity resolution
└────────┬─────────────────┘
         │ returns issues + next_step (awaits user for duplicate)
         ▼
    User: "merge them"
         │
         ▼
┌──────────────────────────┐
│  data_import_fix_issue   │  ← applies merge
└────────┬─────────────────┘
         │ returns next_step (auto: preview)
         ▼
┌──────────────────────────┐
│  data_import_preview     │  ← shows final diff (awaits user)
└────────┬─────────────────┘
         │
         ▼
    User: "go"
         │
         ▼
┌──────────────────────────┐
│  data_import_execute     │  ← creates customers via service layer
└──────────────────────────┘
```

**Total tool calls: 5** (upload, validate, fix, preview, execute)
**User interactions: 3** (confirm mapping, resolve duplicate, confirm execution)

---

## The `next_step` Contract

Every tool response includes a `next_step` object with this structure:

```json
{
  "next_step": {
    "tool": "data_import_validate",     // what to call next
    "arguments": { "job_id": "IMP-001" }, // with these arguments
    "awaits": "user_confirmation",       // null = call immediately; string = wait for user
    "description": "...",                // human-readable instruction for the agent
    "options": ["merge", "keep both"],   // optional: suggested user responses
    "on_confirm": { ... },              // optional: tool+args when user says yes
    "on_resolve": { ... },             // optional: tool+args template for user decision
    "after_resolve": { ... }           // optional: what to call after on_resolve finishes
  }
}
```

Rules:
- If `next_step` is `null` → workflow is done, respond to user
- If `next_step.awaits` is null → call `next_step.tool` immediately (no user interaction)
- If `next_step.awaits` is set → present info to user, wait for their answer, then call the indicated tool
- The agent should NEVER decide on its own what tool to call next — always follow `next_step`

This is the same pattern as the shipment workflow (rule 8 in `Prompt_sales.md`), extended to multi-step import.

---

## Prompt Addition

Add to the agent system prompt:

```
10) Data import workflow orchestration (mandatory):
   For any data import request, follow this exact pattern:
   - Call `data_import_upload` with the file source.
   - After EVERY tool response, check `next_step`:
     - If `next_step` is null → workflow complete, summarise to user.
     - If `next_step.awaits` is null → immediately call `next_step.tool` with `next_step.arguments`.
     - If `next_step.awaits` is set → present the message to user, wait for their response,
       then call the indicated tool with the appropriate arguments.
   - NEVER skip a step or decide independently which import tool to call.
   - ALWAYS relay the `message` field from each tool response.
```

---

## Collapsing Steps: What If We Go Further?

The flow above has 5 tool calls. An alternative is to **collapse upload + detect + map + validate into a single "mega" tool call** (`data_import_upload`). This has big advantages:

1. **Fewer tool calls = less drift.** Each LLM round-trip is a chance for the agent to lose the thread. Doing all the deterministic work server-side in one call removes 2–3 round-trips.
2. **The first user interaction is the interesting one.** Nobody wants to confirm "yes, this is a CSV" and "yes, those are customers" — they want to see the mapping and fix the duplicate.
3. **Mirrors QC.** `qc_submit_image` does label extraction + image storage + AI inspection in a single call. The user sees the final result. Same should apply here.

The design above already collapses detect + map into `data_import_upload`. We could go further and also fold validate into it, reducing the happy path to:

```
data_import_upload  →  user confirms or fixes issues  →  data_import_execute
```

**3 tool calls. 2 user interactions. Minimal drift surface.**

The tradeoff: the first tool call takes longer (multiple LLM calls server-side). But for a demo, a 5-second loading spinner that produces "here's your mapping AND your issues AND your preview" in one shot is more impressive than 5 fast calls with user confirmations in between.

### Recommendation

Start with the 5-step flow (easier to debug, each step is independently testable), then collapse once it works. The `next_step` contract means the agent code doesn't change — only the server decides how many steps to expose.
