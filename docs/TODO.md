# TODO

Things that needs to be done -- but are not specific issues (ISSUES.md)


## Factory Observability — Activity Log, Daily Simulation, Dashboard  ✅

**Completed.** All five phases shipped:

1. **Phase 1 — Daily Simulation Loop:** S01 rewritten from weekly batches to a
   61-day daily loop with intra-day timestamps (08:00 → 18:00).
2. **Phase 2 — `activity_log` table & service:** Schema, `services/activity.py`,
   injected into scenarios (`helpers.py`, `s01_steady_state.py`), side-effects
   (`simulation.py`), and MCP tool decorator (`_common.py`). ~4 000 log rows
   per run.
3. **Phase 3 — API endpoints:** `api_routes/activity_routes.py` (paginated log
   + daily summary) and `api_routes/dashboard_routes.py` (KPIs, status
   distributions, daily volumes, recent activity).
4. **Phase 4 — Frontend:** `ActivityLogPage` (filterable, paginated),
   `DashboardPage` (KPI cards, status bars, SVG volume chart, activity feed),
   home-page KPI banner, "Monitoring" nav group.
5. **Phase 5 — MCP tool:** `mcp_tools/activity_tools.py` with
   `activity_get_log` for agent queries.

    timestamp   TEXT NOT NULL,           -- sim time (ISO)
    actor       TEXT NOT NULL,           -- 'scenario', 'system', 'mcp:sales', …
    category    TEXT NOT NULL,           -- 'sales', 'production', 'logistics', 'purchasing', 'billing'
    action      TEXT NOT NULL,           -- 'sales_order.created', 'production_order.completed', …
    entity_type TEXT,                    -- 'sales_order', 'production_order', 'shipment', …
    entity_id   TEXT,                    -- 'SO-1042', 'MO-0012', …
    details     TEXT                     -- JSON blob, optional context
);
CREATE INDEX IF NOT EXISTS idx_actlog_ts       ON activity_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_actlog_entity   ON activity_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_actlog_action   ON activity_log(action);
CREATE INDEX IF NOT EXISTS idx_actlog_category ON activity_log(category);
```

- [ ] Add `"ACT"` prefix seed to `db.generate_id()`.

#### 2b. Service — `services/activity.py`

- [ ] `log_activity(actor, category, action, entity_type=None, entity_id=None, details=None, timestamp=None)`
  — inserts one row; uses sim clock if timestamp is None.
- [ ] `log_batch(entries: list[dict])` — bulk insert for scenario efficiency.
- [ ] `get_log(limit=50, offset=0, category=None, action=None, entity_type=None, entity_id=None, since=None, until=None)`
  — paginated, filterable read.
- [ ] `get_daily_summary(since=None, until=None)` — `GROUP BY date(timestamp), category, action` for chart data.
- [ ] Register in `services/__init__.py`.

#### 2c. Inject into Scenarios

- [ ] `scenarios/helpers.py` — add `log_activity()` calls in:
  - `create_sales_order_only()` → `sales_order.created` + `sales_order.confirmed`
  - `create_quote_only()` → `quote.created`, `quote.sent`
  - `run_full_sales_cycle()` → all 10 steps
  - `trigger_production_for_orders()` → `production_order.created`, `.started`
  - `restock_materials()` → `purchase_order.created`
  - `send_email()` → `email.sent`
- [ ] `s01_steady_state.py` private helpers:
  - `_ship_ready_orders()` → `shipment.created`, `shipment.dispatched`
  - `_invoice_shipped_orders()` → `invoice.issued`, `payment.recorded`, `sales_order.completed`
  - `_receive_due_pos()` → `purchase_order.received`
  - `_start_ready_mos()` → `production_order.started`

#### 2d. Inject into Side-Effects (`services/simulation.py`)

- [ ] `advance_time()` side-effects should log (actor=`'system'`):
  - `production_order.completed` (per MO completed)
  - `shipment.delivered` (per shipment delivered)
  - `quote.expired` (per quote expired)
  - `production_order.promoted` (waiting→ready, per MO)
  - `invoice.overdue` (per invoice marked overdue)

#### 2e. Inject into MCP Tool Calls

- [ ] Extend `log_tool()` decorator in `mcp_tools/_common.py` to also write
  `activity_log` entries for mutating tools. Use a mapping dict:

```python
TOOL_ACTION_MAP = {
    "sales_confirm_order":      ("sales",      "sales_order.confirmed"),
    "sales_price_order":        ("sales",      "sales_order.priced"),
    "production_create_order":  ("production", "production_order.created"),
    "production_start_order":   ("production", "production_order.started"),
    "logistics_create_shipment":("logistics",  "shipment.created"),
    "invoice_create":           ("billing",    "invoice.created"),
    "invoice_issue":            ("billing",    "invoice.issued"),
    "invoice_record_payment":   ("billing",    "payment.recorded"),
    "quote_send":               ("sales",      "quote.sent"),
    "quote_accept":             ("sales",      "quote.accepted"),
    "quote_reject":             ("sales",      "quote.rejected"),
    # … extend as needed
}
```

  The decorator extracts `entity_type` and `entity_id` from the tool's result
  dict (convention: `*_id` keys). Actor = `'mcp:{tag}'` from tool meta tags.

---

### Phase 3 — API Endpoints

- [ ] Create `api_routes/activity_routes.py`:

  | Method | Path | Description |
  |--------|------|-------------|
  | GET | `/api/activity-log` | Paginated, filterable log entries |
  | GET | `/api/activity-log/summary` | Daily counts by category+action (for charts) |

  Query params: `limit`, `offset`, `category`, `action`, `entity_type`,
  `entity_id`, `since`, `until`.

- [ ] Create `api_routes/dashboard_routes.py`:

  | Method | Path | Description |
  |--------|------|-------------|
  | GET | `/api/dashboard` | Aggregated dashboard payload |

  Returns:
  - `status_distributions` — counts per status for SO, MO, Quote, Invoice,
    Shipment (5 queries)
  - `kpis` — open orders, in-progress MOs, pending shipments, overdue
    invoices, total revenue
  - `recent_activity` — last 20 activity_log entries
  - `daily_volumes` — last 30 sim-days of orders created / shipped / invoiced
    (from `activity_log` summary)

- [ ] Register both in `api_routes/__init__.py`.

---

### Phase 4 — Frontend: Dashboard + Activity Feed

#### 4a. Types & API Client

- [ ] Add to `ui/src/types.ts`:

```ts
export type ActivityLogEntry = {
    id: string
    timestamp: string
    actor: string
    category: string
    action: string
    entity_type: string | null
    entity_id: string | null
    details: Record<string, unknown> | null
}

export type DashboardData = {
    status_distributions: Record<string, { status: string; count: number }[]>
    kpis: {
        open_orders: number
        in_progress_mos: number
        pending_shipments: number
        overdue_invoices: number
        total_revenue: number
    }
    recent_activity: ActivityLogEntry[]
    daily_volumes: { date: string; created: number; shipped: number; invoiced: number }[]
}
```

- [ ] Add to `ui/src/api.ts`:
  - `activityLog(params?)` → `GET /api/activity-log`
  - `activitySummary(params?)` → `GET /api/activity-log/summary`
  - `dashboard()` → `GET /api/dashboard`

#### 4b. Home Page — Activity Widget + KPI Cards

- [ ] In `ui/src/App.tsx` (the `view.page === 'home'` branch), add above or
  below the existing card grid:
  - **KPI row**: 4–5 small cards (open SOs, in-progress MOs, pending
    shipments, overdue invoices, revenue) — data from `/api/dashboard`.
  - **"Recent Activity" card**: compact list of the last 10 entries, each
    showing a colored badge for category, the action in plain English, the
    entity link, and relative time. "View all →" links to the Activity page.

#### 4c. Activity Log Page — `ui/src/pages/ActivityLogPage.tsx`

- [ ] Filterable, paginated table of activity_log entries:
  - Columns: Time, Category (badge), Action, Entity (clickable link), Actor,
    Details
  - Filter bar: category dropdown, action search, date range
  - Clicking entity_id navigates to the relevant detail page via `setHash()`
  - "Load more" pagination at the bottom
- [ ] Add `'activity'` to `ViewPage` type in `App.tsx`
- [ ] Add nav entry (in a "Monitoring" group or top-level)
- [ ] Add route conditional

#### 4d. Dashboard Page — `ui/src/pages/DashboardPage.tsx`

- [ ] **Status bars**: For each entity type (SO, MO, Quote, Invoice, Shipment),
  a horizontal segmented bar showing count per status, colored by status.
  Pure CSS/Tailwind — no charting library needed.
- [ ] **Daily volume trend**: Either a server-rendered PNG chart via
  `/api/charts/` (existing chart service supports `line` and `stacked_area`),
  or inline SVG sparklines.
- [ ] **KPI cards**: Same as home page but larger, with trend indicators.
- [ ] Add `'dashboard'` to `ViewPage` type in `App.tsx`
- [ ] Add nav entry + route conditional

---

### Phase 5 — Optional: MCP Activity Tool

- [ ] Create `mcp_tools/activity_tools.py` with a `activity_get_log` tool so
  agents can query: "what happened yesterday in production?" Returns filtered
  activity_log entries.
- [ ] Register in `mcp_tools/__init__.py`.

---

### Implementation Order

```
Phase 1 → Phase 2a–2d → run scenarios & verify logs → Phase 3 → Phase 2e →
Phase 4a–4b → Phase 4c → Phase 4d → Phase 5
```

Phase 1 (daily loop) should come first because it produces realistic daily
timestamps that make the activity log and dashboard meaningful. There's no
point logging events that all happened at the same time.
