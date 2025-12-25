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
                ("CUST-0103", "Daisy Paddlesworth", "Splash & Co", "daisy@splashco.example", "Nice"),
                ("CUST-0104", "Quackers McGee", None, "quackers@pond.example", "Marseille"),
                ("CUST-0105", "Bella Featherstone", "The Duck Emporium", "bella@duckemporium.example", "Toulouse"),
                ("CUST-0106", "Puddles O'Mallory", None, "puddles@mailexample.example", "Bordeaux"),
                ("CUST-0107", "Drake Fluffington", "Fluff & Feathers", "drake@fluffnfeathers.example", "Strasbourg"),
                ("CUST-0108", "Mallory Beakworth", None, "mallory@beakmail.example", "Nantes"),
                ("CUST-0109", "Waddles Johnson", "Waddle Inc", "waddles@waddleinc.example", "Lille"),
                ("CUST-0110", "Ducky McDuckface", None, "ducky@mcduckface.example", "Montpellier"),
                ("CUST-0111", "Splash Gordon", "Aquatic Adventures", "splash@aquatic.example", "Rennes"),
                ("CUST-0112", "Feather McFloaty", None, "feather@floaty.example", "Grenoble"),
                ("CUST-0113", "Bubbles LaRue", "Bath Time Boutique", "bubbles@bathtime.example", "Dijon"),
                ("CUST-0114", "Captain Quack", "Quack Squadron", "captain@quacksquadron.example", "Angers"),
                ("CUST-0115", "Honk Singleton", None, "honk@singleton.example", "Le Havre"),
                ("CUST-0116", "Webby Toes", "Webfoot Wonders", "webby@webfoot.example", "Reims"),
            ],
        )

        # Items
        conn.executemany(
            "INSERT INTO items (id, sku, name, type, unit_price, uom, reorder_qty) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("ITEM-ELVIS-20", "ELVIS-DUCK-20CM", "Elvis Duck 20cm", "finished_good", 12.0, "ea", 0),
                ("ITEM-MARILYN-20", "MARILYN-DUCK-20CM", "Marilyn Duck 20cm", "finished_good", 12.0, "ea", 0),
                ("ITEM-CLASSIC-10", "CLASSIC-DUCK-10CM", "Classic Duck 10cm", "finished_good", 10.0, "ea", 0),
                ("ITEM-PIRATE-15", "PIRATE-DUCK-15CM", "Pirate Duck 15cm", "finished_good", 14.5, "ea", 0),
                ("ITEM-NINJA-12", "NINJA-DUCK-12CM", "Ninja Duck 12cm", "finished_good", 13.0, "ea", 0),
                ("ITEM-UNICORN-25", "UNICORN-DUCK-25CM", "Unicorn Duck 25cm", "finished_good", 18.0, "ea", 0),
                ("ITEM-DISCO-18", "DISCO-DUCK-18CM", "Disco Duck 18cm", "finished_good", 15.5, "ea", 0),
                ("ITEM-WIZARD-20", "WIZARD-DUCK-20CM", "Wizard Duck 20cm", "finished_good", 16.0, "ea", 0),
                ("ITEM-ASTRONAUT-22", "ASTRONAUT-DUCK-22CM", "Astronaut Duck 22cm", "finished_good", 19.0, "ea", 0),
                ("ITEM-SUPERHERO-20", "SUPERHERO-DUCK-20CM", "Superhero Duck 20cm", "finished_good", 17.5, "ea", 0),
                ("ITEM-ZOMBIE-15", "ZOMBIE-DUCK-15CM", "Zombie Duck 15cm", "finished_good", 11.5, "ea", 0),
                ("ITEM-VIKING-18", "VIKING-DUCK-18CM", "Viking Duck 18cm", "finished_good", 16.5, "ea", 0),
                ("ITEM-MERMAID-20", "MERMAID-DUCK-20CM", "Mermaid Duck 20cm", "finished_good", 14.0, "ea", 0),
                ("ITEM-ROBOT-25", "ROBOT-DUCK-25CM", "Robot Duck 25cm", "finished_good", 22.0, "ea", 0),
                ("ITEM-CHEF-15", "CHEF-DUCK-15CM", "Chef Duck 15cm", "finished_good", 13.5, "ea", 0),
                ("ITEM-ROCKSTAR-20", "ROCKSTAR-DUCK-20CM", "Rockstar Duck 20cm", "finished_good", 15.0, "ea", 0),
                ("ITEM-DETECTIVE-18", "DETECTIVE-DUCK-18CM", "Detective Duck 18cm", "finished_good", 14.5, "ea", 0),
                ("ITEM-SURFER-15", "SURFER-DUCK-15CM", "Surfer Duck 15cm", "finished_good", 12.5, "ea", 0),
                ("ITEM-COWBOY-20", "COWBOY-DUCK-20CM", "Cowboy Duck 20cm", "finished_good", 16.0, "ea", 0),
                ("ITEM-BALLERINA-12", "BALLERINA-DUCK-12CM", "Ballerina Duck 12cm", "finished_good", 11.0, "ea", 0),
                ("ITEM-GARDEN-GNOME-30", "GNOME-DUCK-30CM", "Garden Gnome Duck 30cm", "finished_good", 25.0, "ea", 0),
                ("ITEM-PVC", "PVC-PELLETS", "PVC Pellets", "material", None, "kg", 0),
                ("ITEM-BLACK-DYE", "BLACK-DYE", "Black Dye", "material", None, "ml", 0),
                ("ITEM-YELLOW-DYE", "YELLOW-DYE", "Yellow Dye", "material", None, "ml", 0),
                ("ITEM-BOX-SMALL", "BOX-SMALL", "Small Box", "material", None, "ea", 0),
            ],
        )

        # Stock
        conn.executemany(
            "INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)",
            [
                ("STK-0001", "ITEM-ELVIS-20", "WH-LYON", "FG/BIN-12", 12),
                ("STK-0002", "ITEM-MARILYN-20", "WH-LYON", "FG/BIN-14", 12),
                ("STK-0003", "ITEM-CLASSIC-10", "WH-LYON", "FG/BIN-02", 100),
                ("STK-0004", "ITEM-PVC", "WH-LYON", "RM/BULK-01", 1000),
                ("STK-0005", "ITEM-BLACK-DYE", "WH-LYON", "RM/SHELF-01", 50),
                ("STK-0006", "ITEM-YELLOW-DYE", "WH-LYON", "RM/SHELF-02", 50),
                ("STK-0007", "ITEM-BOX-SMALL", "WH-LYON", "PK/BIN-01", 200),
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

        # Suppliers
        conn.executemany(
            "INSERT INTO suppliers (id, name, contact_email, lead_time_days) VALUES (?, ?, ?, ?)",
            [
                ("SUP-001", "PlasticCorp", "orders@plasticcorp.example", 10),
                ("SUP-002", "ColorMaster Dyes", "sales@colormaster.example", 7),
                ("SUP-003", "PackagingPlus", "contact@packagingplus.example", 5),
            ],
        )

        # Recipes - Elvis Duck (complex character duck)
        conn.execute(
            "INSERT INTO recipes (id, output_item_id, output_qty, output_uom, production_time_hours, notes) VALUES (?, ?, ?, ?, ?, ?)",
            ("RCP-ELVIS-20", "ITEM-ELVIS-20", 12, "ea", 3.5, "Elvis Duck 20cm - signature black hair and white jumpsuit details"),
        )
        conn.executemany(
            "INSERT INTO recipe_ingredients (id, recipe_id, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?)",
            [
                ("ING-ELVIS-1", "RCP-ELVIS-20", "ITEM-PVC", 2.4, "kg"),
                ("ING-ELVIS-2", "RCP-ELVIS-20", "ITEM-BLACK-DYE", 180, "ml"),
                ("ING-ELVIS-3", "RCP-ELVIS-20", "ITEM-YELLOW-DYE", 50, "ml"),
                ("ING-ELVIS-4", "RCP-ELVIS-20", "ITEM-BOX-SMALL", 1, "ea"),
            ],
        )
        conn.executemany(
            "INSERT INTO recipe_operations (id, recipe_id, sequence_order, operation_name, duration_hours) VALUES (?, ?, ?, ?, ?)",
            [
                ("OP-ELVIS-1", "RCP-ELVIS-20", 1, "Mold injection", 1.5),
                ("OP-ELVIS-2", "RCP-ELVIS-20", 2, "Cooling", 0.5),
                ("OP-ELVIS-3", "RCP-ELVIS-20", 3, "Paint hair black", 0.75),
                ("OP-ELVIS-4", "RCP-ELVIS-20", 4, "Paint details yellow", 0.5),
                ("OP-ELVIS-5", "RCP-ELVIS-20", 5, "Pack into box", 0.25),
            ],
        )

        # Recipes - Classic Duck (simple high-volume duck)
        conn.execute(
            "INSERT INTO recipes (id, output_item_id, output_qty, output_uom, production_time_hours, notes) VALUES (?, ?, ?, ?, ?, ?)",
            ("RCP-CLASSIC-10", "ITEM-CLASSIC-10", 24, "ea", 2.5, "Classic yellow duck - high volume simple design"),
        )
        conn.executemany(
            "INSERT INTO recipe_ingredients (id, recipe_id, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?)",
            [
                ("ING-CLASSIC-1", "RCP-CLASSIC-10", "ITEM-PVC", 1.2, "kg"),
                ("ING-CLASSIC-2", "RCP-CLASSIC-10", "ITEM-YELLOW-DYE", 150, "ml"),
                ("ING-CLASSIC-3", "RCP-CLASSIC-10", "ITEM-BOX-SMALL", 2, "ea"),
            ],
        )
        conn.executemany(
            "INSERT INTO recipe_operations (id, recipe_id, sequence_order, operation_name, duration_hours) VALUES (?, ?, ?, ?, ?)",
            [
                ("OP-CLASSIC-1", "RCP-CLASSIC-10", 1, "Mold injection", 1.0),
                ("OP-CLASSIC-2", "RCP-CLASSIC-10", 2, "Paint yellow", 0.75),
                ("OP-CLASSIC-3", "RCP-CLASSIC-10", 3, "Quality check", 0.5),
                ("OP-CLASSIC-4", "RCP-CLASSIC-10", 4, "Pack into boxes", 0.25),
            ],
        )

        # Recipes - Robot Duck (most complex)
        conn.execute(
            "INSERT INTO recipes (id, output_item_id, output_qty, output_uom, production_time_hours, notes) VALUES (?, ?, ?, ?, ?, ?)",
            ("RCP-ROBOT-25", "ITEM-ROBOT-25", 8, "ea", 6.5, "Robot Duck - metallic finish, most complex design"),
        )
        conn.executemany(
            "INSERT INTO recipe_ingredients (id, recipe_id, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?)",
            [
                ("ING-ROBOT-1", "RCP-ROBOT-25", "ITEM-PVC", 3.2, "kg"),
                ("ING-ROBOT-2", "RCP-ROBOT-25", "ITEM-BLACK-DYE", 200, "ml"),
                ("ING-ROBOT-3", "RCP-ROBOT-25", "ITEM-YELLOW-DYE", 80, "ml"),
                ("ING-ROBOT-4", "RCP-ROBOT-25", "ITEM-BOX-SMALL", 1, "ea"),
            ],
        )
        conn.executemany(
            "INSERT INTO recipe_operations (id, recipe_id, sequence_order, operation_name, duration_hours) VALUES (?, ?, ?, ?, ?)",
            [
                ("OP-ROBOT-1", "RCP-ROBOT-25", 1, "Mold injection", 2.0),
                ("OP-ROBOT-2", "RCP-ROBOT-25", 2, "Curing process", 1.0),
                ("OP-ROBOT-3", "RCP-ROBOT-25", 3, "Base coat", 1.5),
                ("OP-ROBOT-4", "RCP-ROBOT-25", 4, "Paint robot details", 1.0),
                ("OP-ROBOT-5", "RCP-ROBOT-25", 5, "Assemble parts", 0.5),
                ("OP-ROBOT-6", "RCP-ROBOT-25", 6, "Quality check", 0.25),
                ("OP-ROBOT-7", "RCP-ROBOT-25", 7, "Pack into box", 0.25),
            ],
        )

        # Recipes - Pirate Duck
        conn.execute(
            "INSERT INTO recipes (id, output_item_id, output_qty, output_uom, production_time_hours, notes) VALUES (?, ?, ?, ?, ?, ?)",
            ("RCP-PIRATE-15", "ITEM-PIRATE-15", 12, "ea", 4.0, "Pirate Duck with eye patch and hat"),
        )
        conn.executemany(
            "INSERT INTO recipe_ingredients (id, recipe_id, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?)",
            [
                ("ING-PIRATE-1", "RCP-PIRATE-15", "ITEM-PVC", 1.8, "kg"),
                ("ING-PIRATE-2", "RCP-PIRATE-15", "ITEM-BLACK-DYE", 150, "ml"),
                ("ING-PIRATE-3", "RCP-PIRATE-15", "ITEM-YELLOW-DYE", 60, "ml"),
                ("ING-PIRATE-4", "RCP-PIRATE-15", "ITEM-BOX-SMALL", 1, "ea"),
            ],
        )
        conn.executemany(
            "INSERT INTO recipe_operations (id, recipe_id, sequence_order, operation_name, duration_hours) VALUES (?, ?, ?, ?, ?)",
            [
                ("OP-PIRATE-1", "RCP-PIRATE-15", 1, "Mold injection", 1.5),
                ("OP-PIRATE-2", "RCP-PIRATE-15", 2, "Cooling", 0.5),
                ("OP-PIRATE-3", "RCP-PIRATE-15", 3, "Paint base yellow", 0.75),
                ("OP-PIRATE-4", "RCP-PIRATE-15", 4, "Paint pirate details", 0.75),
                ("OP-PIRATE-5", "RCP-PIRATE-15", 5, "Quality check", 0.25),
                ("OP-PIRATE-6", "RCP-PIRATE-15", 6, "Pack into box", 0.25),
            ],
        )

        # Recipes - Ninja Duck
        conn.execute(
            "INSERT INTO recipes (id, output_item_id, output_qty, output_uom, production_time_hours, notes) VALUES (?, ?, ?, ?, ?, ?)",
            ("RCP-NINJA-12", "ITEM-NINJA-12", 12, "ea", 3.75, "Ninja Duck with mask and ninja outfit"),
        )
        conn.executemany(
            "INSERT INTO recipe_ingredients (id, recipe_id, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?)",
            [
                ("ING-NINJA-1", "RCP-NINJA-12", "ITEM-PVC", 1.4, "kg"),
                ("ING-NINJA-2", "RCP-NINJA-12", "ITEM-BLACK-DYE", 160, "ml"),
                ("ING-NINJA-3", "RCP-NINJA-12", "ITEM-YELLOW-DYE", 40, "ml"),
                ("ING-NINJA-4", "RCP-NINJA-12", "ITEM-BOX-SMALL", 1, "ea"),
            ],
        )
        conn.executemany(
            "INSERT INTO recipe_operations (id, recipe_id, sequence_order, operation_name, duration_hours) VALUES (?, ?, ?, ?, ?)",
            [
                ("OP-NINJA-1", "RCP-NINJA-12", 1, "Mold injection", 1.25),
                ("OP-NINJA-2", "RCP-NINJA-12", 2, "Cooling", 0.5),
                ("OP-NINJA-3", "RCP-NINJA-12", 3, "Paint ninja outfit", 1.0),
                ("OP-NINJA-4", "RCP-NINJA-12", 4, "Quality check", 0.75),
                ("OP-NINJA-5", "RCP-NINJA-12", 5, "Pack into box", 0.25),
            ],
        )

        # Recipes - Unicorn Duck
        conn.execute(
            "INSERT INTO recipes (id, output_item_id, output_qty, output_uom, production_time_hours, notes) VALUES (?, ?, ?, ?, ?, ?)",
            ("RCP-UNICORN-25", "ITEM-UNICORN-25", 10, "ea", 5.0, "Unicorn Duck with horn and rainbow colors"),
        )
        conn.executemany(
            "INSERT INTO recipe_ingredients (id, recipe_id, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?)",
            [
                ("ING-UNICORN-1", "RCP-UNICORN-25", "ITEM-PVC", 2.5, "kg"),
                ("ING-UNICORN-2", "RCP-UNICORN-25", "ITEM-BLACK-DYE", 100, "ml"),
                ("ING-UNICORN-3", "RCP-UNICORN-25", "ITEM-YELLOW-DYE", 120, "ml"),
                ("ING-UNICORN-4", "RCP-UNICORN-25", "ITEM-BOX-SMALL", 1, "ea"),
            ],
        )
        conn.executemany(
            "INSERT INTO recipe_operations (id, recipe_id, sequence_order, operation_name, duration_hours) VALUES (?, ?, ?, ?, ?)",
            [
                ("OP-UNICORN-1", "RCP-UNICORN-25", 1, "Mold injection", 1.75),
                ("OP-UNICORN-2", "RCP-UNICORN-25", 2, "Cooling", 0.75),
                ("OP-UNICORN-3", "RCP-UNICORN-25", 3, "Paint rainbow colors", 1.5),
                ("OP-UNICORN-4", "RCP-UNICORN-25", 4, "Attach horn", 0.5),
                ("OP-UNICORN-5", "RCP-UNICORN-25", 5, "Quality check", 0.25),
                ("OP-UNICORN-6", "RCP-UNICORN-25", 6, "Pack into box", 0.25),
            ],
        )

        # Production orders (recipe-based, smaller set)
        conn.executemany(
            "INSERT INTO production_orders (id, recipe_id, item_id, qty_planned, qty_completed, current_operation, status, eta_finish, eta_ship) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("MO-555", "RCP-ELVIS-20", "ITEM-ELVIS-20", 5, 2, "Paint hair black", "in_progress", "2026-01-19", "2026-01-20"),
                ("MO-1000", "RCP-PIRATE-15", "ITEM-PIRATE-15", 10, 8, "Pack into box", "in_progress", "2026-01-03", "2026-01-04"),
                ("MO-1001", "RCP-UNICORN-25", "ITEM-UNICORN-25", 15, 2, "Paint rainbow colors", "in_progress", "2026-02-10", "2026-02-11"),
                ("MO-1002", "RCP-ROBOT-25", "ITEM-ROBOT-25", 50, 22, "Paint robot details", "in_progress", "2026-01-24", "2026-01-25"),
                ("MO-1003", "RCP-NINJA-12", "ITEM-NINJA-12", 20, 7, "Paint ninja outfit", "in_progress", "2025-12-31", "2026-01-01"),
                ("MO-1004", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", 12, 10, "Pack into boxes", "in_progress", "2026-01-05", "2026-01-06"),
                ("MO-1005", "RCP-ELVIS-20", "ITEM-ELVIS-20", 8, 8, "Pack into box", "completed", "2025-12-20", "2025-12-21"),
                ("MO-1006", "RCP-PIRATE-15", "ITEM-PIRATE-15", 6, 6, "Pack into box", "completed", "2025-12-18", "2025-12-19"),
                ("MO-1007", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", 15, 15, "Pack into boxes", "completed", "2025-12-15", "2025-12-16"),
                ("MO-1008", "RCP-ROBOT-25", "ITEM-ROBOT-25", 4, 0, None, "planned", "2026-02-08", "2026-02-09"),
                ("MO-1009", "RCP-NINJA-12", "ITEM-NINJA-12", 12, 0, None, "planned", "2026-02-15", "2026-02-16"),
                ("MO-1010", "RCP-UNICORN-25", "ITEM-UNICORN-25", 8, 0, None, "waiting", "2026-03-01", "2026-03-02"),
                ("MO-1011", "RCP-ELVIS-20", "ITEM-ELVIS-20", 10, 0, None, "ready", "2026-01-28", "2026-01-29"),
                ("MO-1012", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", 20, 0, None, "ready", "2026-01-15", "2026-01-16"),
            ],
        )


        conn.commit()
        print(f"Seeded demo database at {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
