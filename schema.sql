-- SQLite schema for duck-demo MCP server

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT,
    email TEXT,
    city TEXT
);

CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    direction TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    interaction_at TEXT
);

CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    unit_price REAL
);

CREATE TABLE IF NOT EXISTS stock (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    warehouse TEXT NOT NULL,
    location TEXT NOT NULL,
    on_hand REAL NOT NULL,
    reserved REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_reservations (
    id TEXT PRIMARY KEY,
    reference_type TEXT NOT NULL,
    reference_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty REAL NOT NULL,
    warehouse TEXT,
    location TEXT
);

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

CREATE TABLE IF NOT EXISTS sales_order_pricing (
    sales_order_id TEXT PRIMARY KEY,
    currency TEXT NOT NULL,
    subtotal REAL NOT NULL,
    discount REAL NOT NULL,
    shipping REAL NOT NULL,
    total REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS email_drafts (
    id TEXT PRIMARY KEY,
    to_address TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_at TEXT
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

CREATE TABLE IF NOT EXISTS production_orders (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    qty_planned REAL NOT NULL,
    qty_completed REAL NOT NULL,
    current_operation TEXT,
    eta_finish TEXT,
    eta_ship TEXT
);

CREATE TABLE IF NOT EXISTS pricelists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    currency TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pricelist_lines (
    id TEXT PRIMARY KEY,
    pricelist_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    unit_price REAL NOT NULL
);
