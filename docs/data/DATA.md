# AI-Powered Data Import & Export

## Problem Statement

Data import is the unglamorous reality of every ERP deployment. Customers show up with:

- A CSV exported from their old system where columns are named in German
- An Excel file with merged cells, colour-coded rows, and three tabs that contradict each other
- A PDF price list from a supplier — scanned, slightly rotated, in Comic Sans
- A photo of a whiteboard with next week's orders scribbled on it
- An email body with a table pasted from Word that lost all its formatting
- A JSON dump from an API that nests addresses four levels deep

Traditional import wizards demand the user hand-map every column, fix every date format, and reconcile every name. It's the #1 source of implementation pain.

**The pitch**: let the AI agent handle the mess. Drop your file. Describe what it is. Walk away.

---

## Design Principles

1. **Any format, any quality.** The agent must never say "unsupported format". If a human can read it, the agent should be able to import it.
2. **Confidence, not magic.** Every mapped field gets a confidence score. High-confidence rows go through silently; low-confidence rows surface for review. The human stays in control.
3. **Entity resolution, not blind insert.** "J. Doe, Paris" should match the existing John Doe customer, not create a duplicate. The AI resolves references against live ERP data.
4. **Explain every decision.** The agent must justify each mapping, merge, and correction — auditable and reversible.
5. **Fit the MCP agent model.** Import starts with a single MCP tool call. The interactive MCP app handles review, fixes, and execution — the user works directly in the app, not through back-and-forth chat. The agent is a thin launcher.

---

## Feature Set

### F1 — Universal File Ingest

**What:** Accept any reasonably structured file and extract tabular or semi-structured data.

Supported inputs:
| Source | Method |
|--------|--------|
| CSV / TSV | Parse with delimiter detection, encoding sniffing |
| Excel (.xlsx) | Read sheets, handle merged cells, detect header rows |
| JSON / JSONL | Flatten nested structures |
| PDF (text-based) | Extract tables via layout analysis |
| PDF (scanned) / Image | OCR → table extraction via vision model |
| Email body (pasted) | Regex + LLM structured extraction |
| Clipboard (HTML table) | Parse HTML table tags |

**File delivery:** Currently via `file://` URL pasted in chat (the agent reads the file from the local path). When the chat client supports document attachments, the tool will accept inline base64 content instead — no design change needed.

The ingest step produces a normalised **staging table**: a list of flat dicts with raw string values and a `_source_row` reference back to the original.

**MCP tool:** `data_import_upload`
- Input: file content (base64 or text), file name, optional hint ("this is a customer list from our old CRM")
- Output: full staging state rendered in the interactive import panel (mapping, rows, issues, batch questions)

---

### F2 — AI Schema Mapping

**What:** Columns are mapped to ERP entity fields using the LLM, not a rule engine. This happens automatically as part of `data_import_upload` — no separate tool call.

The model receives:
1. The staging table column names + sample values (first 10 rows)
2. The target ERP schema (e.g. customers table columns with descriptions)
3. An optional user hint ("the `Kd-Nr` column is the customer reference")

It returns a **mapping plan**: for each staging column, the target field, a transformation (if needed), and a confidence score.

Example:

```
Staging Column     → Target Field          Transform           Confidence
─────────────────────────────────────────────────────────────────────────
Kd-Nr              → customer.id           prefix "CUST-"      0.72
Firma              → customer.company       none                0.95
Ansprechpartner    → customer.name          none                0.91
E-Mail             → customer.email         lowercase           0.98
Straße             → customer.address_line1  none               0.94
PLZ                → customer.postal_code   zero-pad to 5       0.96
Ort                → customer.city          none                0.97
Land               → customer.country       ISO 3166-1 alpha-2  0.88
Telefon            → customer.phone         normalize +49       0.85
Zahlungsziel       → customer.payment_terms parse "30 Tage"→30  0.79
```

The user sees the mapping in the interactive import panel and can request adjustments via the Fix field.

---

### F3 — Data Quality Analysis

**What:** Before inserting anything, every row is scanned and problems are flagged. This runs automatically as part of `data_import_upload`.

Categories of issues:
| Severity | Examples |
|----------|----------|
| **Error** | Missing required field, value violates constraint, unparseable date |
| **Warning** | Possible duplicate of existing record, value outside normal range |
| **Info** | Field was auto-corrected (e.g. "france" → "FR"), default applied |

The analysis is powered by a combination of:
- **Schema validation** — type checks, required fields, unique constraints
- **LLM judgement** — "Is `Bückingham Palace` a plausible address?" → yes (typo for Buckingham), auto-correct
- **ERP cross-reference** — check for duplicate customers, validate SKUs exist, verify supplier IDs

Each row gets an overall status: `ready`, `needs_review`, or `rejected`. Issues are displayed in the interactive import panel grouped by severity, with auto-fixes shown as info-level annotations.

---

### F4 — Entity Resolution (Fuzzy Matching)

**What:** When imported data references existing ERP records, references are resolved intelligently instead of requiring exact ID matches. This runs automatically as part of `data_import_upload`.

Scenarios:
- **Customer dedup:** Incoming "J. Doe — Duck Fan Paris" matches existing customer `CUST-042` (John Doe, company "DuckFan Paris SARL") with 87% confidence
- **Item matching:** "Elvis rubber duck, large" resolves to SKU `ELVIS-DUCK-20CM` via semantic similarity
- **Supplier matching:** "PlasticCorp GmbH" matches `SUP-001` (PlasticCorp) despite the legal suffix

Resolution strategy:
1. **Exact match** on normalised key fields (email, SKU, tax ID) → confidence 1.0
2. **Fuzzy match** on name/company using trigram similarity → confidence 0.6–0.9
3. **Semantic match** via embedding similarity from the LLM → confidence 0.5–0.8
4. **No match** → flag as new record, propose creation

The agent presents matches with explanations: _"Matched to CUST-042 (John Doe) because email `john@duckfan-paris.example` is an exact match, and company name is 84% similar."_ Ambiguous matches are surfaced in the import panel as batch questions.

---

### F5 — Smart Transform & Enrichment

**What:** Values are transformed to fit the ERP schema, and gaps filled using context. This happens automatically during `data_import_upload` — the results are shown as before/after annotations in the import panel.

Transforms:
| Input | Output | How |
|-------|--------|-----|
| "30 Tage" | `30` | LLM parses German payment terms |
| "france" | `"FR"` | Country name → ISO code |
| "+49 (0) 30 123456" | `"+493012345"` | Phone normalisation |
| "12,50 €" | `12.50` | European decimal + currency extraction |
| "2025-31-01" | `"2025-01-31"` | Ambiguous date → infer DD-MM vs MM-DD from context |
| "Elvis duck x24" | SKU: `ELVIS-DUCK-20CM`, qty: `24` | Product + quantity extraction |
| (missing city) | `"Paris"` | Inferred from postal code `75001` |

The key insight: the LLM handles the **long tail** of format variations that no regex library will ever cover. Rule engines handle the common 80%; the LLM handles the weird 20% that makes import projects drag on for weeks.

---

### F6 — Conversational Conflict Resolution

**What:** When the system encounters ambiguity it cannot resolve alone, it asks the user — but smartly, batching related questions. This happens in the interactive import panel, not via agent chat.

Instead of:
> "Row 3: Is 'Large Elvis' the 20cm or 25cm variant?"
> "Row 7: Is 'Large Elvis' the 20cm or 25cm variant?"
> "Row 12: Is 'Large Elvis' the 20cm or 25cm variant?"

The import panel shows:
> "12 rows reference 'Large Elvis'. I think this is ELVIS-DUCK-20CM (the only Elvis duck in catalog). Should I map all 12 to that SKU?"

The user types a free-text instruction in the Fix field (e.g. "yes, map them all"). The backend LLM interprets the instruction, applies the fix, and the panel refreshes. One answer fixes dozens of rows.

---

### F7 — Import Execution with Preview

**What:** Once all issues are resolved, the import panel shows a final summary and the user clicks "Import" to execute.

The panel shows:
- Total records to create / update / skip
- All rows with their status badges and annotations
- Side effects: "This will create 3 new customers"

The user clicks "Import" in the panel. The backend creates records via the standard service layer (`crm_create_customer`, `quote_create`, etc.) so all normal business logic, validation, and activity logging apply. No backdoor inserts. The panel updates to show created entity IDs with links.

Rollback is available via `data_import_rollback` (deletes created records by stored IDs).

---

### F8 — Intelligent Export

**What:** Export ERP data in any format the recipient expects — not just our internal structure.

Export modes:
- **Template-based:** "Export all open orders as a CSV that looks like [this sample]" — the agent reverse-engineers the expected column names, order, and formatting from an example file
- **Natural language:** "Give me a list of Paris customers with their total order value this quarter" — the agent queries the data, formats it, and produces the file
- **EDI/Format-aware:** "Export in EDIFACT ORDERS format" or "Make it look like a SAP IDoc" — the AI generates the correct structure
- **Recipient-adaptive:** Remember how customer X expects their order confirmations and auto-apply that template next time

**MCP tools:**
- `data_export_create` — generate an export file (CSV, JSON, Excel, PDF)
- `data_export_from_template` — match the format of a provided sample file
- `data_export_list` — list recent exports for download

---

### F9 — Photo & Document Import

**What:** Point your phone camera at physical documents and import the data.

Supported document types:
| Document | Extracted Entity |
|----------|-----------------|
| Paper purchase order (handwritten or printed) | Sales order / quote |
| Supplier invoice (PDF or photo) | Purchase order match + payment record |
| Business card | New customer record |
| Whiteboard with production schedule | Production orders |
| Printed price list | Item price updates |
| Packing slip | Shipment receipt / stock movement |

This builds on the existing QC vision pipeline (MyForterro inference with image inputs). The agent:
1. Receives an image via `data_import_upload`
2. Sends it to the vision model with a tailored extraction prompt
3. Gets structured JSON back
4. Feeds it through the same F2–F7 pipeline

**Demo moment:** The presenter writes a fake purchase order on a sticky note, takes a photo, uploads it, and watches the agent create the customer, quote, and sales order in seconds.

---

## Database Changes

Two new staging tables (`import_jobs`, `import_rows`) isolated from operational data. See [DATA_DESIGN.md](DATA_DESIGN.md) § 1 for full schema.

---

## MCP Tool Summary

| Tool | Tag | Description |
|------|-----|-------------|
| `data_import_upload` | data_import | Upload file, parse, map, validate, resolve — returns interactive staging panel |
| `data_export_create` | shared | Export ERP data to file |
| `data_export_from_template` | shared | Export matching a sample file's format |
| `data_export_list` | shared | List recent exports |

The import flow uses only **one MCP tool** (`data_import_upload`). All subsequent interaction (fix issues, execute import) happens in the interactive MCP app via REST endpoints — the agent is not involved after the initial call. See [DATA_DESIGN.md](DATA_DESIGN.md) §5 for REST endpoint details.

---

## Demo Scenarios

### Demo A — "The German Spreadsheet"

The presenter drops a CSV with German column headers, inconsistent formatting, and a few deliberate errors:

```csv
Kd-Nr;Firma;Ansprechpartner;E-Mail;Straße;PLZ;Ort;Land;Telefon;Zahlungsziel
101;DuckFan Paris SARL;Jean Dupont;jean@duckfan-paris.example;12 Rue du Canard;75001;Paris;france;+33 1 23 45 67 89;30 Tage
102;QuackShop London;;orders@quackshop.co.uk;42 Mallard Lane;SW1A 1AA;London;GB;+44 20 1234 5678;
103;Enten-Welt GmbH;Hans Müller;hans@entenwelt.example;Entenstraße 7;10115;Berlin;DE;+49 30 9876543;60 Tage
104;DuckFan Paris SARL;J. Dupont;j.dupont@duckfan-paris.example;12 Rue du Canard;75001;Paris;FR;;45 jours
```

The agent:
1. Calls `data_import_upload` → parses file, detects entity type, maps columns, validates, resolves entities — all server-side in one call
2. The interactive import panel renders inline showing: mapping table, all 4 rows with annotations, auto-fixes ("france" → "FR", "30 Tage" → 30, "45 jours" → 45), and a batch question about the duplicate
3. Presenter types "merge them, use the longer name" in the Fix field → panel refreshes with 3 clean rows
4. Presenter clicks "Import" → 3 customers created

### Demo B — "The Sticky Note Order"

The presenter photographs a handwritten note:
> _"24× Elvis ducks, 12× Pirate, deliver to Dean Forbes, Buckingham Palace, London. Need by Feb 15."_

The agent:
1. OCR extracts the text
2. Resolves "Elvis ducks" → `ELVIS-DUCK-20CM`, "Pirate" → `PIRATE-DUCK-15CM`
3. Matches "Dean Forbes" to existing customer (or creates new)
4. Parses delivery address and date
5. Creates quote with 2 lines, applies pricing

### Demo C — "Export Like SAP"

A customer says: _"We need your order confirmations to look like this."_ They attach a sample CSV from their old supplier with columns like `VBELN`, `POSNR`, `MATNR`, `MENGE`, `NETWR`.

The agent:
1. Analyses the sample to understand the column semantics (SAP sales order fields)
2. Maps ERP fields to the expected output format
3. Generates the export with matching column names, number formatting, and structure
4. Remembers this template for future exports to this customer

### Demo D — "The Multi-Entity Disaster"

A new distributor sends a single Excel file with three tabs:
- **Customers** — their retail outlets (messy, with merged header rows)
- **Products** — their internal product codes mapped to "your duck names" (approximate)
- **Orders** — 50 orders referencing their own customer and product codes

The agent:
1. Processes tab by tab: customers first, then products (to build the reference mappings), then orders
2. Creates the customers, maps their product codes to our SKUs
3. Imports all 50 orders as quotes, correctly cross-referencing the newly created customers and resolved SKUs
4. Presents a summary: "Created 12 customers, mapped 8 products, generated 50 quotes totalling €14,320"

### Demo E — "The Supplier Price Update"

A supplier emails a PDF price list — poorly formatted, with some items having crossed-out old prices and new prices in bold.

The agent:
1. Vision model extracts the table from the PDF image
2. Maps supplier item names to ERP raw material SKUs
3. Shows a before/after comparison of cost prices
4. Asks: "Apply these price changes to 4 raw materials?"
5. Updates cost prices on confirmation

---

## MCP App — Interactive Import Panel

One interactive MCP app (`data-import.html`) handles the entire review, fix, and execute flow. It renders inline in the chat after `data_import_upload` returns — same pattern as `tariff-picker.html` and `qc-inspection.html`, but with a free-text input field for issuing fix instructions.

### What it shows

- **Mapping table:** source column → target field, confidence badges, transform descriptions
- **Data grid:** all rows with status badges (ready / needs review / auto-fixed / rejected)
- **Auto-fix log:** collapsible list of corrections applied automatically ("'france' → FR")
- **Batch question area:** the current grouped question (if any issues remain)
- **Fix field:** free-text input where the user types fix instructions (e.g. "merge them, use the longer name")
- **Import button:** enabled when all errors are resolved; clicks execute the import via REST endpoint

### How it works

The MCP app communicates directly with the backend via REST endpoints — no agent involvement. When the user types in the Fix field, the app sends the instruction to `POST /api/data-import/{job_id}/fix`. The backend LLM interprets the instruction, applies fixes, re-validates, and returns the updated staging state. The app re-renders. When the user clicks "Import", the app calls `POST /api/data-import/{job_id}/execute`.

After execution, the panel shows created entity IDs with links to each record in the ERP.

---

## Implementation Notes

The import follows an **Extract → Transform → Load** pattern:

- **Extract:** Agent calls `data_import_upload` (one MCP tool call). The backend parses the file, maps columns, validates, resolves entities — all server-side.
- **Transform:** The interactive MCP app renders. The user reviews data, fixes issues via free-text instructions (MCP app ↔ backend REST, no agent involved).
- **Load:** User clicks "Import" in the panel. Backend creates records via the service layer.

The agent is a thin launcher — it calls one tool, summarises the result, and the MCP app takes over. No multi-step agent orchestration, no workflow drift.

For the full technical design — service architecture, LLM prompts, REST endpoints, MCP app design, and dependencies — see [DATA_DESIGN.md](DATA_DESIGN.md).

---

## Why This Demo Is Compelling

Traditional ERP demos show pristine data flowing through pristine processes. In reality, the first six months of any implementation are spent fighting data migration. By showing:

1. **A messy real-world file** going in clean data coming out
2. **The AI explaining its reasoning** for every mapping and correction
3. **A photo of a handwritten note** turning into a priced quote in 10 seconds
4. **Zero manual column mapping** — the AI just figures it out

…you demonstrate that the AI isn't just a chatbot bolted onto an ERP. It solves one of the hardest, most expensive problems in enterprise software: **getting data in**.
