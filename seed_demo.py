"""Populate demo SQLite database with the dataset described in SPECIFICATION.md."""

from pathlib import Path
import sqlite3
import os
from io import BytesIO
from PIL import Image

from db import DB_PATH, init_db


def seed(from_admin=False):
    # When called standalone, delete file and start fresh
    # When called from admin tool, tables already dropped so just init schema
    if not from_admin and DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        
        # Initialize simulation state with fixed starting time for reproducibility
        conn.execute(
            "INSERT INTO simulation_state (id, sim_time) VALUES (1, '2025-12-24 08:30:00')"
        )
        
        # Customers
        conn.executemany(
            "INSERT INTO customers (id, name, company, email, city, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("CUST-0044", "Sarah Martin", None, "sarah@martin-retail.example", "Paris", "2025-12-01 10:00:00"),
                ("CUST-0001", "Rubber Duck Works", None, "contact@rubberduck.example", "Lyon", "2025-12-02 11:30:00"),
                ("CUST-0102", "John Doe", "DuckFan Paris", "john@duckfan-paris.example", "Paris", "2025-12-05 14:20:00"),
                ("CUST-0103", "Daisy Paddlesworth", "Splash & Co", "daisy@splashco.example", "Nice", "2025-12-07 09:15:00"),
                ("CUST-0104", "Quackers McGee", None, "quackers@pond.example", "Marseille", "2025-12-08 16:45:00"),
                ("CUST-0105", "Bella Featherstone", "The Duck Emporium", "bella@duckemporium.example", "Toulouse", "2025-12-10 13:00:00"),
                ("CUST-0106", "Puddles O'Mallory", None, "puddles@mailexample.example", "Bordeaux", "2025-12-12 10:30:00"),
                ("CUST-0107", "Drake Fluffington", "Fluff & Feathers", "drake@fluffnfeathers.example", "Strasbourg", "2025-12-14 15:20:00"),
                ("CUST-0108", "Mallory Beakworth", None, "mallory@beakmail.example", "Nantes", "2025-12-15 11:00:00"),
                ("CUST-0109", "Waddles Johnson", "Waddle Inc", "waddles@waddleinc.example", "Lille", "2025-12-16 14:45:00"),
                ("CUST-0110", "Ducky McDuckface", None, "ducky@mcduckface.example", "Montpellier", "2025-12-17 09:30:00"),
                ("CUST-0111", "Splash Gordon", "Aquatic Adventures", "splash@aquatic.example", "Rennes", "2025-12-18 16:00:00"),
                ("CUST-0112", "Feather McFloaty", None, "feather@floaty.example", "Grenoble", "2025-12-19 10:15:00"),
                ("CUST-0113", "Bubbles LaRue", "Bath Time Boutique", "bubbles@bathtime.example", "Dijon", "2025-12-20 13:30:00"),
                ("CUST-0114", "Captain Quack", "Quack Squadron", "captain@quacksquadron.example", "Angers", "2025-12-21 11:45:00"),
                ("CUST-0115", "Honk Singleton", None, "honk@singleton.example", "Le Havre", "2025-12-22 14:20:00"),
                ("CUST-0116", "Webby Toes", "Webfoot Wonders", "webby@webfoot.example", "Reims", "2025-12-23 09:00:00"),
            ],
        )

        # Items - prepare items with image loading
        items_data = [
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
            ("ITEM-PARROT-18", "PARROT-DUCK-18CM", "Parrot Duck 18cm", "finished_good", 16.5, "ea", 0),
            ("ITEM-PVC", "PVC-PELLETS", "PVC Pellets", "material", None, "kg", 0),
            ("ITEM-BLACK-DYE", "BLACK-DYE", "Black Dye", "material", None, "ml", 0),
            ("ITEM-YELLOW-DYE", "YELLOW-DYE", "Yellow Dye", "material", None, "ml", 0),
            ("ITEM-BOX-SMALL", "BOX-SMALL", "Small Box", "material", None, "ea", 0),
        ]
        
        # Insert items with images
        script_dir = Path(__file__).parent
        images_dir = script_dir / "images"
        
        for item_id, sku, name, item_type, unit_price, uom, reorder_qty in items_data:
            image_data = None
            image_path = images_dir / f"{sku}.png"
            if image_path.exists():
                with Image.open(image_path) as img:
                    # Resize to 256x256
                    img_resized = img.resize((256, 256), Image.Resampling.LANCZOS)
                    # Convert to PNG bytes
                    buffer = BytesIO()
                    img_resized.save(buffer, format='PNG')
                    image_data = buffer.getvalue()
            
            conn.execute(
                "INSERT INTO items (id, sku, name, type, unit_price, uom, reorder_qty, image) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, sku, name, item_type, unit_price, uom, reorder_qty, image_data)
            )

        # Stock - diverse levels for interesting bar chart
        conn.executemany(
            "INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)",
            [
                # Finished goods - varied stock levels
                ("STK-0001", "ITEM-ELVIS-20", "WH-LYON", "FG/BIN-12", 127),
                ("STK-0002", "ITEM-ELVIS-20", "WH-LYON", "FG/BIN-13", 79),  # Total: 206 (medium)
                ("STK-0003", "ITEM-MARILYN-20", "WH-LYON", "FG/BIN-14", 18),
                ("STK-0004", "ITEM-CLASSIC-10", "WH-LYON", "FG/BIN-02", 571),
                ("STK-0005", "ITEM-CLASSIC-10", "WH-LYON", "FG/BIN-03", 412),  # Total: 983 (high stock)
                ("STK-0006", "ITEM-ROBOT-25", "WH-LYON", "FG/BIN-05", 47),  # Low stock
                ("STK-0007", "ITEM-PIRATE-15", "WH-LYON", "FG/BIN-06", 94),  # Medium
                ("STK-0008", "ITEM-NINJA-12", "WH-LYON", "FG/BIN-07", 8),  # Critical low
                ("STK-0009", "ITEM-UNICORN-25", "WH-LYON", "FG/BIN-08", 53),  # Low
                
                # Raw materials
                ("STK-0010", "ITEM-PVC", "WH-LYON", "RM/BULK-01", 987),
                ("STK-0011", "ITEM-BLACK-DYE", "WH-LYON", "RM/SHELF-01", 43),
                ("STK-0012", "ITEM-YELLOW-DYE", "WH-LYON", "RM/SHELF-02", 56),
                ("STK-0013", "ITEM-BOX-SMALL", "WH-LYON", "PK/BIN-01", 218),
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
            # Completed orders (37 total) - dates span Nov 15 - Dec 23 for trend analysis
            # Mid-November (ramping up)
            ("MO-1101", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "completed", "2025-11-15T09:00", "2025-11-15T11:30", "2025-11-16", "2025-11-17"),
            ("MO-1102", "RCP-ELVIS-20", "ITEM-ELVIS-20", "completed", "2025-11-17T10:00", "2025-11-17T13:30", "2025-11-18", "2025-11-19"),
            ("MO-1103", "RCP-NINJA-12", "ITEM-NINJA-12", "completed", "2025-11-19T08:00", "2025-11-19T10:30", "2025-11-20", "2025-11-21"),
            ("MO-1104", "RCP-PIRATE-15", "ITEM-PIRATE-15", "completed", "2025-11-21T09:00", "2025-11-21T15:00", "2025-11-22", "2025-11-23"),
            ("MO-1105", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "completed", "2025-11-22T14:00", "2025-11-22T16:30", "2025-11-23", "2025-11-24"),
            ("MO-1106", "RCP-ROBOT-25", "ITEM-ROBOT-25", "completed", "2025-11-25T08:00", "2025-11-25T14:30", "2025-11-26", "2025-11-27"),
            ("MO-1107", "RCP-ELVIS-20", "ITEM-ELVIS-20", "completed", "2025-11-26T10:00", "2025-11-26T13:30", "2025-11-27", "2025-11-28"),
            ("MO-1108", "RCP-UNICORN-25", "ITEM-UNICORN-25", "completed", "2025-11-28T09:00", "2025-11-28T15:00", "2025-11-29", "2025-11-30"),
            
            # Early December (steady pace)
            ("MO-1109", "RCP-NINJA-12", "ITEM-NINJA-12", "completed", "2025-12-01T08:00", "2025-12-01T10:30", "2025-12-02", "2025-12-03"),
            ("MO-1110", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "completed", "2025-12-02T10:00", "2025-12-02T12:30", "2025-12-03", "2025-12-04"),
            ("MO-1111", "RCP-PIRATE-15", "ITEM-PIRATE-15", "completed", "2025-12-03T09:00", "2025-12-03T15:00", "2025-12-04", "2025-12-05"),
            ("MO-1112", "RCP-ELVIS-20", "ITEM-ELVIS-20", "completed", "2025-12-04T13:00", "2025-12-04T16:30", "2025-12-05", "2025-12-06"),
            ("MO-1011", "RCP-ELVIS-20", "ITEM-ELVIS-20", "completed", "2025-12-05T10:00", "2025-12-05T13:30", "2025-12-06", "2025-12-07"),
            ("MO-1113", "RCP-ROBOT-25", "ITEM-ROBOT-25", "completed", "2025-12-06T09:00", "2025-12-06T15:30", "2025-12-07", "2025-12-08"),
            ("MO-1010", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "completed", "2025-12-08T14:00", "2025-12-08T16:30", "2025-12-09", "2025-12-10"),
            ("MO-1017", "RCP-UNICORN-25", "ITEM-UNICORN-25", "completed", "2025-12-09T10:00", "2025-12-09T16:00", "2025-12-10", "2025-12-11"),
            
            # Mid December (increasing volume)
            ("MO-1009", "RCP-NINJA-12", "ITEM-NINJA-12", "completed", "2025-12-10T09:00", "2025-12-10T11:30", "2025-12-11", "2025-12-12"),
            ("MO-1015", "RCP-NINJA-12", "ITEM-NINJA-12", "completed", "2025-12-11T08:00", "2025-12-11T10:30", "2025-12-12", "2025-12-13"),
            ("MO-1012", "RCP-PIRATE-15", "ITEM-PIRATE-15", "completed", "2025-12-12T08:00", "2025-12-12T14:00", "2025-12-13", "2025-12-14"),
            ("MO-1114", "RCP-ELVIS-20", "ITEM-ELVIS-20", "completed", "2025-12-13T10:00", "2025-12-13T13:30", "2025-12-14", "2025-12-15"),
            ("MO-1003", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "completed", "2025-12-14T10:00", "2025-12-14T12:30", "2025-12-15", "2025-12-16"),
            ("MO-1013", "RCP-ROBOT-25", "ITEM-ROBOT-25", "completed", "2025-12-15T09:00", "2025-12-15T15:30", "2025-12-16", "2025-12-17"),
            ("MO-1115", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "completed", "2025-12-16T08:00", "2025-12-16T10:30", "2025-12-17", "2025-12-18"),
            ("MO-1006", "RCP-PIRATE-15", "ITEM-PIRATE-15", "completed", "2025-12-17T08:00", "2025-12-17T14:00", "2025-12-18", "2025-12-19"),
            ("MO-1016", "RCP-ELVIS-20", "ITEM-ELVIS-20", "completed", "2025-12-18T13:00", "2025-12-18T16:30", "2025-12-19", "2025-12-20"),
            ("MO-1001", "RCP-ELVIS-20", "ITEM-ELVIS-20", "completed", "2025-12-19T08:00", "2025-12-19T11:30", "2025-12-20", "2025-12-21"),
            ("MO-1116", "RCP-NINJA-12", "ITEM-NINJA-12", "completed", "2025-12-19T14:00", "2025-12-19T16:30", "2025-12-20", "2025-12-21"),
            ("MO-1014", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "completed", "2025-12-20T11:00", "2025-12-20T13:30", "2025-12-21", "2025-12-22"),
            ("MO-1117", "RCP-ROBOT-25", "ITEM-ROBOT-25", "completed", "2025-12-21T09:00", "2025-12-21T15:30", "2025-12-22", "2025-12-23"),
            ("MO-1118", "RCP-PIRATE-15", "ITEM-PIRATE-15", "completed", "2025-12-22T08:00", "2025-12-22T14:00", "2025-12-23", "2025-12-24"),
            ("MO-1119", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "completed", "2025-12-22T14:00", "2025-12-22T16:30", "2025-12-23", "2025-12-24"),
            ("MO-1120", "RCP-UNICORN-25", "ITEM-UNICORN-25", "completed", "2025-12-23T09:00", "2025-12-23T15:00", "2025-12-24", "2025-12-25"),
            ("MO-1121", "RCP-ELVIS-20", "ITEM-ELVIS-20", "completed", "2025-12-23T13:00", "2025-12-23T16:30", "2025-12-24", "2025-12-25"),
            ("MO-1122", "RCP-NINJA-12", "ITEM-NINJA-12", "completed", "2025-12-23T10:00", "2025-12-23T12:30", "2025-12-24", "2025-12-25"),
            ("MO-1123", "RCP-ROBOT-25", "ITEM-ROBOT-25", "completed", "2025-12-23T15:00", "2025-12-23T21:30", "2025-12-24", "2025-12-25"),
            ("MO-1124", "RCP-PIRATE-15", "ITEM-PIRATE-15", "completed", "2025-12-23T09:00", "2025-12-23T15:00", "2025-12-24", "2025-12-25"),
            
            # In progress orders (5 total - ~17%)
            ("MO-1002", "RCP-ELVIS-20", "ITEM-ELVIS-20", "in_progress", "2025-12-24T09:00", None, "2025-12-25", "2025-12-26"),
            ("MO-1005", "RCP-ROBOT-25", "ITEM-ROBOT-25", "in_progress", "2025-12-23T14:00", None, "2025-12-29", "2025-12-30"),
            ("MO-1018", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "in_progress", "2025-12-24T08:00", None, "2025-12-25", "2025-12-26"),
            ("MO-1019", "RCP-PIRATE-15", "ITEM-PIRATE-15", "in_progress", "2025-12-23T10:00", None, "2025-12-24", "2025-12-25"),
            ("MO-1020", "RCP-NINJA-12", "ITEM-NINJA-12", "in_progress", "2025-12-24T13:00", None, "2025-12-25", "2025-12-26"),
            
            # Ready orders (4 total - ~13%)
            ("MO-1004", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "ready", None, None, "2026-01-10", "2026-01-11"),
            ("MO-1021", "RCP-ELVIS-20", "ITEM-ELVIS-20", "ready", None, None, "2026-01-08", "2026-01-09"),
            ("MO-1022", "RCP-ROBOT-25", "ITEM-ROBOT-25", "ready", None, None, "2026-01-12", "2026-01-13"),
            ("MO-1023", "RCP-UNICORN-25", "ITEM-UNICORN-25", "ready", None, None, "2026-01-15", "2026-01-16"),
            
            # Waiting orders (5 total - ~17%, blocked on materials)
            ("MO-1008", "RCP-UNICORN-25", "ITEM-UNICORN-25", "waiting", None, None, "2026-02-01", "2026-02-02"),
            ("MO-1024", "RCP-ROBOT-25", "ITEM-ROBOT-25", "waiting", None, None, "2026-01-20", "2026-01-21"),
            ("MO-1025", "RCP-PIRATE-15", "ITEM-PIRATE-15", "waiting", None, None, "2026-01-18", "2026-01-19"),
            ("MO-1026", "RCP-UNICORN-25", "ITEM-UNICORN-25", "waiting", None, None, "2026-01-25", "2026-01-26"),
            ("MO-1027", "RCP-NINJA-12", "ITEM-NINJA-12", "waiting", None, None, "2026-01-22", "2026-01-23"),
            
            # Planned orders (7 total, future orders)
            ("MO-1007", "RCP-NINJA-12", "ITEM-NINJA-12", "planned", None, None, "2026-01-05", "2026-01-06"),
            ("MO-1028", "RCP-ELVIS-20", "ITEM-ELVIS-20", "planned", None, None, "2026-02-10", "2026-02-11"),
            ("MO-1029", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "planned", None, None, "2026-02-15", "2026-02-16"),
            ("MO-1030", "RCP-ROBOT-25", "ITEM-ROBOT-25", "planned", None, None, "2026-02-20", "2026-02-21"),
            ("MO-1031", "RCP-PIRATE-15", "ITEM-PIRATE-15", "planned", None, None, "2026-02-25", "2026-02-26"),
            ("MO-1032", "RCP-UNICORN-25", "ITEM-UNICORN-25", "planned", None, None, "2026-03-01", "2026-03-02"),
            ("MO-1033", "RCP-NINJA-12", "ITEM-NINJA-12", "ready", None, None, "2026-01-20", "2026-01-21"),
            ("MO-1034", "RCP-PIRATE-15", "ITEM-PIRATE-15", "ready", None, None, "2026-01-25", "2026-01-26"),
            ("MO-1035", "RCP-UNICORN-25", "ITEM-UNICORN-25", "in_progress", "2025-12-24T10:00", None, "2025-12-26", "2025-12-27"),
            ("MO-1036", "RCP-ELVIS-20", "ITEM-ELVIS-20", "waiting", None, None, "2026-02-05", "2026-02-06"),
            ("MO-1037", "RCP-CLASSIC-10", "ITEM-CLASSIC-10", "waiting", None, None, "2026-02-08", "2026-02-09"),
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

        # Emails
        conn.executemany(
            "INSERT INTO emails (id, customer_id, sales_order_id, recipient_email, recipient_name, subject, body, status, created_at, modified_at, sent_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("EMAIL-0001", "CUST-0044", "SO-1041", "sarah@martin-retail.example", "Sarah Martin",
                 "Order Confirmation - SO-1041",
                 "Dear Sarah,\n\nThank you for your order SO-1041. We have received your request for 12 Small Yellow Rubber Ducks (8cm).\n\nYour order is currently being processed and we will keep you updated on its progress.\n\nBest regards,\nDuck Inc Sales Team",
                 "sent", "2025-12-20 09:00:00", "2025-12-20 09:00:00", "2025-12-20 09:00:00"),
                
                ("EMAIL-0002", "CUST-0102", "SO-1042", "john@duckfan-paris.example", "John Doe",
                 "Quote for Elvis Duck Order",
                 "Dear John,\n\nThank you for your interest in our Elvis Presley Rubber Ducks (20cm).\n\nFor an order of 24 units, we can offer:\n- Unit price: €12.00\n- Volume discount (5%): -€14.40\n- Subtotal: €273.60\n- Shipping: Free (order over €300 threshold)\n- Total: €273.60\n\nEstimated delivery: January 8, 2026\n\nPlease let us know if you would like to proceed.\n\nBest regards,\nDuck Inc Sales Team",
                 "draft", "2025-12-21 14:30:00", "2025-12-22 10:15:00", None),
                
                ("EMAIL-0003", "CUST-0044", None, "sarah@martin-retail.example", "Sarah Martin",
                 "New Product Announcement - Pirate Rubber Duck",
                 "Dear Sarah,\n\nWe're excited to announce our latest addition to the Duck Inc collection: the Pirate Rubber Duck (15cm)!\n\nThis swashbuckling companion features:\n- Authentic pirate outfit with tricorn hat\n- Eye patch and bandana details\n- Premium quality vinyl construction\n- Perfect for bath time adventures\n\nSpecial launch price: €12.00 per unit\nAvailable now with immediate shipping.\n\nWould you like to add some to your next order?\n\nBest regards,\nDuck Inc Sales Team",
                 "sent", "2025-12-22 11:00:00", "2025-12-22 11:00:00", "2025-12-22 11:00:00"),
                
                ("EMAIL-0004", "CUST-0103", None, "daisy@splashco.example", "Daisy Paddlesworth",
                 "Follow-up: Your Recent Inquiry",
                 "Dear Daisy,\n\nThank you for contacting Duck Inc regarding our rubber duck collection.\n\nI wanted to follow up on your inquiry about bulk ordering options for Splash & Co. We offer attractive volume discounts for orders over 24 units:\n- 5% discount on all items\n- Free shipping on orders over €300\n- Priority production scheduling\n\nOur current bestsellers are:\n1. Elvis Presley Rubber Duck (20cm) - €12.00\n2. Small Yellow Rubber Duck (8cm) - €12.00\n3. Pirate Rubber Duck (15cm) - €12.00\n\nWould you like to schedule a call to discuss your specific needs?\n\nBest regards,\nFred Stark\nDuck Inc Sales",
                 "draft", "2025-12-23 15:45:00", "2025-12-23 16:20:00", None),
            ]
        )

        conn.commit()
        print(f"Seeded demo database at {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
