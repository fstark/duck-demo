-- SQLite schema for duck-demo MCP server

-- Simulation state - single row table for tracking simulated time
CREATE TABLE IF NOT EXISTS simulation_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    sim_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT,
    email TEXT,
    phone TEXT,
    address_line1 TEXT,
    address_line2 TEXT,
    city TEXT,
    postal_code TEXT,
    country TEXT DEFAULT 'FR',
    tax_id TEXT,
    payment_terms INTEGER DEFAULT 30,
    currency TEXT DEFAULT 'EUR',
    notes TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    unit_price REAL,           -- selling price (finished goods)
    cost_price REAL,           -- purchase cost (raw materials / components)
    uom TEXT DEFAULT 'ea',
    reorder_qty INTEGER DEFAULT 0,
    default_supplier_id TEXT,
    image BLOB
);

CREATE TABLE IF NOT EXISTS stock (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    warehouse TEXT NOT NULL,
    location TEXT NOT NULL,
    on_hand INTEGER NOT NULL
);

-- Quotes: customer quotations with pricing frozen at creation time
-- Status: draft -> sent -> accepted / rejected / expired / superseded
CREATE TABLE IF NOT EXISTS quotes (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    revision_number INTEGER NOT NULL DEFAULT 1,
    supersedes_quote_id TEXT,
    requested_delivery_date TEXT,
    ship_to_line1 TEXT,
    ship_to_line2 TEXT,
    ship_to_postal_code TEXT,
    ship_to_city TEXT,
    ship_to_country TEXT,
    note TEXT,
    subtotal REAL NOT NULL DEFAULT 0,
    discount REAL NOT NULL DEFAULT 0,
    shipping REAL NOT NULL DEFAULT 0,
    tax REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'EUR',
    valid_until TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    sent_at TEXT,
    accepted_at TEXT,
    rejected_at TEXT
);

CREATE TABLE IF NOT EXISTS quote_lines (
    id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    line_total REAL NOT NULL
);

-- Sales order workflow: draft -> confirmed -> completed
CREATE TABLE IF NOT EXISTS sales_orders (
    id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    requested_delivery_date TEXT,
    ship_to_line1 TEXT,
    ship_to_line2 TEXT,
    ship_to_postal_code TEXT,
    ship_to_city TEXT,
    ship_to_country TEXT,
    note TEXT,
    subtotal REAL NOT NULL DEFAULT 0,
    discount REAL NOT NULL DEFAULT 0,
    shipping REAL NOT NULL DEFAULT 0,
    tax REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'EUR',
    status TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS sales_order_lines (
    id TEXT PRIMARY KEY,
    sales_order_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    line_total REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    id TEXT PRIMARY KEY,
    ship_from_warehouse TEXT NOT NULL,
    ship_to_line1 TEXT NOT NULL,
    ship_to_line2 TEXT,
    ship_to_postal_code TEXT NOT NULL,
    ship_to_city TEXT NOT NULL,
    ship_to_country TEXT NOT NULL,
    planned_departure TEXT NOT NULL,
    planned_arrival TEXT NOT NULL,
    status TEXT NOT NULL,
    tracking_ref TEXT,
    dispatched_at TEXT,
    delivered_at TEXT
);

CREATE TABLE IF NOT EXISTS shipment_lines (
    id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sales_order_shipments (
    sales_order_id TEXT NOT NULL,
    shipment_id TEXT NOT NULL,
    PRIMARY KEY (sales_order_id, shipment_id)
);

-- Production order workflow: planned -> waiting (blocked on stock) -> ready -> in_progress -> completed
-- Each production order produces exactly one batch from one recipe
CREATE TABLE IF NOT EXISTS production_orders (
    id TEXT PRIMARY KEY,
    sales_order_id TEXT NOT NULL,
    recipe_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    status TEXT DEFAULT 'planned',
    parent_production_order_id TEXT,
    current_operation TEXT,
    qty_produced INTEGER,
    started_at TEXT,
    completed_at TEXT,
    eta_finish TEXT,
    eta_ship TEXT
);

-- Production operations track execution of each step in a production order
-- Status: pending -> in_progress -> completed (or failed)
CREATE TABLE IF NOT EXISTS production_operations (
    id TEXT PRIMARY KEY,
    production_order_id TEXT NOT NULL,
    recipe_operation_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    operation_name TEXT NOT NULL,
    duration_hours REAL NOT NULL,
    work_center TEXT,
    status TEXT DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT,
    blocked_reason TEXT,
    blocked_at TEXT
);

-- Suppliers for raw materials
CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    lead_time_days INTEGER NOT NULL
);

-- Recipes define how to produce finished goods from materials
CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,
    output_item_id TEXT NOT NULL,
    output_qty INTEGER NOT NULL,
    output_uom TEXT NOT NULL DEFAULT 'ea',
    production_time_hours REAL NOT NULL,
    notes TEXT
);

-- Recipe ingredients (bill of materials)
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id TEXT PRIMARY KEY,
    recipe_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    input_item_id TEXT NOT NULL,
    input_qty INTEGER NOT NULL,
    input_uom TEXT NOT NULL,
    notes TEXT
);

-- Work centers define shared production resources with finite capacity
CREATE TABLE IF NOT EXISTS work_centers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    max_concurrent INTEGER NOT NULL DEFAULT 1,
    description TEXT
);

-- Recipe operations (production steps)
CREATE TABLE IF NOT EXISTS recipe_operations (
    id TEXT PRIMARY KEY,
    recipe_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    operation_name TEXT NOT NULL,
    duration_hours REAL NOT NULL,
    work_center TEXT,
    notes TEXT
);

-- Purchase orders for restocking materials
-- Status: 'ordered' (sent to supplier), 'received' (arrived)
-- reorder_qty on items accumulates need; purchase_restock_materials() creates these orders
CREATE TABLE IF NOT EXISTS purchase_orders (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    supplier_id TEXT NOT NULL,
    unit_price REAL,
    total REAL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    status TEXT NOT NULL DEFAULT 'ordered',
    ordered_at TEXT,
    expected_delivery TEXT,
    received_at TEXT
);

CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    sales_order_id TEXT,
    recipient_email TEXT NOT NULL,
    recipient_name TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    sent_at TEXT
);

-- Invoices: generated from sales orders for billing
-- Status: draft -> issued -> paid / overdue
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    sales_order_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    invoice_date TEXT,
    due_date TEXT,
    subtotal REAL NOT NULL DEFAULT 0,
    discount REAL NOT NULL DEFAULT 0,
    shipping REAL NOT NULL DEFAULT 0,
    tax REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'EUR',
    status TEXT NOT NULL DEFAULT 'draft',
    issued_at TEXT,
    paid_at TEXT,
    created_at TEXT NOT NULL
);

-- Payments: record money received against invoices
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT NOT NULL DEFAULT 'bank_transfer',
    payment_date TEXT NOT NULL,
    reference TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

-- Documents: stores PDFs and other document artifacts
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    content BLOB NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/pdf',
    filename TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_entity ON documents(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);

-- Production wait log: event-sourced tracking of why production orders wait.
-- Each row is one wait period with a specific cause.
-- reason_type: 'material' (missing ingredient) or 'work_center' (capacity full)
-- reason_ref : the item_id (material) or work center name (work_center)
CREATE TABLE IF NOT EXISTS production_wait_log (
    id TEXT PRIMARY KEY,
    production_order_id TEXT NOT NULL,
    production_operation_id TEXT,
    reason_type TEXT NOT NULL,
    reason_ref TEXT NOT NULL,
    started_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pwl_mo ON production_wait_log(production_order_id);

-- Foreign-key / hot-path indexes
CREATE INDEX IF NOT EXISTS idx_stock_item ON stock(item_id);
CREATE INDEX IF NOT EXISTS idx_sol_so ON sales_order_lines(sales_order_id);
CREATE INDEX IF NOT EXISTS idx_sol_item ON sales_order_lines(item_id);
CREATE INDEX IF NOT EXISTS idx_ri_recipe ON recipe_ingredients(recipe_id);
CREATE INDEX IF NOT EXISTS idx_ro_recipe ON recipe_operations(recipe_id);
CREATE INDEX IF NOT EXISTS idx_po_ops ON production_operations(production_order_id);
CREATE INDEX IF NOT EXISTS idx_po_ops_wc ON production_operations(work_center, status);
CREATE INDEX IF NOT EXISTS idx_mo_status ON production_orders(status);
CREATE INDEX IF NOT EXISTS idx_inv_so ON invoices(sales_order_id);
CREATE INDEX IF NOT EXISTS idx_shiplines_ship ON shipment_lines(shipment_id);
CREATE INDEX IF NOT EXISTS idx_ql_quote ON quote_lines(quote_id);
CREATE INDEX IF NOT EXISTS idx_purchord_status ON purchase_orders(status, expected_delivery);
CREATE INDEX IF NOT EXISTS idx_sos_ship ON sales_order_shipments(shipment_id);
CREATE INDEX IF NOT EXISTS idx_payments_inv ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_emails_cust ON emails(customer_id);

-- Stock movements: full audit trail for every stock change
CREATE TABLE IF NOT EXISTS stock_movements (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    item_id TEXT NOT NULL,
    movement_type TEXT NOT NULL,
    qty INTEGER NOT NULL,
    stock_id TEXT NOT NULL,
    reference_type TEXT,
    reference_id TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_stock_mov_item ON stock_movements(item_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_stock_mov_stock ON stock_movements(stock_id);
CREATE INDEX IF NOT EXISTS idx_stock_mov_ref ON stock_movements(reference_type, reference_id);

-- Activity log: persistent event stream for factory observability
CREATE TABLE IF NOT EXISTS activity_log (
    id          TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    category    TEXT NOT NULL,
    action      TEXT NOT NULL,
    entity_type TEXT,
    entity_id   TEXT,
    details     TEXT
);
CREATE INDEX IF NOT EXISTS idx_actlog_ts       ON activity_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_actlog_entity   ON activity_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_actlog_action   ON activity_log(action);
CREATE INDEX IF NOT EXISTS idx_actlog_category ON activity_log(category);
