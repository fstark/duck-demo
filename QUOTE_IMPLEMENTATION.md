# Quote Entity Implementation Summary

Complete implementation of Quote entity with revision support, frozen pricing, and PDF generation.

## Overview

Quotes are formal price proposals sent to customers **before** creating sales orders. They freeze pricing at creation time, support revisions, and integrate with the existing sales workflow.

## Architecture

### Database Schema

**quotes table:**
- `id` (TEXT PRIMARY KEY) - Format: QUOTE-0001, QUOTE-0002...
- `customer_id` (TEXT) - Foreign key to customers
- `revision_number` (INTEGER) - 1, 2, 3... for R1, R2, R3
- `supersedes_quote_id` (TEXT) - Links to previous revision
- `status` (TEXT) - draft, sent, accepted, rejected, expired, superseded
- Frozen pricing: `subtotal`, `tax`, `total`
- Timestamps: `created_at`, `sent_at`, `valid_until`, `accepted_at`
- `sales_order_id` (TEXT) - Created when quote is accepted

**quote_lines table:**
- Links to quotes table
- **Frozen pricing:** `unit_price`, `line_total` stored at quote creation
- `sku`, `qty` for line items

### Services (services.py)

**QuoteService** - 8 methods:
1. `create_quote(customer_id, lines, valid_days)` - Creates draft with frozen pricing
2. `get_quote(quote_id)` - Returns full details with lines and revisions
3. `list_quotes(customer_id, status, limit, show_superseded)` - Filtered list
4. `send_quote(quote_id)` - Generates PDF, stores in documents table, status → sent
5. `accept_quote(quote_id)` - Creates sales order, status → accepted
6. `reject_quote(quote_id, reason)` - Status → rejected
7. `revise_quote(quote_id, lines, changes_summary, valid_days)` - Creates new revision (R2, R3...), old → superseded
8. `generate_quote_pdf(quote_id)` - ReportLab PDF with validity notice

**DocumentService** - Generic document storage:
- `store_document(entity_type, entity_id, document_type, content, filename)`
- `get_document(entity_type, entity_id, document_type)`

### MCP Tools (mcp_tools.py)

7 quote tools (tag: `sales`):
- `quote_create` 🔧 - mutating
- `quote_get` - direct read
- `quote_list` - direct read
- `quote_send` 🔧 - mutating
- `quote_accept` 🔧 - mutating (compound: also creates sales order)
- `quote_reject` 🔧 - mutating
- `quote_revise` 🔧 - mutating

### API Routes (api_routes.py)

- `GET /api/quotes` - List with filters (customer_id, status, show_superseded)
- `GET /api/quotes/{id}` - Quote detail with lines and revisions
- `GET /api/quotes/{id}/pdf` - PDF download (stored or on-demand)

### UI Components

**QuotesListPage.tsx:**
- Filterable list (status, show_superseded checkbox)
- Shows customer, revision, status, total, validity, timestamps
- Navigate to detail view

**QuoteDetailPage.tsx:**
- Quote information card with all fields
- Line items table with frozen pricing
- Pricing summary (subtotal, tax, total)
- Revision history table
- PDF download button
- Links to customer, sales order, items, superseded quotes

**Navigation:**
- Added "Quotes" to main navigation menu
- Hash routing: `#/quotes` and `#/quotes/{id}`
- Types and API methods in types.ts and api.ts

## Workflow

### Standard Flow
1. Sales rep creates quote → `quote_create` → returns created quote
2. Quote PDF generated and sent → `quote_send` → returns updated quote
3. Customer accepts → `quote_accept` → creates sales order and returns accepted quote
4. Sales order → Production → Invoice/Shipping

### Revision Flow
1. Customer requests changes
2. Sales rep revises quote → `quote_revise` → returns new revision
3. New revision created (QUOTE-0001-R2), old marked as superseded
4. Send new revision → `quote_send` → returns updated quote
5. Continue with standard flow

### Pricing Behavior
- Unit prices are **frozen** in quote_lines at quote creation time
- Subsequent catalog price changes do NOT affect existing quotes
- Revisions capture current prices at revision time
- Prevents disputes over pricing changes during negotiation

## Key Features

1. **Revision Support:** Base ID + revision number (QUOTE-0001-R1, QUOTE-0001-R2)
2. **Frozen Pricing:** unit_price and line_total stored in quote_lines
3. **PDF Generation:** ReportLab with validity notice, stored in documents table
4. **Direct Execution:** All mutation tools execute immediately and return the created/updated object
5. **Status Tracking:** draft → sent → accepted/rejected/expired/superseded
6. **Document Storage:** Generic documents table for all PDFs (quotes, invoices, etc.)
7. **UI Integration:** Full CRUD with navigation, filters, detail views

## Files Modified/Created

### Backend
- schema.sql - Added quotes and quote_lines tables
- migrate_quotes_table.py - Migration script (executed)
- services.py - QuoteService class (570+ lines)
- mcp_tools.py - 7 quote tools with executors
- api_routes.py - 3 quote API endpoints

### Frontend
- ui/src/types.ts - Quote and QuoteDetail types
- ui/src/api.ts - quotes() and quoteDetail() methods
- ui/src/pages/QuotesListPage.tsx - List view (125 lines)
- ui/src/pages/QuoteDetailPage.tsx - Detail view (251 lines)
- ui/src/App.tsx - Routes and navigation

### Documentation
- Prompt_sales.md - Quote workflow section
- AGENTS.md - Updated tool counts (54 tools, 45 for sales agent)
- QUOTE_IMPLEMENTATION.md - This file

## Testing Checklist

- [ ] Create quote with multiple line items
- [ ] Send quote (verify PDF generated and stored)
- [ ] Download PDF from UI
- [ ] Accept quote (verify sales order created)
- [ ] Reject quote with reason
- [ ] Revise quote (verify new revision created, old superseded)
- [ ] Filter quotes by status
- [ ] Show/hide superseded revisions
- [ ] Navigate between quote revisions
- [ ] Verify frozen pricing (change catalog price, check quote unchanged)
- [ ] Test quote expiration (advance simulation time past valid_until)

## Database Changes

```sql
-- quotes table (22 columns)
CREATE TABLE quotes (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    revision_number INTEGER DEFAULT 1,
    supersedes_quote_id TEXT,
    status TEXT DEFAULT 'draft',
    subtotal REAL NOT NULL,
    tax REAL DEFAULT 0,
    total REAL NOT NULL,
    valid_until TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    sent_at TEXT,
    accepted_at TEXT,
    sales_order_id TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (supersedes_quote_id) REFERENCES quotes(id),
    FOREIGN KEY (sales_order_id) REFERENCES sales_orders(id)
);

-- quote_lines table (6 columns)
CREATE TABLE quote_lines (
    quote_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    qty REAL NOT NULL,
    unit_price REAL NOT NULL,
    line_total REAL NOT NULL,
    PRIMARY KEY (quote_id, sku),
    FOREIGN KEY (quote_id) REFERENCES quotes(id),
    FOREIGN KEY (sku) REFERENCES items(sku)
);
```

## Next Steps

1. **Testing:** Verify all workflows with actual quote operations
2. **Integration:** Test sales agent with quote tools
3. **Email Integration:** Add quote links to customer emails
4. **Analytics:** Add quote metrics to dashboard (conversion rate, avg time to acceptance)
5. **Expiration Automation:** Create job to auto-expire quotes past valid_until date

## Implementation Notes

- **Direct Execution:** All quote mutation tools execute immediately and return the result
- **PDF Storage:** Stored in documents table as BLOB, entity_type='quote'
- **Revision Linking:** supersedes_quote_id creates chain, status='superseded' hides old versions
- **Sales Order Creation:** quote_accept() calls SalesService.create_order() internally
- **Pricing Service:** Uses existing PricingService for subtotal/tax/total calculations
- **Simulation Time:** Uses SimulationService.get_current_time() for timestamps
- **Hash Routing:** UI uses #/quotes/{id} pattern (not React Router)
