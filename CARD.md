# Card Spotlight Design

Each overview card shows aggregate stats on the left and 2-3 "spotlight" items on the right for quick access to the most relevant records.

---

## Sales & CRM

### Customers
**Criteria:** Most recently interacted (requires `last_interacted` field or computed from related entities)
| Name | Sublabel |
|------|----------|
| Customer name | relative time ("2h ago", "yesterday") |

**Items:** 3 most recent

**Data source:** MAX of (last sales order, last quote, last email, last invoice) per customer

---

### Quotes
**Criteria:** Actionable quotes needing attention
| Name | Sublabel |
|------|----------|
| Quote ID | context |

**Items:**
1. **Newest** → most recent `created_at` where status = draft/sent → sublabel: "newest"
2. **Expiring soonest** → closest `valid_until` in future where status = sent → sublabel: "expires in Xd"

---

### Sales Orders
**Criteria:** High-value and urgent orders
| Name | Sublabel |
|------|----------|
| Order ID | context |

**Items:**
1. **Largest open** → highest `total` where status ≠ completed/cancelled → sublabel: formatted amount
2. **Most urgent** → closest `requested_delivery_date` in future → sublabel: "due today" / "due in Xd"

---

### Shipments
**Criteria:** Shipments requiring action
| Name | Sublabel |
|------|----------|
| Shipment ID | context |

**Items:**
1. **Pending pickup** → status = 'pending' ordered by created_at → sublabel: "pending"
2. **In transit** → status = 'in_transit' ordered by shipped_at → sublabel: "in transit"

---

### Invoices
**Criteria:** Payment urgency
| Name | Sublabel |
|------|----------|
| Invoice ID | context |

**Items:**
1. **Overdue** → status = 'overdue' ordered by due_date ASC → sublabel: "overdue" (could be red)
2. **Due soonest** → status = 'issued' with closest `due_date` → sublabel: "due in Xd"

---

### Emails
**Criteria:** Drafts needing completion
| Name | Sublabel |
|------|----------|
| Email subject (truncated) | recipient |

**Items:** 2-3 most recent drafts ordered by `updated_at` DESC

---

## Catalog & Inventory

### Items
**Criteria:** Recently added or popular
| Name | Sublabel |
|------|----------|
| Item name | SKU or category |

**Items:** 3 most recently created items (by `created_at` or just skip spotlight for this card)

**Note:** This card may not benefit much from spotlight — catalog is relatively static.

---

### Stock
**Criteria:** Low stock alerts
| Name | Sublabel |
|------|----------|
| Item name | qty on hand |

**Items:** 2-3 items with lowest stock relative to demand (or absolute low qty)

**Note:** Could highlight items below reorder point if that concept exists.

---

### Recipes
**Criteria:** None obvious

**Recommendation:** Skip spotlight for Recipes — it's reference data, not actionable.

---

## Production & Supply Chain

### Production Orders
**Criteria:** Active work
| Name | Sublabel |
|------|----------|
| Order ID | status |

**Items:**
1. **In progress** → status = 'in_progress' → sublabel: "in progress"
2. **Next planned** → status = 'planned' ordered by created_at → sublabel: "planned"

---

### Suppliers
**Criteria:** Active relationships

**Recommendation:** Skip spotlight — suppliers are reference data. Alternatively: supplier with most recent PO.

---

### Purchase Orders
**Criteria:** Pending arrivals
| Name | Sublabel |
|------|----------|
| PO ID | context |

**Items:**
1. **Awaiting delivery** → status = 'ordered' ordered by expected date → sublabel: "ordered"
2. **Recently received** → status = 'received' most recent → sublabel: "received"

---

## Summary: Cards WITH Spotlight

| Card | # Items | Primary Criteria |
|------|---------|------------------|
| Customers | 3 | Last interacted |
| Quotes | 2 | Newest + expiring soonest |
| Sales Orders | 2 | Largest + most urgent |
| Shipments | 2 | Pending + in transit |
| Invoices | 2 | Overdue + due soonest |
| Emails | 2-3 | Recent drafts |
| Stock | 2-3 | Low stock items |
| Production Orders | 2 | In progress + planned |
| Purchase Orders | 2 | Ordered + received |

## Cards WITHOUT Spotlight

| Card | Reason |
|------|--------|
| Items | Static catalog, not actionable |
| Recipes | Reference data |
| Suppliers | Reference data |

---

## Implementation Notes

1. **Customer `last_interacted`**: Needs either a DB column with triggers OR a computed field via JOIN across sales_orders, quotes, emails, invoices
2. **API endpoint**: Single `/api/stats/spotlight` returning all spotlight data to avoid N+1 calls
3. **Date formatting**: Use relative time ("2h ago", "yesterday", "3 days") for recency, countdown ("due in 2d", "expires in 5d") for deadlines
4. **Urgency colors**: Consider red/amber sublabel styling for "overdue" or "due today"
