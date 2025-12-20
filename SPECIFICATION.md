The python virtual environment is in venv

The implementation should be python (probably django, but this is not mandatory).

The database is sqllite.



Below is a demo flow that’s *small*, but feels real: one new order that needs negotiation, and one existing customer asking for status.

---

## Minimal demo dataset (so the flow can “compute”)

### Items

* **ELVIS-DUCK-20CM** (finished good)
* **MARILYN-DUCK-20CM** (finished good)
* **PVC-PELLETS**, **BLACK-DYE**, **YELLOW-DYE**, **BOX-SMALL** (materials)

### Stock (finished goods)

* **ELVIS-DUCK-20CM**: 12 units in FinishedGoods/Bin-12
* **MARILYN-DUCK-20CM**: 12 units in FinishedGoods/Bin-14
  (So: we can’t ship 24 Elvis, but we can ship 12 Elvis + 12 Marilyn now.)

### Production capacity (simplified)

* Production lead for finished goods is **~30 days**. An extra Elvis batch would finish around **Jan 19** and arrive around **Jan 21**, so it cannot help a Jan 10 request.
* Enough raw material exists; the constraint is time (long lead), not supply.

### PriceList rules (simple but convincing)

* Unit price: €12 each
* 24+ units: 5% discount
* Free shipping over €300

---

## Demo Flow A: New customer email → negotiation → order creation

### Step A1 — Input to **Sales Agent MCP**

User pastes the email:

> **From:** John Doe (DuckFan Paris)
> **Subject:** Need 24 Elvis ducks for Jan 10
> Hi,
> I’d like to order **24 Elvis Presley rubber ducks (20cm)** delivered to Paris **no later than Jan 10**.
> Can you confirm availability and send a quote?
> Thanks,
> John

**Sales Agent actions (MCP calls you’ll want):**

1. `crm_find_customers(name="John Doe", company="DuckFan Paris")` (then `crm_create_customer(...)` if not found)
2. `check_item_availability(item="ELVIS-DUCK-20CM", qty=24, date=Jan10)`
3. `suggest_alternatives()` based on stock + lead time
4. `draft_reply_email()` (important: give options)

### Step A1 — Expected outcome (what your MCP should return)

* Customer exists/created
* Availability result: **12 in stock now**; any additional Elvis would only arrive **around Jan 21** (30-day production lead + transit).
* Alternatives:

  * Option 1: **Stock mix** — ship **12 Elvis + 12 Marilyn** from stock to arrive by **Jan 10**.
  * Option 2: **Keep all Elvis** — ship **12 Elvis** by **Jan 10**, with the remaining **12 Elvis** arriving around **Jan 21** (production).
  * Option 3: **All Elvis later** — single shipment of **24 Elvis** arriving around **Jan 21** (production + transit).

### Step A1 — Draft reply (sales agent output)

You want the agent to produce a real “sendable” email draft like:

* Confirm what’s possible
* Offer choices
* Ask for confirmation on substitution/split

Example draft (tone: helpful + concrete):

> Hi John,
> Thanks for your request. For **ELVIS-DUCK-20CM**, we have **12 units in stock** and can deliver those to Paris by **Jan 10**.
> For the remaining 12, you have two options:
>
> 1. **Stock mix now:** ship **12 Elvis + 12 Marilyn (20cm)** together to arrive by **Jan 10**; or
> 2. **All Elvis later:** ship **12 Elvis** to arrive by **Jan 10**, then ship the remaining **12 Elvis** with expected arrival around **Jan 21** (production lead is ~30 days).
>    If you tell me which option you prefer (and your delivery address), I’ll send a formal quote right away.
>    Best regards,
>    (Your name)

That email is the “demo moment” because it shows reasoning grounded in stock and lead time.

---

### Step A2 — Customer responds (paste into Sales Agent)

> Hi,
> Let’s do **12 Elvis + 12 Marilyn**, all delivered by Jan 10. Address: …
> Please proceed.
> John

**Sales Agent MCP actions**

1. `create_sales_order(customer, lines=[...], requested_ship_date=Jan8/Jan9)`
2. `reserve_stock(item, qty, location)` (or create pick request)
3. `price_sales_order(sales_order_id, pricelist="Retail EU 2026")`
4. `create_shipment_from_sales_order(sales_order_id, planned_departure=Jan8, planned_arrival=Jan10)`
5. `draft_order_confirmation_email()`

**Sales agent output should include**

* SalesOrder created (2 lines)
* Shipment created (planned dates)
* Pricing applied (including any discount + free shipping)
* A clean confirmation email

---

## Demo Flow B: Another customer asks “where is my order?”

You absolutely should include this — it proves your MCP can query state across contexts.

### Background data you pre-create

Customer **Sarah Martin** has two orders:

* **SO-1030**: 10× CLASSIC-DUCK-10CM → already shipped yesterday
* **SO-1037**: 50× ELVIS-DUCK-20CM → in production, not yet shipped

### Step B1 — Input email to **Support/Sales Agent MCP**

> **From:** Sarah Martin
> **Subject:** Order status?
> Hi, can you tell me the status of my last two orders?
> One was small ducks, the other Elvis ducks.
> Thanks,
> Sarah

**Agent actions**

1. `crm_find_customers(name="Sarah Martin")`
2. `search_sales_orders(customer_id, last_n=2)`
3. For each order:

   * if shipped: `get_shipment_status(shipment_id)`
   * if in production: `get_production_order_status(production_order_id)` (progress by operations)
4. `draft_reply_email()` summarizing in plain language

**Draft reply example**

> Hi Sarah,
> Here’s the latest on your two orders:
>
> * **SO-1030 (10× Classic Duck 10cm):** shipped on **Dec 19**, carrier tracking shows it is **in transit** with expected delivery **Dec 22**.
> * **SO-1037 (50× Elvis Duck 20cm):** currently **in production**; molding is complete and the batch is in the **painting step**. We expect it to ship on **Dec 23**.
>   If you’d like, I can split the shipment so you receive any completed quantity earlier.
>   Best regards,
>   (Your name)

That’s a great “multi-context retrieval” demo: orders + shipment + production.

---

## How to structure MCP “agent contexts” cleanly

Even if it’s one server, it helps to present it as distinct tool sets:

### Sales context tools

* customer lookup/create
* quote/pricing
* sales order create/update
* reservation request
* shipment creation

Additional CRM helpers

* `crm_find_customers` returns possible matches
* `crm_create_customer` explicitly creates a customer
* `crm_get_customer_details` returns profile plus recent/pending orders

### Inventory context tools

* stock by item/location
* reserve/unreserve
* stock moves (pick, consume, produce, receive)

### Production context tools

* create production order from demand
* check capacity / lead time estimate
* operation progress updates
* consume ingredients / report finished qty

### Logistics context tools

* shipment planning
* shipment status updates
* link shipment ↔ sales order

This separation makes the demo feel like “agents” even if it’s one backend.

---

## A very workable “first demo script” (short)

1. Paste John’s email → Sales agent proposes options (key moment)
2. Paste John’s confirmation → Sales agent creates SO + Shipment + confirmation email
3. Paste Sarah status email → Agent returns one shipped + one in production + a reply

That’s enough to prove:

* reasoning
* data creation
* cross-module querying
* consistent terminology/state

---

Below is a **concrete demo transcript** you can use as the “golden path” for your MCP server. It’s written as a sequence of:

* **User input** (email pasted into the agent)
* **Agent → MCP tool calls** (what the agent asks the server to do)
* **MCP responses** (structured, grounded state changes / lookups)
* **Agent output** (draft reply email + what it “pseudo-sends”)

Assumptions (for realism + determinism):

* Today is **Sat, Dec 20, 2025** (Europe/Paris).
* Delivery promise dates are in **January 2026**.
* The dataset already contains Items/Locations/Machines and some Stock.

---

# MCP Demo Transcript

## Tool surface (example names)

You can rename these, but the transcript assumes these capabilities exist:

* `crm_find_customers`
* `crm_create_customer`
* `crm_get_customer_details`
* `catalog_get_item`
* `catalog_search_items`
* `inventory_list_items`
* `inventory_get_stock_summary`
* `sales_quote_options`
* `sales_create_sales_order`
* `sales_price_sales_order`
* `inventory_reserve_stock`
* `logistics_create_shipment`
* `sales_link_shipment_to_sales_order`
* `sales_draft_email`
* `sales_mark_email_sent`
* `sales_list_email_drafts`
* `sales_search_sales_orders`
* `logistics_get_shipment_status`
* `production_get_production_order_status`

---

## Scenario A — New order + negotiation

### A1) Customer email arrives (user pastes into Sales Agent)

**User → Sales Agent (pasted email)**
**From:** John Doe [john@duckfan-paris.example](mailto:john@duckfan-paris.example)
**Subject:** Need 24 Elvis ducks for Jan 10
Hi,
I’d like to order **24 Elvis Presley rubber ducks (20cm)** delivered to Paris **no later than Jan 10, 2026**.
Can you confirm availability and send a quote?
Thanks,
John

---

### A1) Agent queries ERP state

**Agent → MCP tool call 1**
`crm_find_customers({ name: "John Doe", company: "DuckFan Paris", email: "john@duckfan-paris.example" })`

**MCP → Agent response**
`{ customers: [] }`

**Agent → MCP tool call 2 (create explicitly if not found)**
`crm_create_customer({ name: "John Doe", company: "DuckFan Paris", email: "john@duckfan-paris.example", city: "Paris" })`

**MCP → Agent response**
`{ customer_id: "CUST-0102", customer: { ... } }`

**Agent → MCP tool call 3**
`catalog_get_item({ sku: "ELVIS-DUCK-20CM" })`

**MCP → Agent response**
`{ item_id: "ITEM-ELVIS-20", sku: "ELVIS-DUCK-20CM", name: "Elvis Duck 20cm", type: "finished_good" }`

**Agent → MCP tool call 4**
`inventory_get_stock_summary({ item_id: "ITEM-ELVIS-20" })`

**MCP → Agent response**

```json
{
  "item_id": "ITEM-ELVIS-20",
  "on_hand_total": 12,
  "reserved_total": 0,
  "available_total": 12,
  "by_location": [
    { "warehouse": "WH-LYON", "location": "FG/BIN-12", "on_hand": 12, "reserved": 0, "available": 12 }
  ]
}
```

**Agent (internally decides):** cannot deliver 24 Elvis by Jan 10 from stock.

**Agent → MCP tool call 5**
`catalog_get_item({ sku: "MARILYN-DUCK-20CM" })`

**MCP → Agent response**
`{ item_id: "ITEM-MARILYN-20", sku: "MARILYN-DUCK-20CM", name: "Marilyn Duck 20cm", type: "finished_good" }`

**Agent → MCP tool call 6**
`inventory_get_stock_summary({ item_id: "ITEM-MARILYN-20" })`

**MCP → Agent response**

```json
{
  "item_id": "ITEM-MARILYN-20",
  "on_hand_total": 12,
  "reserved_total": 0,
  "available_total": 12,
  "by_location": [
    { "warehouse": "WH-LYON", "location": "FG/BIN-14", "on_hand": 12, "reserved": 0, "available": 12 }
  ]
}
```

**Agent → MCP tool call 7**
`sales_quote_options({
  sku: "ELVIS-DUCK-20CM",
  qty: 24,
  need_by: "2026-01-10",
  allowed_substitutions: ["MARILYN-DUCK-20CM"]
})`

**MCP → Agent response**

```json
{
  "options": [
    {
      "option_id": "OPT-1",
      "summary": "Ship 12 from stock, 12 from production",
      "lines": [
        { "sku": "ELVIS-DUCK-20CM", "qty": 12, "source": "stock" },
        { "sku": "ELVIS-DUCK-20CM", "qty": 12, "source": "production" }
      ],
      "can_arrive_by": "2026-01-21",
      "notes": "Partial stock now; remainder after 30-day production lead."
    },
    {
      "option_id": "OPT-2",
      "summary": "Stock mix: 12 x ELVIS-DUCK-20CM + 12 x MARILYN-DUCK-20CM",
      "lines": [
        { "sku": "ELVIS-DUCK-20CM", "qty": 12, "source": "stock" },
        { "sku": "MARILYN-DUCK-20CM", "qty": 12, "source": "stock" }
      ],
      "can_arrive_by": "2026-01-10",
      "notes": "Mix requested SKU with substitution from stock to meet date."
    },
    {
      "option_id": "OPT-3",
      "summary": "Substitute 12 stock + 12 production of MARILYN-DUCK-20CM",
      "lines": [
        { "sku": "MARILYN-DUCK-20CM", "qty": 12, "source": "stock" },
        { "sku": "MARILYN-DUCK-20CM", "qty": 12, "source": "production", "lead_days": 30 }
      ],
      "can_arrive_by": "2026-01-21",
      "notes": "Within price band and same type; remainder after production lead."
    }
  ]
}
```

---

### A1) Agent drafts reply email (human-friendly negotiation)

**Agent → MCP tool call 8**
`sales_draft_email({
  to: "john@duckfan-paris.example",
  subject: "Re: 24 Elvis ducks delivery by Jan 10",
  context: {
    customer_id: "CUST-0102",
    key_points: [
      "We have 12 Elvis in stock now",
      "To meet Jan 10, we can mix 12 Elvis + 12 Marilyn from stock",
      "If you prefer all Elvis, the remaining 12 would arrive around Jan 21 (production lead)"
    ]
  }
})`

**MCP → Agent response**

```json
{
  "draft_id": "DRAFT-901",
  "body": "Hi John,\n\nThanks for your request. For ELVIS-DUCK-20CM (20cm), we currently have 12 units available in stock and can deliver those to Paris by Jan 10, 2026.\n\nTo cover the remaining 12 units, you have two options:\n1) Stock mix now: ship 12 Elvis + 12 Marilyn (20cm) together so everything arrives by Jan 10.\n2) All Elvis later: ship 12 Elvis to arrive by Jan 10, then ship the remaining 12 Elvis with expected arrival around Jan 21 (production lead is about 30 days).\n\nIf you tell me which option you prefer (and confirm the delivery address), I’ll send a formal quote and proceed.\n\nBest regards,\nSales Team\nRubber Duck Works"
}
```

**Agent → User (what the Sales Agent shows as the output)**

* Availability checked (12 Elvis available now)
* Proposed options (stock mix now vs all-Elvis later)
* **Draft reply ready to send**

**Agent → MCP tool call 9 (pseudo-send)**
`sales_mark_email_sent({ draft_id: "DRAFT-901", sent_at: "2025-12-20T10:18:00+01:00" })`

**MCP → Agent response**
`{ status: "sent", message_id: "MSG-77102" }`

---

## Scenario A continued — Customer accepts substitution, order gets created

### A2) Customer replies (user pastes response)

**User → Sales Agent (pasted email)**
**From:** John Doe [john@duckfan-paris.example](mailto:john@duckfan-paris.example)
**Subject:** Re: 24 Elvis ducks delivery by Jan 10
Hi,
Let’s do **12 Elvis + 12 Marilyn**, delivered by **Jan 10, 2026**.
Ship to: 14 Rue Example, 75011 Paris.
Please proceed.
John

---

### A2) Agent creates SalesOrder, reserves stock, creates Shipment, prices order, confirms

**Agent → MCP tool call 10**
`sales_create_sales_order({
  customer_id: "CUST-0102",
  requested_delivery_date: "2026-01-10",
  ship_to: { line1: "14 Rue Example", postal_code: "75011", city: "Paris", country: "FR" },
  lines: [
    { "sku": "ELVIS-DUCK-20CM", "qty": 12 },
    { "sku": "MARILYN-DUCK-20CM", "qty": 12 }
  ],
  note: "Customer accepted substitution to meet delivery date."
})`

**MCP → Agent response**

```json
{
  "sales_order_id": "SO-1042",
  "status": "draft",
  "lines": [
    { "line_id": "SO-1042-1", "sku": "ELVIS-DUCK-20CM", "qty": 12 },
    { "line_id": "SO-1042-2", "sku": "MARILYN-DUCK-20CM", "qty": 12 }
  ]
}
```

**Agent → MCP tool call 11**
`inventory_reserve_stock({
  reason: "sales_order",
  reference_id: "SO-1042",
  reservations: [
    { "sku": "ELVIS-DUCK-20CM", "qty": 12, "warehouse": "WH-LYON", "location": "FG/BIN-12" },
    { "sku": "MARILYN-DUCK-20CM", "qty": 12, "warehouse": "WH-LYON", "location": "FG/BIN-14" }
  ]
})`

**MCP → Agent response**
`{ status: "reserved", reservation_id: "RSV-5001" }`

**Agent → MCP tool call 12**
`sales_price_sales_order({ sales_order_id: "SO-1042", pricelist: "Retail EU 2026" })`

**MCP → Agent response**

```json
{
  "sales_order_id": "SO-1042",
  "pricing": {
    "currency": "EUR",
    "lines": [
      { "sku": "ELVIS-DUCK-20CM", "qty": 12, "unit_price": 12.0, "line_total": 144.0 },
      { "sku": "MARILYN-DUCK-20CM", "qty": 12, "unit_price": 12.0, "line_total": 144.0 }
    ],
    "discounts": [
      { "type": "volume", "description": "24+ units discount", "amount": -14.4 }
    ],
    "shipping": { "amount": 0.0, "description": "Free shipping over €300" },
    "total": 273.6
  }
}
```

**Agent → MCP tool call 13**
`logistics_create_shipment({
  ship_from: { "warehouse": "WH-LYON" },
  ship_to: { "line1": "14 Rue Example", "postal_code": "75011", "city": "Paris", "country": "FR" },
  planned_departure: "2026-01-08",
  planned_arrival: "2026-01-10",
  packages: [
    { "contents": [ { "sku": "ELVIS-DUCK-20CM", "qty": 12 }, { "sku": "MARILYN-DUCK-20CM", "qty": 12 } ] }
  ],
  reference: { "type": "sales_order", "id": "SO-1042" }
})`

**MCP → Agent response**
`{ shipment_id: "SHIP-900", status: "planned", planned_departure: "2026-01-08", planned_arrival: "2026-01-10" }`

**Agent → MCP tool call 14**
`sales_link_shipment_to_sales_order({ sales_order_id: "SO-1042", shipment_id: "SHIP-900" })`

**MCP → Agent response**
`{ status: "linked" }`

**Agent → MCP tool call 15**
`sales_draft_email({
  to: "john@duckfan-paris.example",
  subject: "Order confirmation SO-1042 — delivery by Jan 10",
  context: {
    sales_order_id: "SO-1042",
    shipment_id: "SHIP-900",
    pricing_total: "€273.60",
    planned_departure: "2026-01-08",
    planned_arrival: "2026-01-10"
  }
})`

**MCP → Agent response (draft)**

```json
{
  "draft_id": "DRAFT-919",
  "body": "Hi John,\n\nConfirmed — we’ve created order SO-1042 for:\n- 12 × Elvis Duck 20cm\n- 12 × Marilyn Duck 20cm\n\nPlanned shipment: departs Jan 8, 2026 and arrives in Paris by Jan 10, 2026 (SHIP-900).\nTotal: €273.60 (incl. volume discount; shipping free).\n\nIf you have any special delivery instructions (gate code, contact phone), just reply to this email.\n\nBest regards,\nSales Team\nRubber Duck Works"
}
```

**Agent → MCP tool call 16 (pseudo-send)**
`sales_mark_email_sent({ draft_id: "DRAFT-919", sent_at: "2025-12-20T10:29:00+01:00" })`

**MCP → Agent response**
`{ status: "sent", message_id: "MSG-77155" }`

---

## Scenario B — Existing customer asks for order status (one shipped, one in production)

### B1) Customer status email arrives (user pastes it)

**User → Sales Agent (pasted email)**
**From:** Sarah Martin [sarah@martin-retail.example](mailto:sarah@martin-retail.example)
**Subject:** Order status?
Hi, can you tell me the status of my last two orders?
One was small ducks, the other Elvis ducks.
Thanks,
Sarah

---

### B1) Agent finds customer, looks up last orders, returns shipment + production statuses

**Agent → MCP tool call 17**
`crm_find_customers({ name: "Sarah Martin", email: "sarah@martin-retail.example" })`

**MCP → Agent response**
`{ customers: [ { "id": "CUST-0044", "name": "Sarah Martin", "email": "sarah@martin-retail.example" } ] }`

**Agent → MCP tool call 18**
`sales_search_sales_orders({ customer_id: "CUST-0044", limit: 2, sort: "most_recent" })`

**MCP → Agent response**

```json
{
  "sales_orders": [
    {
      "sales_order_id": "SO-1037",
      "created_at": "2025-12-15",
      "summary": "50 × ELVIS-DUCK-20CM",
      "fulfillment_state": "in_production",
      "production_order_id": "MO-555"
    },
    {
      "sales_order_id": "SO-1030",
      "created_at": "2025-12-10",
      "summary": "10 × CLASSIC-DUCK-10CM",
      "fulfillment_state": "shipped",
      "shipment_id": "SHIP-870"
    }
  ]
}
```

**Agent → MCP tool call 19**
`production_get_production_order_status({ production_order_id: "MO-555" })`

**MCP → Agent response**

```json
{
  "production_order_id": "MO-555",
  "item": "ELVIS-DUCK-20CM",
  "qty_planned": 50,
  "qty_completed": 20,
  "current_operation": "Paint Elvis Hair",
  "eta_finish": "2026-01-19",
  "eta_ship": "2026-01-20"
}
```

**Agent → MCP tool call 20**
`logistics_get_shipment_status({ shipment_id: "SHIP-870" })`

**MCP → Agent response**

```json
{
  "shipment_id": "SHIP-870",
  "status": "in_transit",
  "departed_at": "2025-12-19",
  "planned_arrival": "2025-12-22",
  "tracking_ref": "CARRIER-XZ-112233"
}
```

**Agent → MCP tool call 21**
`sales_draft_email({
  to: "sarah@martin-retail.example",
  subject: "Re: Order status update",
  context: {
    customer_id: "CUST-0044",
    orders: [
      { "sales_order_id": "SO-1030", "shipment_id": "SHIP-870", "shipment_status": "in_transit", "arrival": "2025-12-22" },
      { "sales_order_id": "SO-1037", "production_order_id": "MO-555", "prod_status": "painting", "eta_ship": "2026-01-20" }
    ]
  }
})`

**MCP → Agent response (draft)**

```json
{
  "draft_id": "DRAFT-940",
  "body": "Hi Sarah,\n\nHere’s the latest on your two most recent orders:\n\n1) SO-1030 (10 × Classic Duck 10cm): shipped on Dec 19, 2025 and currently in transit (SHIP-870). Expected delivery: Dec 22, 2025. Tracking: CARRIER-XZ-112233.\n\n2) SO-1037 (50 × Elvis Duck 20cm): currently in production (MO-555). The batch is in the painting step and we expect it to ship on Jan 20, 2026.\n\nIf you need partial delivery on SO-1037, tell me and we can ship completed quantities earlier.\n\nBest regards,\nSales Team\nRubber Duck Works"
}
```

**Agent → MCP tool call 22 (pseudo-send)**
`sales_mark_email_sent({ draft_id: "DRAFT-940", sent_at: "2025-12-20T11:06:00+01:00" })`

**MCP → Agent response**
`{ status: "sent", message_id: "MSG-77220" }`

---

# Notes (so this works smoothly in “real demo life”)

* The transcript intentionally shows **cross-context reasoning**:

  * Sales checks inventory
  * Sales proposes substitution
  * Sales reserves stock
  * Logistics plans shipment
  * Status inquiry pulls shipment + production progress
* You don’t need “perfect ERP”: you just need **consistent state transitions** and **credible outputs**.
* If you want to weave in **StockMove** explicitly during shipping/production, add two visible actions later:

  * “Pick for shipment” stock moves out of FG bin
  * “Consume materials / receive finished goods” stock moves during production reporting


---

Great — now we freeze the scope and make this **boringly solid** 🙂

Below is a **minimal, demo-safe SQLite schema** that supports **exactly** the MCP functions and demo transcript you approved.
No extra columns, no future-proofing, no accounting depth.

This schema is intentionally:

* **Readable**
* **Queryable by an agent**
* **Easy to seed with mock data**
* **Stable for the demo**

---

# Design principles for this schema

* One table = one concept from the demo
* Only attributes that are:

  * referenced by MCP calls
  * needed to compute demo logic
  * needed to draft emails / statuses
* No hard constraints that would block demo flows
* Foreign keys are logical, not strict (SQLite-friendly)

---

# Core reference tables

## customers

```sql
CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT,
    email TEXT,
    city TEXT
);
```

Used by:

* `crm_find_customers`, `crm_create_customer`, `crm_get_customer_details`
* sales orders
* email drafting

---

## items

```sql
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    type TEXT NOT NULL            -- finished_good / material
);
```

Unified **Item** concept:

* finished ducks
* materials
* packaging (if needed later)

---

# Inventory

## stock

```sql
CREATE TABLE stock (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    warehouse TEXT NOT NULL,
    location TEXT NOT NULL,
    on_hand REAL NOT NULL,
    reserved REAL NOT NULL
);
```

Used by:

* `get_stock_summary`
* availability checks
* reservation logic

> Available = `on_hand - reserved` (computed, not stored)

---

## stock_reservations

```sql
CREATE TABLE stock_reservations (
    id TEXT PRIMARY KEY,
    reference_type TEXT NOT NULL,   -- sales_order
    reference_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty REAL NOT NULL,
    warehouse TEXT,
    location TEXT
);
```

Used by:

* `inventory_reserve_stock`
* tying reservations to a sales order

---

# Sales

## sales_orders

```sql
CREATE TABLE sales_orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    requested_delivery_date TEXT,
    ship_to_line1 TEXT,
    ship_to_postal_code TEXT,
    ship_to_city TEXT,
    ship_to_country TEXT,
    note TEXT,
    status TEXT                    -- draft / confirmed
);
```

Used by:

* order creation
* order lookup
* shipment linking

---

## sales_order_lines

```sql
CREATE TABLE sales_order_lines (
    id TEXT PRIMARY KEY,
    sales_order_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty REAL NOT NULL
);
```

Used by:

* pricing
* shipment contents
* availability logic

---

## sales_order_pricing

```sql
CREATE TABLE sales_order_pricing (
    sales_order_id TEXT PRIMARY KEY,
    currency TEXT NOT NULL,
    subtotal REAL NOT NULL,
    discount REAL NOT NULL,
    shipping REAL NOT NULL,
    total REAL NOT NULL
);
```

Used by:

* `price_sales_order`
* email confirmations

---

## email_drafts

```sql
CREATE TABLE email_drafts (
    id TEXT PRIMARY KEY,
    to_address TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_at TEXT
);
```

Used by:

* draft generation
* pseudo-send tracking

---

# Logistics

## shipments

```sql
CREATE TABLE shipments (
    id TEXT PRIMARY KEY,
    ship_from_warehouse TEXT,
    ship_to_line1 TEXT,
    ship_to_postal_code TEXT,
    ship_to_city TEXT,
    ship_to_country TEXT,
    planned_departure TEXT,
    planned_arrival TEXT,
    status TEXT,                    -- planned / in_transit / delivered
    tracking_ref TEXT
);
```

---

## shipment_lines

```sql
CREATE TABLE shipment_lines (
    id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty REAL NOT NULL
);
```

Used by:

* shipment creation
* shipment status replies

---

## sales_order_shipments

```sql
CREATE TABLE sales_order_shipments (
    sales_order_id TEXT NOT NULL,
    shipment_id TEXT NOT NULL,
    PRIMARY KEY (sales_order_id, shipment_id)
);
```

Simple link table, used by:

* status lookups
* customer communication

---

# Production (read-only for demo)

## production_orders

```sql
CREATE TABLE production_orders (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    qty_planned REAL NOT NULL,
    qty_completed REAL NOT NULL,
    current_operation TEXT,
    eta_finish TEXT,
    eta_ship TEXT
);
```

Used only by:

* `get_production_order_status`
* order status demo for Sarah

No execution logic needed.

---

# Optional but helpful seed tables (very small)

## pricelists

```sql
CREATE TABLE pricelists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    currency TEXT NOT NULL
);
```

## pricelist_lines

```sql
CREATE TABLE pricelist_lines (
    id TEXT PRIMARY KEY,
    pricelist_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    unit_price REAL NOT NULL
);
```

Discount logic can be hard-coded in MCP for demo purposes (24+ units → 5%).

---

# What is deliberately NOT in this schema

* Invoices tables (you didn’t execute them in demo)
* Machines, operators, recipes, ingredients
* Warehouses / locations as master data tables
* Stock moves
* Payments, accounting
* Users / auth
* Status history tables

All of those would add complexity without improving the demo.

---

# Mental check: does this schema support the full demo?

✔ Paste customer email → customer
✔ Check stock → stock + reservations
✔ Propose substitution → items + stock
✔ Create sales order → sales_orders + lines
✔ Reserve stock → stock_reservations
✔ Price order → sales_order_pricing
✔ Create shipment → shipments + shipment_lines
✔ Order status email → shipments + production_orders

---

