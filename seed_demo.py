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
        
        # Initialize simulation state with fixed starting time for reproducibility
        conn.execute(
            "INSERT INTO simulation_state (id, sim_time) VALUES (1, '2025-01-15 08:00:00')"
        )
        
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
            "INSERT INTO recipe_ingredients (id, recipe_id, sequence_order, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("ING-ELVIS-1", "RCP-ELVIS-20", 1, "ITEM-PVC", 2.4, "kg"),
                ("ING-ELVIS-2", "RCP-ELVIS-20", 2, "ITEM-BLACK-DYE", 180, "ml"),
                ("ING-ELVIS-3", "RCP-ELVIS-20", 3, "ITEM-YELLOW-DYE", 50, "ml"),
                ("ING-ELVIS-4", "RCP-ELVIS-20", 4, "ITEM-BOX-SMALL", 1, "ea"),
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
            "INSERT INTO recipe_ingredients (id, recipe_id, sequence_order, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("ING-CLASSIC-1", "RCP-CLASSIC-10", 1, "ITEM-PVC", 1.2, "kg"),
                ("ING-CLASSIC-2", "RCP-CLASSIC-10", 2, "ITEM-YELLOW-DYE", 150, "ml"),
                ("ING-CLASSIC-3", "RCP-CLASSIC-10", 3, "ITEM-BOX-SMALL", 2, "ea"),
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
            "INSERT INTO recipe_ingredients (id, recipe_id, sequence_order, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("ING-ROBOT-1", "RCP-ROBOT-25", 1, "ITEM-PVC", 3.2, "kg"),
                ("ING-ROBOT-2", "RCP-ROBOT-25", 2, "ITEM-BLACK-DYE", 200, "ml"),
                ("ING-ROBOT-3", "RCP-ROBOT-25", 3, "ITEM-YELLOW-DYE", 80, "ml"),
                ("ING-ROBOT-4", "RCP-ROBOT-25", 4, "ITEM-BOX-SMALL", 1, "ea"),
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
            "INSERT INTO recipe_ingredients (id, recipe_id, sequence_order, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("ING-PIRATE-1", "RCP-PIRATE-15", 1, "ITEM-PVC", 1.8, "kg"),
                ("ING-PIRATE-2", "RCP-PIRATE-15", 2, "ITEM-BLACK-DYE", 150, "ml"),
                ("ING-PIRATE-3", "RCP-PIRATE-15", 3, "ITEM-YELLOW-DYE", 60, "ml"),
                ("ING-PIRATE-4", "RCP-PIRATE-15", 4, "ITEM-BOX-SMALL", 1, "ea"),
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
            "INSERT INTO recipe_ingredients (id, recipe_id, sequence_order, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("ING-NINJA-1", "RCP-NINJA-12", 1, "ITEM-PVC", 1.4, "kg"),
                ("ING-NINJA-2", "RCP-NINJA-12", 2, "ITEM-BLACK-DYE", 160, "ml"),
                ("ING-NINJA-3", "RCP-NINJA-12", 3, "ITEM-YELLOW-DYE", 40, "ml"),
                ("ING-NINJA-4", "RCP-NINJA-12", 4, "ITEM-BOX-SMALL", 1, "ea"),
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
            "INSERT INTO recipe_ingredients (id, recipe_id, sequence_order, input_item_id, input_qty, input_uom) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("ING-UNICORN-1", "RCP-UNICORN-25", 1, "ITEM-PVC", 2.5, "kg"),
                ("ING-UNICORN-2", "RCP-UNICORN-25", 2, "ITEM-BLACK-DYE", 100, "ml"),
                ("ING-UNICORN-3", "RCP-UNICORN-25", 3, "ITEM-YELLOW-DYE", 120, "ml"),
                ("ING-UNICORN-4", "RCP-UNICORN-25", 4, "ITEM-BOX-SMALL", 1, "ea"),
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

        # Purchase orders for materials
        conn.executemany(
            "INSERT INTO purchase_orders (id, item_id, qty, supplier_id, status, ordered_at, expected_delivery, received_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("PO-1001", "ITEM-PVC", 500, "SUP-001", "received", "2025-12-01", "2025-12-08", "2025-12-07"),
                ("PO-1002", "ITEM-BLACK-DYE", 50, "SUP-002", "received", "2025-12-01", "2025-12-06", "2025-12-06"),
                ("PO-1003", "ITEM-YELLOW-DYE", 30, "SUP-002", "received", "2025-12-01", "2025-12-06", "2025-12-06"),
                ("PO-1004", "ITEM-BLACK-DYE", 25, "SUP-002", "received", "2025-12-05", "2025-12-10", "2025-12-10"),
                ("PO-1005", "ITEM-BOX-SMALL", 1000, "SUP-003", "received", "2025-12-10", "2025-12-17", "2025-12-16"),
                ("PO-1006", "ITEM-PVC", 750, "SUP-001", "ordered", "2025-12-20", "2025-12-27", None),
                ("PO-1007", "ITEM-YELLOW-DYE", 40, "SUP-002", "ordered", "2025-12-22", "2025-12-29", None),
                ("PO-1008", "ITEM-BLACK-DYE", 60, "SUP-002", "ordered", "2025-12-23", "2025-12-30", None),
                ("PO-1009", "ITEM-BOX-SMALL", 1500, "SUP-003", "ordered", "2025-12-24", "2026-01-02", None),
            ],
        )

# Production orders (one per batch) with their operations
        production_orders = [
            ("MO-1001", "RCP-ELVIS-20", "ITEM-ELVIS-20", "completed", "2025-12-19T08:00", "2025-12-19T11:30", "2025-12-20", "2025-12-21"),
            ("MO-1002", "RCP-ELVIS-20", "ITEM-ELVIS-20", "in_progress", "2025-12-24T09:00", None, "2025-12-25", "2025-12-26"),
            ("MO-1003", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "completed", "2025-12-14T10:00", "2025-12-14T12:30", "2025-12-15", "2025-12-16"),
            ("MO-1004", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "ready", None, None, "2026-01-10", "2026-01-11"),
            ("MO-1005", "RCP-ROBOT-25", "ITEM-ROBOT-25", "in_progress", "2025-12-23T14:00", None, "2025-12-29", "2025-12-30"),
            ("MO-1006", "RCP-PIRATE-15", "ITEM-PIRATE-15", "completed", "2025-12-17T08:00", "2025-12-17T14:00", "2025-12-18", "2025-12-19"),
            ("MO-1007", "RCP-NINJA-12", "ITEM-NINJA-12", "planned", None, None, "2026-01-05", "2026-01-06"),
            ("MO-1008", "RCP-UNICORN-25", "ITEM-UNICORN-25", "waiting", None, None, "2026-02-01", "2026-02-02"),
        ]
        conn.executemany(
            "INSERT INTO production_orders (id, recipe_id, item_id, status, started_at, completed_at, eta_finish, eta_ship) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            production_orders
        )
        
        # Production operations for each order
        # MO-1001 (Elvis, completed)
        conn.executemany(
            "INSERT INTO production_operations (id, production_order_id, recipe_operation_id, sequence_order, operation_name, duration_hours, status, started_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("POP-1001-1", "MO-1001", "OP-ELVIS-1", 1, "Mold duck shape", 1.5, "completed", "2025-12-19T08:00", "2025-12-19T09:30"),
                ("POP-1001-2", "MO-1001", "OP-ELVIS-2", 2, "Cooling", 0.5, "completed", "2025-12-19T09:30", "2025-12-19T10:00"),
                ("POP-1001-3", "MO-1001", "OP-ELVIS-3", 3, "Paint hair black", 0.75, "completed", "2025-12-19T10:00", "2025-12-19T10:45"),
                ("POP-1001-4", "MO-1001", "OP-ELVIS-4", 4, "Paint details", 0.5, "completed", "2025-12-19T10:45", "2025-12-19T11:15"),
                ("POP-1001-5", "MO-1001", "OP-ELVIS-5", 5, "Pack into box", 0.25, "completed", "2025-12-19T11:15", "2025-12-19T11:30"),
                # MO-1002 (Elvis, in progress on operation 3)
                ("POP-1002-1", "MO-1002", "OP-ELVIS-1", 1, "Mold duck shape", 1.5, "completed", "2025-12-24T09:00", "2025-12-24T10:30"),
                ("POP-1002-2", "MO-1002", "OP-ELVIS-2", 2, "Cooling", 0.5, "completed", "2025-12-24T10:30", "2025-12-24T11:00"),
                ("POP-1002-3", "MO-1002", "OP-ELVIS-3", 3, "Paint hair black", 0.75, "in_progress", "2025-12-24T11:00", None),
                ("POP-1002-4", "MO-1002", "OP-ELVIS-4", 4, "Paint details", 0.5, "pending", None, None),
                ("POP-1002-5", "MO-1002", "OP-ELVIS-5", 5, "Pack into box", 0.25, "pending", None, None),
                # MO-1003 (Classic, completed)
                ("POP-1003-1", "MO-1003", "OP-CLASSIC-1", 1, "Mold classic shape", 1.0, "completed", "2025-12-14T10:00", "2025-12-14T11:00"),
                ("POP-1003-2", "MO-1003", "OP-CLASSIC-2", 2, "Cooling", 0.5, "completed", "2025-12-14T11:00", "2025-12-14T11:30"),
                ("POP-1003-3", "MO-1003", "OP-CLASSIC-3", 3, "Paint yellow", 0.5, "completed", "2025-12-14T11:30", "2025-12-14T12:00"),
                ("POP-1003-4", "MO-1003", "OP-CLASSIC-4", 4, "Pack into boxes", 0.5, "completed", "2025-12-14T12:00", "2025-12-14T12:30"),
                # MO-1005 (Robot, in progress on operation 4)
                ("POP-1005-1", "MO-1005", "OP-ROBOT-1", 1, "Mold robot shape", 2.5, "completed", "2025-12-23T14:00", "2025-12-23T16:30"),
                ("POP-1005-2", "MO-1005", "OP-ROBOT-2", 2, "Cooling", 1.0, "completed", "2025-12-23T16:30", "2025-12-23T17:30"),
                ("POP-1005-3", "MO-1005", "OP-ROBOT-3", 3, "Paint silver base", 1.0, "completed", "2025-12-23T17:30", "2025-12-23T18:30"),
                ("POP-1005-4", "MO-1005", "OP-ROBOT-4", 4, "Paint robot details", 1.5, "in_progress", "2025-12-24T08:00", None),
                ("POP-1005-5", "MO-1005", "OP-ROBOT-5", 5, "Quality check", 0.25, "pending", None, None),
                ("POP-1005-6", "MO-1005", "OP-ROBOT-6", 6, "Pack into box", 0.25, "pending", None, None),
                # MO-1006 (Pirate, completed)
                ("POP-1006-1", "MO-1006", "OP-PIRATE-1", 1, "Mold pirate shape", 1.5, "completed", "2025-12-17T08:00", "2025-12-17T09:30"),
                ("POP-1006-2", "MO-1006", "OP-PIRATE-2", 2, "Cooling", 0.5, "completed", "2025-12-17T09:30", "2025-12-17T10:00"),
                ("POP-1006-3", "MO-1006", "OP-PIRATE-3", 3, "Paint pirate outfit", 1.0, "completed", "2025-12-17T10:00", "2025-12-17T11:00"),
                ("POP-1006-4", "MO-1006", "OP-PIRATE-4", 4, "Paint details", 0.75, "completed", "2025-12-17T11:00", "2025-12-17T11:45"),
                ("POP-1006-5", "MO-1006", "OP-PIRATE-5", 5, "Quality check", 0.25, "completed", "2025-12-17T11:45", "2025-12-17T12:00"),
                ("POP-1006-6", "MO-1006", "OP-PIRATE-6", 6, "Pack into box", 0.25, "completed", "2025-12-17T13:45", "2025-12-17T14:00"),
            ]
        )

        conn.commit()
        print(f"Seeded demo database at {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
