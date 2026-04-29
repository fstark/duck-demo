"""Minimal seed data for contract tests.

Provides a small, deterministic dataset: 2 customers, 2 items (1 finished good,
1 raw material), 1 supplier, 1 recipe, stock for both items, 1 quote (accepted),
1 sales order (confirmed), 1 production order, 1 shipment, 1 invoice (issued),
1 email, 1 purchase order, and 1 payment.
Also includes QC seed data: 1 finished-good item with an image BLOB,
a recipe, and a completed production order with inspection_required=1.

All IDs are prefixed with "T-" to make them obviously test data.
"""

import config

SIM_TIME = "2025-08-01T08:00:00"

# ── Customers ──────────────────────────────────────────────────────────────
CUSTOMERS = [
    {
        "id": "CUST-0101",
        "name": "Alice Testworth",
        "company": "TestCorp",
        "email": "alice@testcorp.example",
        "phone": "+33 1 00 00 00 01",
        "address_line1": "1 Rue du Test",
        "city": "Paris",
        "postal_code": "75001",
        "country": "FR",
        "tax_id": "FR00000000001",
        "payment_terms": 30,
        "currency": "EUR",
        "notes": "Test customer A",
        "created_at": SIM_TIME,
    },
    {
        "id": "CUST-0102",
        "name": "Bob Mockman",
        "company": None,
        "email": "bob@mockman.example",
        "phone": None,
        "address_line1": "2 Avenue du Mock",
        "city": "Lyon",
        "postal_code": "69001",
        "country": "FR",
        "tax_id": None,
        "payment_terms": 30,
        "currency": "EUR",
        "notes": None,
        "created_at": SIM_TIME,
    },
]

# ── Suppliers ──────────────────────────────────────────────────────────────
SUPPLIERS = [
    {
        "id": "SUP-001",
        "name": "PlasticCorp",
        "contact_name": "Marc Dupont",
        "contact_email": "orders@plasticcorp.example",
        "contact_phone": "+33 1 40 00 11 22",
        "lead_time_days": 10,
    },
]

# ── Items ──────────────────────────────────────────────────────────────────
ITEMS = [
    {
        "id": "ITEM-PVC",
        "sku": "PVC-PELLETS",
        "name": "PVC Pellets",
        "type": "raw_material",
        "unit_price": None,
        "cost_price": 0.012,
        "uom": "g",
        "reorder_qty": 1500000,
        "default_supplier_id": "SUP-001",
        "image": None,
    },
    {
        "id": "ITEM-YELLOW-DYE",
        "sku": "YELLOW-DYE",
        "name": "Yellow Dye",
        "type": "raw_material",
        "unit_price": None,
        "cost_price": 0.09,
        "uom": "ml",
        "reorder_qty": 800,
        "default_supplier_id": None,
        "image": None,
    },
    {
        "id": "ITEM-BOX-SMALL",
        "sku": "BOX-SMALL",
        "name": "Small Box",
        "type": "raw_material",
        "unit_price": None,
        "cost_price": 0.45,
        "uom": "ea",
        "reorder_qty": 1000,
        "default_supplier_id": None,
        "image": None,
    },
    {
        "id": "ITEM-CLASSIC-10",
        "sku": "CLASSIC-DUCK-10CM",
        "name": "Classic Duck 10cm",
        "type": "finished_good",
        "unit_price": 10.0,
        "cost_price": None,
        "uom": "ea",
        "reorder_qty": 0,
        "default_supplier_id": None,
        "image": None,
    },
    # QC test item — has a 1-pixel JPEG image BLOB for inspection tests
    {
        "id": "ITEM-QC-DUCK",
        "sku": "QC-DUCK-TEST",
        "name": "QC Test Duck",
        "type": "finished_good",
        "unit_price": 12.0,
        "cost_price": None,
        "uom": "ea",
        "reorder_qty": 0,
        "default_supplier_id": None,
        # Minimal 1x1 JPEG (valid JPEG bytes for testing reference image resolution)
        "image": bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
            0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
            0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
            0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
            0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
            0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
            0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
            0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD6, 0xFF, 0xD9,
        ]),
    },
]

# ── Recipes ────────────────────────────────────────────────────────────────
RECIPES = [
    {
        "id": "RCP-CLASSIC-10",
        "output_item_id": "ITEM-CLASSIC-10",
        "output_qty": 24,
        "output_uom": "ea",
        "production_time_hours": 2.5,
        "notes": "Classic yellow duck - high volume simple design",
    },
]

RECIPE_INGREDIENTS = [
    {"id": "ING-T001", "recipe_id": "RCP-CLASSIC-10", "sequence_order": 1, "input_item_id": "ITEM-PVC", "input_qty": 1200, "input_uom": "g"},
    {"id": "ING-T002", "recipe_id": "RCP-CLASSIC-10", "sequence_order": 2, "input_item_id": "ITEM-YELLOW-DYE", "input_qty": 150, "input_uom": "ml"},
    {"id": "ING-T003", "recipe_id": "RCP-CLASSIC-10", "sequence_order": 3, "input_item_id": "ITEM-BOX-SMALL", "input_qty": 2, "input_uom": "ea"},
]

RECIPE_OPERATIONS = [
    {"id": "OP-T001", "recipe_id": "RCP-CLASSIC-10", "sequence_order": 1, "operation_name": "Mold injection", "duration_hours": 1.0, "work_center": "MOLDING"},
    {"id": "OP-T002", "recipe_id": "RCP-CLASSIC-10", "sequence_order": 2, "operation_name": "Paint yellow", "duration_hours": 0.75, "work_center": "PAINTING"},
    {"id": "OP-T003", "recipe_id": "RCP-CLASSIC-10", "sequence_order": 3, "operation_name": "Quality check", "duration_hours": 0.5, "work_center": "QC"},
    {"id": "OP-T004", "recipe_id": "RCP-CLASSIC-10", "sequence_order": 4, "operation_name": "Pack into boxes", "duration_hours": 0.25, "work_center": "PACKAGING"},
]

# ── Work centers ───────────────────────────────────────────────────────────
WORK_CENTERS = [
    {"id": "WC-MOLDING", "name": "MOLDING", "max_concurrent": 3, "description": "Molding work center"},
    {"id": "WC-PAINTING", "name": "PAINTING", "max_concurrent": 4, "description": "Painting work center"},
    {"id": "WC-QC", "name": "QC", "max_concurrent": 2, "description": "Quality check work center"},
    {"id": "WC-PACKAGING", "name": "PACKAGING", "max_concurrent": 3, "description": "Packaging work center"},
    {"id": "WC-CURING", "name": "CURING", "max_concurrent": 2, "description": "Curing work center"},
    {"id": "WC-ASSEMBLY", "name": "ASSEMBLY", "max_concurrent": 2, "description": "Assembly work center"},
]

# ── Stock ──────────────────────────────────────────────────────────────────
STOCK = [
    {"id": "STK-T001", "item_id": "ITEM-PVC", "warehouse": config.WAREHOUSE_DEFAULT, "location": "RM/BULK-01", "on_hand": 500000},
    {"id": "STK-T002", "item_id": "ITEM-YELLOW-DYE", "warehouse": config.WAREHOUSE_DEFAULT, "location": "RM/SHELF-02", "on_hand": 600},
    {"id": "STK-T003", "item_id": "ITEM-BOX-SMALL", "warehouse": config.WAREHOUSE_DEFAULT, "location": "PK/BIN-01", "on_hand": 200},
    {"id": "STK-T004", "item_id": "ITEM-CLASSIC-10", "warehouse": config.WAREHOUSE_DEFAULT, "location": "FG", "on_hand": 48},
]

STOCK_MOVEMENTS = [
    {"id": "MOV-T001", "timestamp": SIM_TIME, "item_id": "ITEM-PVC", "movement_type": "adjustment", "qty": 500000, "stock_id": "STK-T001", "reference_type": "backfill", "reference_id": None, "notes": "Test seed"},
    {"id": "MOV-T002", "timestamp": SIM_TIME, "item_id": "ITEM-YELLOW-DYE", "movement_type": "adjustment", "qty": 600, "stock_id": "STK-T002", "reference_type": "backfill", "reference_id": None, "notes": "Test seed"},
    {"id": "MOV-T003", "timestamp": SIM_TIME, "item_id": "ITEM-BOX-SMALL", "movement_type": "adjustment", "qty": 200, "stock_id": "STK-T003", "reference_type": "backfill", "reference_id": None, "notes": "Test seed"},
    {"id": "MOV-T004", "timestamp": SIM_TIME, "item_id": "ITEM-CLASSIC-10", "movement_type": "adjustment", "qty": 48, "stock_id": "STK-T004", "reference_type": "backfill", "reference_id": None, "notes": "Test seed"},
]

# ── Quotes ─────────────────────────────────────────────────────────────────
QUOTES = [
    {
        "id": "QUO-T001",
        "customer_id": "CUST-0101",
        "revision_number": 1,
        "supersedes_quote_id": None,
        "requested_delivery_date": "2025-08-20",
        "ship_to_line1": "1 Rue du Test",
        "ship_to_line2": None,
        "ship_to_postal_code": "75001",
        "ship_to_city": "Paris",
        "ship_to_country": "FR",
        "note": "Test quote",
        "subtotal": 120.0,
        "discount": 0.0,
        "shipping": 20.0,
        "tax": 0.0,
        "total": 140.0,
        "currency": "EUR",
        "valid_until": "2025-09-01",
        "status": "accepted",
        "created_at": SIM_TIME,
        "sent_at": SIM_TIME,
        "accepted_at": SIM_TIME,
        "rejected_at": None,
    },
]

QUOTE_LINES = [
    {"id": "QL-T001", "quote_id": "QUO-T001", "item_id": "ITEM-CLASSIC-10", "qty": 12, "unit_price": 10.0, "line_total": 120.0},
]

# ── Sales orders ───────────────────────────────────────────────────────────
SALES_ORDERS = [
    {
        "id": "SO-T001",
        "quote_id": "QUO-T001",
        "customer_id": "CUST-0101",
        "requested_delivery_date": "2025-08-20",
        "ship_to_line1": "1 Rue du Test",
        "ship_to_line2": None,
        "ship_to_postal_code": "75001",
        "ship_to_city": "Paris",
        "ship_to_country": "FR",
        "note": "Test sales order",
        "subtotal": 120.0,
        "discount": 0.0,
        "shipping": 20.0,
        "tax": 0.0,
        "total": 140.0,
        "currency": "EUR",
        "status": "confirmed",
        "created_at": SIM_TIME,
    },
]

SALES_ORDER_LINES = [
    {"id": "SOL-T001", "sales_order_id": "SO-T001", "item_id": "ITEM-CLASSIC-10", "qty": 12, "unit_price": 10.0, "line_total": 120.0},
]

# ── Shipments ──────────────────────────────────────────────────────────────
SHIPMENTS = [
    {
        "id": "SHIP-T001",
        "ship_from_warehouse": config.WAREHOUSE_DEFAULT,
        "ship_to_line1": "1 Rue du Test",
        "ship_to_line2": None,
        "ship_to_postal_code": "75001",
        "ship_to_city": "Paris",
        "ship_to_country": "FR",
        "planned_departure": "2025-08-18",
        "planned_arrival": "2025-08-20",
        "status": "planned",
        "tracking_ref": None,
        "dispatched_at": None,
        "delivered_at": None,
    },
    {
        "id": "SHIP-T002",
        "ship_from_warehouse": config.WAREHOUSE_DEFAULT,
        "ship_to_line1": "123 Main St",
        "ship_to_line2": None,
        "ship_to_postal_code": "10001",
        "ship_to_city": "New York",
        "ship_to_country": "US",
        "planned_departure": "2025-08-18",
        "planned_arrival": "2025-08-25",
        "status": "planned",
        "tracking_ref": None,
        "dispatched_at": None,
        "delivered_at": None,
    },
]

SHIPMENT_LINES = [
    {
        "id": "SHL-T001",
        "shipment_id": "SHIP-T001",
        "item_id": "ITEM-CLASSIC-10",
        "qty": 12,
        "tariff_code": None,
        "tariff_description": None,
    },
    {
        "id": "SHL-T002",
        "shipment_id": "SHIP-T002",
        "item_id": "ITEM-CLASSIC-10",
        "qty": 6,
        "tariff_code": "9503.00",
        "tariff_description": "Toys; other toys",
    },
]

SALES_ORDER_SHIPMENTS = [
    {"sales_order_id": "SO-T001", "shipment_id": "SHIP-T001"},
    {"sales_order_id": "SO-T001", "shipment_id": "SHIP-T002"},
]

# ── Production orders ──────────────────────────────────────────────────────
PRODUCTION_ORDERS = [
    {
        "id": "MO-T001",
        "sales_order_id": "SO-T001",
        "recipe_id": "RCP-CLASSIC-10",
        "item_id": "ITEM-CLASSIC-10",
        "status": "planned",
        "parent_production_order_id": None,
        "current_operation": None,
        "qty_produced": None,
        "started_at": None,
        "completed_at": None,
        "eta_finish": None,
        "eta_ship": None,
    },
]

PRODUCTION_OPERATIONS = [
    {"id": "POP-T001", "production_order_id": "MO-T001", "recipe_operation_id": "OP-T001", "sequence_order": 1, "operation_name": "Mold injection", "duration_hours": 1.0, "work_center": "MOLDING", "status": "pending"},
    {"id": "POP-T002", "production_order_id": "MO-T001", "recipe_operation_id": "OP-T002", "sequence_order": 2, "operation_name": "Paint yellow", "duration_hours": 0.75, "work_center": "PAINTING", "status": "pending"},
    {"id": "POP-T003", "production_order_id": "MO-T001", "recipe_operation_id": "OP-T003", "sequence_order": 3, "operation_name": "Quality check", "duration_hours": 0.5, "work_center": "QC", "status": "pending"},
    {"id": "POP-T004", "production_order_id": "MO-T001", "recipe_operation_id": "OP-T004", "sequence_order": 4, "operation_name": "Pack into boxes", "duration_hours": 0.25, "work_center": "PACKAGING", "status": "pending"},
]

# ── QC seed data ───────────────────────────────────────────────────────────
# Recipe for the QC test item
QC_RECIPES = [
    {
        "id": "RCP-QC-DUCK",
        "output_item_id": "ITEM-QC-DUCK",
        "output_qty": 12,
        "output_uom": "ea",
        "production_time_hours": 2.0,
        "notes": "QC test duck recipe",
    },
]

QC_RECIPE_INGREDIENTS = [
    {"id": "ING-QC001", "recipe_id": "RCP-QC-DUCK", "sequence_order": 1, "input_item_id": "ITEM-PVC", "input_qty": 600, "input_uom": "g"},
]

# A completed production order with inspection_required=1 (fixture for QC tests)
QC_SALES_ORDERS = [
    {
        "id": "SO-QC001",
        "quote_id": "QUO-T001",
        "customer_id": "CUST-0101",
        "requested_delivery_date": "2025-08-20",
        "ship_to_line1": "1 Rue du Test",
        "ship_to_line2": None,
        "ship_to_postal_code": "75001",
        "ship_to_city": "Paris",
        "ship_to_country": "FR",
        "note": "QC test SO",
        "subtotal": 144.0,
        "discount": 0.0,
        "shipping": 20.0,
        "tax": 0.0,
        "total": 164.0,
        "currency": "EUR",
        "status": "confirmed",
        "created_at": SIM_TIME,
    },
]

QC_SALES_ORDER_LINES = [
    {"id": "SOL-QC001", "sales_order_id": "SO-QC001", "item_id": "ITEM-QC-DUCK", "qty": 12, "unit_price": 12.0, "line_total": 144.0},
]

QC_PRODUCTION_ORDERS = [
    {
        "id": "MO-QC001",
        "sales_order_id": "SO-QC001",
        "recipe_id": "RCP-QC-DUCK",
        "item_id": "ITEM-QC-DUCK",
        "status": "completed",
        "parent_production_order_id": None,
        "current_operation": None,
        "qty_produced": 12,
        "started_at": SIM_TIME,
        "completed_at": SIM_TIME,
        "eta_finish": "2025-08-01",
        "eta_ship": "2025-08-02",
        "inspection_required": 1,
        "inspection_status": "pending_inspection",
    },
    # A second MO that is still completable (used in completion tests)
    {
        "id": "MO-QC002",
        "sales_order_id": "SO-QC001",
        "recipe_id": "RCP-QC-DUCK",
        "item_id": "ITEM-QC-DUCK",
        "status": "planned",
        "parent_production_order_id": None,
        "current_operation": None,
        "qty_produced": None,
        "started_at": None,
        "completed_at": None,
        "eta_finish": "2025-08-05",
        "eta_ship": "2025-08-06",
        "inspection_required": 1,
        "inspection_status": "none",
    },
]

QC_HOLD_BATCHES = [
    {
        "id": "QCB-T001",
        "production_order_id": "MO-QC001",
        "sales_order_id": "SO-QC001",
        "item_id": "ITEM-QC-DUCK",
        "status": "pending",
        "qty_on_hold": 12,
        "qty_released": 0,
        "qty_scrapped": 0,
        "created_at": SIM_TIME,
        "released_at": None,
    },
]

# ── Purchase orders ────────────────────────────────────────────────────────
PURCHASE_ORDERS = [
    {
        "id": "PO-T001",
        "item_id": "ITEM-PVC",
        "qty": 1500000,
        "supplier_id": "SUP-001",
        "unit_price": 0.012,
        "total": 18000.0,
        "currency": "EUR",
        "status": "ordered",
        "ordered_at": SIM_TIME,
        "expected_delivery": "2025-08-11",
        "received_at": None,
    },
]

# ── Invoices ───────────────────────────────────────────────────────────────
INVOICES = [
    {
        "id": "INV-T001",
        "sales_order_id": "SO-T001",
        "customer_id": "CUST-0101",
        "invoice_date": "2025-08-01",
        "due_date": "2025-08-31",
        "subtotal": 120.0,
        "discount": 0.0,
        "shipping": 20.0,
        "tax": 0.0,
        "total": 140.0,
        "currency": "EUR",
        "status": "issued",
        "issued_at": SIM_TIME,
        "paid_at": None,
        "created_at": SIM_TIME,
    },
]

# ── Payments ───────────────────────────────────────────────────────────────
PAYMENTS = [
    {
        "id": "PAY-T001",
        "invoice_id": "INV-T001",
        "amount": 140.0,
        "payment_method": "bank_transfer",
        "payment_date": "2025-08-01",
        "reference": "REF-TEST-001",
        "notes": "Test payment",
        "created_at": SIM_TIME,
    },
]

# ── Emails ─────────────────────────────────────────────────────────────────
EMAILS = [
    {
        "id": "EMAIL-T001",
        "customer_id": "CUST-0101",
        "sales_order_id": "SO-T001",
        "recipient_email": "alice@testcorp.example",
        "recipient_name": "Alice Testworth",
        "subject": "Order SO-T001 confirmation",
        "body": "Dear Alice, your order has been confirmed.",
        "status": "sent",
        "created_at": SIM_TIME,
        "modified_at": SIM_TIME,
        "sent_at": SIM_TIME,
    },
]

# ── Activity log (single entry) ───────────────────────────────────────────
ACTIVITY_LOG = [
    {
        "id": "ACT-T001",
        "timestamp": SIM_TIME,
        "actor": "mcp:sales",
        "category": "sales",
        "action": "sales_order.confirmed",
        "entity_type": "sales_order",
        "entity_id": "SO-T001",
        "details": '{"sales_order_id": "SO-T001"}',
    },
]


# ============================================================================
# Table insertion order (respects FK dependencies)
# ============================================================================
TABLE_DATA = [
    ("simulation_state", [{"id": 1, "sim_time": SIM_TIME}]),
    ("suppliers", SUPPLIERS),
    ("customers", CUSTOMERS),
    ("items", ITEMS),
    ("stock", STOCK),
    ("stock_movements", STOCK_MOVEMENTS),
    ("recipes", RECIPES),
    ("recipe_ingredients", RECIPE_INGREDIENTS),
    ("recipe_operations", RECIPE_OPERATIONS),
    ("work_centers", WORK_CENTERS),
    ("quotes", QUOTES),
    ("quote_lines", QUOTE_LINES),
    ("sales_orders", SALES_ORDERS),
    ("sales_order_lines", SALES_ORDER_LINES),
    ("shipments", SHIPMENTS),
    ("shipment_lines", SHIPMENT_LINES),
    ("sales_order_shipments", SALES_ORDER_SHIPMENTS),
    ("production_orders", PRODUCTION_ORDERS),
    ("production_operations", PRODUCTION_OPERATIONS),
    ("purchase_orders", PURCHASE_ORDERS),
    ("invoices", INVOICES),
    ("payments", PAYMENTS),
    ("emails", EMAILS),
    ("activity_log", ACTIVITY_LOG),
    # QC seed data
    ("recipes", QC_RECIPES),
    ("recipe_ingredients", QC_RECIPE_INGREDIENTS),
    ("sales_orders", QC_SALES_ORDERS),
    ("sales_order_lines", QC_SALES_ORDER_LINES),
    ("production_orders", QC_PRODUCTION_ORDERS),
    ("qc_hold_batches", QC_HOLD_BATCHES),
    # Import tables (empty — jobs created on demand)
    ("import_jobs", []),
    ("import_rows", []),
]
