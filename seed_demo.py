"""Populate demo SQLite database with the dataset described in SPECIFICATION.md."""

from pathlib import Path
import sqlite3

from db import DB_PATH, init_db


def seed():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        # Customers
        conn.executemany(
            "INSERT INTO customers (id, name, company, email, city) VALUES (?, ?, ?, ?, ?)",
            [
                ("CUST-0044", "Sarah Martin", None, "sarah@martin-retail.example", "Paris"),
                ("CUST-0001", "Rubber Duck Works", None, "contact@rubberduck.example", "Lyon"),
                ("CUST-0102", "John Doe", "DuckFan Paris", "john@duckfan-paris.example", "Paris"),
            ],
        )

        # Items
        conn.executemany(
            "INSERT INTO items (id, sku, name, type, unit_price) VALUES (?, ?, ?, ?, ?)",
            [
                ("ITEM-ELVIS-20", "ELVIS-DUCK-20CM", "Elvis Duck 20cm", "finished_good", 12.0),
                ("ITEM-MARILYN-20", "MARILYN-DUCK-20CM", "Marilyn Duck 20cm", "finished_good", 12.0),
                ("ITEM-CLASSIC-10", "CLASSIC-DUCK-10CM", "Classic Duck 10cm", "finished_good", 10.0),
                ("ITEM-PVC", "PVC-PELLETS", "PVC Pellets", "material", None),
                ("ITEM-BLACK-DYE", "BLACK-DYE", "Black Dye", "material", None),
                ("ITEM-YELLOW-DYE", "YELLOW-DYE", "Yellow Dye", "material", None),
                ("ITEM-BOX-SMALL", "BOX-SMALL", "Small Box", "material", None),
            ],
        )

        # Stock
        conn.executemany(
            "INSERT INTO stock (id, item_id, warehouse, location, on_hand, reserved) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("STK-0001", "ITEM-ELVIS-20", "WH-LYON", "FG/BIN-12", 12, 0),
                ("STK-0002", "ITEM-MARILYN-20", "WH-LYON", "FG/BIN-14", 12, 0),
                ("STK-0003", "ITEM-CLASSIC-10", "WH-LYON", "FG/BIN-02", 100, 10),
                ("STK-0004", "ITEM-PVC", "WH-LYON", "RM/BULK-01", 1000, 0),
                ("STK-0005", "ITEM-BLACK-DYE", "WH-LYON", "RM/SHELF-01", 50, 0),
                ("STK-0006", "ITEM-YELLOW-DYE", "WH-LYON", "RM/SHELF-02", 50, 0),
                ("STK-0007", "ITEM-BOX-SMALL", "WH-LYON", "PK/BIN-01", 200, 0),
            ],
        )

        # Sales orders
        conn.execute(
            "INSERT INTO sales_orders (id, customer_id, requested_delivery_date, ship_to_line1, ship_to_postal_code, ship_to_city, ship_to_country, note, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "SO-1030",
                "CUST-0044",
                "2025-12-22",
                "12 Rue Client",
                "75002",
                "Paris",
                "FR",
                "Seed: classic ducks shipped",
                "confirmed",
                "2025-12-10",
            ),
        )
        conn.execute(
            "INSERT INTO sales_orders (id, customer_id, requested_delivery_date, ship_to_line1, ship_to_postal_code, ship_to_city, ship_to_country, note, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "SO-1037",
                "CUST-0044",
                "2025-12-23",
                "12 Rue Client",
                "75002",
                "Paris",
                "FR",
                "Seed: Elvis ducks in production",
                "in_production",
                "2025-12-15",
            ),
        )

        conn.executemany(
            "INSERT INTO sales_order_lines (id, sales_order_id, item_id, qty) VALUES (?, ?, ?, ?)",
            [
                ("SO-1030-1", "SO-1030", "ITEM-CLASSIC-10", 10),
                ("SO-1037-1", "SO-1037", "ITEM-ELVIS-20", 50),
            ],
        )

        # Pricing (optional pre-fill)
        conn.executemany(
            "INSERT INTO sales_order_pricing (sales_order_id, currency, subtotal, discount, shipping, total) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("SO-1030", "EUR", 120.0, 0.0, 15.0, 135.0),
                ("SO-1037", "EUR", 600.0, 30.0, 0.0, 570.0),
            ],
        )

        # Shipments
        conn.execute(
            "INSERT INTO shipments (id, ship_from_warehouse, ship_to_line1, ship_to_postal_code, ship_to_city, ship_to_country, planned_departure, planned_arrival, status, tracking_ref) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "SHIP-870",
                "WH-LYON",
                "12 Rue Client",
                "75002",
                "Paris",
                "FR",
                "2025-12-19",
                "2025-12-22",
                "in_transit",
                "CARRIER-XZ-112233",
            ),
        )
        conn.executemany(
            "INSERT INTO shipment_lines (id, shipment_id, item_id, qty) VALUES (?, ?, ?, ?)",
            [
                ("SHIP-870-1", "SHIP-870", "ITEM-CLASSIC-10", 10),
            ],
        )
        conn.executemany(
            "INSERT INTO sales_order_shipments (sales_order_id, shipment_id) VALUES (?, ?)",
            [
                ("SO-1030", "SHIP-870"),
            ],
        )

        # Production orders
        conn.execute(
            "INSERT INTO production_orders (id, item_id, qty_planned, qty_completed, current_operation, eta_finish, eta_ship) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "MO-555",
                "ITEM-ELVIS-20",
                50,
                20,
                "Paint Elvis Hair",
                "2026-01-19",
                "2026-01-20",
            ),
        )

        # Pricelist data (not strictly required)
        conn.execute(
            "INSERT INTO pricelists (id, name, currency) VALUES (?, ?, ?)",
            ("PL-EU-2026", "Retail EU 2026", "EUR"),
        )
        conn.executemany(
            "INSERT INTO pricelist_lines (id, pricelist_id, item_id, unit_price) VALUES (?, ?, ?, ?)",
            [
                ("PLL-1", "PL-EU-2026", "ITEM-ELVIS-20", 12.0),
                ("PLL-2", "PL-EU-2026", "ITEM-MARILYN-20", 12.0),
                ("PLL-3", "PL-EU-2026", "ITEM-CLASSIC-10", 10.0),
            ],
        )

        conn.commit()
        print(f"Seeded demo database at {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
