# Demo Flow — "The German Spreadsheet"

Customer import from a semicolon-separated CSV with German column headers, inconsistent formatting, and a near-duplicate row.

---

## The AI ETL Pattern

The import follows an **Extract → Transform → Load** pattern, where the AI handles the hard parts:

| Phase | Who does it | What happens |
|-------|-------------|-------------|
| **Extract** | Agent → single MCP tool call | Parse file, detect entity type, map columns, apply transforms, validate, resolve entities — all server-side |
| **Transform** | User ↔ interactive MCP app | Review mapping and issues, fix problems via free-text input, iterate until clean |
| **Load** | User clicks "Import" in MCP app | Execute via service layer, show results |

The agent is a **thin launcher**. It calls one tool, the MCP app takes over, the user interacts directly with the MCP app until done. The agent never re-enters the loop.

---

## Why This Architecture

### The agent reliability problem

Multi-step workflows are the #1 failure mode with LLM agents. After 4–5 tool calls the agent tends to:
- Summarise what it did and stop (forgetting there are remaining steps)
- Hallucinate the result of a step it skipped
- Re-explain the plan instead of executing the next step
- Drift into a tangent if a tool returns unexpected output

### The fix: remove the agent from the loop

Instead of the agent mediating every fix (user → agent → tool → agent → user), the MCP app talks directly to the backend. The agent is not involved in the Transform or Load phases at all.

This gives us:
- **1 agent tool call** (Extract) — near-zero drift surface
- **Direct MCP app ↔ backend loop** (Transform) — no LLM round-trips, instant feedback
- **One-click execution** (Load) — MCP app calls app-only MCP tool directly

### Dedicated import agent

Data import uses its own agent with a purpose-built prompt. This agent knows nothing about sales, production, or logistics — it only handles imports. The agent's tool set is limited to `data_import_upload` plus read-only catalog/CRM lookups. No mutating business tools. It cannot drift because it has almost nothing to drift into.

---

## Issue Resolution in the MCP App

### How decisions scale (the "30 issues" problem)

The validate step uses aggressive auto-resolution with three tiers:

**Tier 1 — Auto-fix (no user interaction).** The vast majority of issues are deterministic corrections:
- `"france"` → `"FR"` (country normalisation)
- `"30 Tage"` → `30` (payment terms parsing)
- Empty contact name → use company name as fallback
- Phone number reformatting

These are applied silently during Extract and shown as `info`-level annotations in the MCP app. The user sees them but doesn't have to approve each one.

**Tier 2 — Batch decisions (one answer fixes many rows).** The MCP app groups similar issues into a single question:
- "15 rows are missing phone numbers → leave blank (default) or reject those rows?"
- "8 rows reference 'Large Elvis' → matched all 8 to ELVIS-DUCK-20CM. OK?"
- "3 pairs of rows look like duplicates → merge all, or review individually?"

One free-text answer resolves the entire group.

**Tier 3 — Individual decisions (rare).** Only genuinely unique ambiguities:
- "Row 17 has 'Canard Géant' — is this GNOME-DUCK-30CM or a product we don't carry?"

For a realistic 200-row import, the expected interaction is ~2 fix rounds in the MCP app, not 30.

### How the "Fix" field works

The MCP app presents a batch question and a free-text input field. The user types a natural language instruction (e.g. "merge them, use the longer name"). The MCP app calls the backend via an app-only MCP tool:

```javascript
await app.callServerTool({
  name: "data_import_fix",
  arguments: {
    job_id: "IMP-001",
    instruction: "merge the duplicates, use the longer name, keep both emails"
  }
});
```

The backend LLM interprets the instruction against the actual row data, applies the fix, re-validates, and returns the updated staging state + next batch question (if any). The MCP app refreshes its display — no page reload, just a DOM update.

When the user is satisfied, they click **"Import"**. The MCP app calls:

```javascript
await app.callServerTool({
  name: "data_import_execute",
  arguments: { job_id: "IMP-001" }
});
```

The backend creates the records via the service layer and returns the result. The MCP app shows the execution summary.

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

### Step 1 — User Message (chat)

The user pastes the file path in chat:

> Please import this customer list: file:///Users/demo/Downloads/Kundenstammdatenübernahme_Altdatenbank.csv

Nothing else. No hint about entity type, no column descriptions.

### Step 2 — Extract (`data_import_upload`)

**Agent calls:**
```
data_import_upload(
    source="file:///Users/demo/Downloads/Kundenstammdatenübernahme_Altdatenbank.csv",
    hint=null
)
```

**Service does everything in one call:**
1. Read file from local path
2. Detect format: CSV, delimiter `;`, encoding UTF-8
3. Parse into staging rows (raw string values)
4. Store in `import_jobs` + `import_rows` tables
5. LLM call: detect entity type = `customer`
6. LLM call: generate column mapping plan
7. Apply transforms (country codes, phone normalisation, payment terms parsing)
8. Run schema validation (required fields, types)
9. Run entity resolution against existing `customers` table
10. Flag issues, group batch questions

**Returns:** structured content for the MCP app, containing the full staging state.

**MCP app `data-import.html` renders inline** showing:
- Mapping table (source → target, confidence badges, transforms)
- Data grid with all rows, annotated with status badges and issue flags
- Auto-fix log: "'france' → FR", "'45 jours' → 45 days", etc.
- Batch question: _"Rows 1 and 4 may be the same customer (DuckFan Paris SARL). Same company, same address, similar names. Merge or keep both?"_
- **Fix** text input field
- **Import** button (disabled until no errors remain)

**Agent says:**
> I've parsed your file and prepared it for import. Review the data in the panel — you can fix any issues there and import when ready.

The agent's job is done. Everything from here happens in the MCP app.

### Step 3 — Transform (MCP app ↔ backend loop)

**User types in the Fix field:**
> Merge the duplicates, use the longer name, keep both emails

**MCP app calls:**
```javascript
await app.callServerTool({
  name: "data_import_fix",
  arguments: {
    job_id: "IMP-001",
    instruction: "Merge the duplicates, use the longer name, keep both emails"
  }
});
```

**Backend does:**
1. Backend LLM interprets: merge rows 1+4, name="Jean Dupont", primary email from row 1, second email in notes, payment_terms=45
2. Merge rows in staging table
3. Re-validate remaining rows
4. Return updated state

**MCP app refreshes, now showing:**
- 3 rows (rows 1+4 merged, row 2 and 3 unchanged)
- All rows `ready` (green badges)
- No more batch questions
- **Import** button now enabled
- Summary: _"3 customers ready to import. No issues remaining."_

If there were more issues, the app would show the next batch question and the cycle repeats.

### Step 4 — Load (MCP app → backend)

**User clicks "Import".**

**MCP app calls:**
```javascript
await app.callServerTool({
  name: "data_import_execute",
  arguments: { job_id: "IMP-001" }
});
```

**Backend does:**
1. For each ready row, call `customer_service.create_customer(...)` (same service layer as `crm_create_customer`)
2. Record created IDs in `import_rows.created_entity_id`
3. Log to `activity_log`

**MCP app updates to show execution result:**
- Created: CUST-045 (Jean Dupont, DuckFan Paris), CUST-046 (QuackShop London), CUST-047 (Hans Müller, Enten-Welt)
- Links to each customer in the ERP UI

---

## Tool Call Sequence Summary

```
User message
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  data_import_upload                                  │
│  (parse, map, transform, validate, resolve — all    │
│   server-side in one call)                           │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │    MCP App renders    │
         │  data-import.html     │
         └───────┬───────────────┘
                 │
        ┌────────┴─────────┐
        ▼                  ▼
  ┌───────────┐     ┌────────────┐
  │ Fix field │     │  Import    │
  │ (free     │     │  button    │
  │  text)    │     │            │
  └─────┬─────┘     └──────┬─────┘
        │                   │
        ▼                   ▼
  callServerTool       callServerTool
  (data_import_fix)    (data_import_execute)
  backend LLM           service layer
   interprets,          creates records
   re-validates,
   returns updated
   state
        │
        ▼
  MCP App refreshes
  (loop until clean)
```

**Agent tool calls: 1** (`data_import_upload`)
**MCP app ↔ backend tool calls: 1–3** (fix iterations via `data_import_fix`, no agent involved)
**User clicks: 1** ("Import")

---

## Agent Prompt

The import agent prompt is trivially simple because the agent barely does anything:

```
You are a data import assistant for Duck Inc's ERP system.

When the user wants to import data from a file, call `data_import_upload`
with the file source. The interactive import panel will take over from there.

You handle data import only. If the user asks about orders, production,
or anything else, say it's outside your scope.
```

That's it. No workflow orchestration rules, no `next_step` contract, no multi-step sequencing. The agent is a launcher.
