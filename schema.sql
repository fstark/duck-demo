-- SQLite schema for duck-demo MCP server

-- Simulation state - single row table for tracking simulated time
DROP TABLE IF EXISTS simulation_state;
CREATE TABLE simulation_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    sim_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT,
    email TEXT,
    city TEXT
);

CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    unit_price REAL,
    uom TEXT DEFAULT 'ea',
    reorder_qty REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stock (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    warehouse TEXT NOT NULL,
    location TEXT NOT NULL,
    on_hand REAL NOT NULL
);

-- Sales order workflow: draft -> committed (price locked) -> delivery (stock allocated) -> completed
CREATE TABLE IF NOT EXISTS sales_orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    requested_delivery_date TEXT,
    ship_to_line1 TEXT,
    ship_to_postal_code TEXT,
    ship_to_city TEXT,
    ship_to_country TEXT,
    note TEXT,
    status TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sales_order_lines (
    id TEXT PRIMARY KEY,
    sales_order_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    id TEXT PRIMARY KEY,
    ship_from_warehouse TEXT,
    ship_to_line1 TEXT,
    ship_to_postal_code TEXT,
    ship_to_city TEXT,
    ship_to_country TEXT,
    planned_departure TEXT,
    planned_arrival TEXT,
    status TEXT,
    tracking_ref TEXT
);

CREATE TABLE IF NOT EXISTS shipment_lines (
    id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty REAL NOT NULL
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
    recipe_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    status TEXT DEFAULT 'planned',
    parent_production_order_id TEXT,
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
    status TEXT DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT
);

-- Suppliers for raw materials
CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    contact_email TEXT,
    lead_time_days INTEGER NOT NULL
);

-- Recipes define how to produce finished goods from materials
CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,
    output_item_id TEXT NOT NULL,
    output_qty REAL NOT NULL,
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
    input_qty REAL NOT NULL,
    input_uom TEXT NOT NULL,
    notes TEXT
);

-- Recipe operations (production steps)
CREATE TABLE IF NOT EXISTS recipe_operations (
    id TEXT PRIMARY KEY,
    recipe_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    operation_name TEXT NOT NULL,
    duration_hours REAL NOT NULL,
    notes TEXT
);

-- Purchase orders for restocking materials
-- Status: 'ordered' (sent to supplier), 'received' (arrived)
-- reorder_qty on items accumulates need; purchase_restock_materials() creates these orders
CREATE TABLE IF NOT EXISTS purchase_orders (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    qty REAL NOT NULL,
    supplier_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ordered',
    ordered_at TEXT DEFAULT (datetime('now')),
    expected_delivery TEXT,
    received_at TEXT
);
