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
            "INSERT INTO items (id, sku, name, type, unit_price) VALUES (?, ?, ?, ?, ?)",
            [
                ("ITEM-ELVIS-20", "ELVIS-DUCK-20CM", "Elvis Duck 20cm", "finished_good", 12.0),
                ("ITEM-MARILYN-20", "MARILYN-DUCK-20CM", "Marilyn Duck 20cm", "finished_good", 12.0),
                ("ITEM-CLASSIC-10", "CLASSIC-DUCK-10CM", "Classic Duck 10cm", "finished_good", 10.0),
                ("ITEM-PIRATE-15", "PIRATE-DUCK-15CM", "Pirate Duck 15cm", "finished_good", 14.5),
                ("ITEM-NINJA-12", "NINJA-DUCK-12CM", "Ninja Duck 12cm", "finished_good", 13.0),
                ("ITEM-UNICORN-25", "UNICORN-DUCK-25CM", "Unicorn Duck 25cm", "finished_good", 18.0),
                ("ITEM-DISCO-18", "DISCO-DUCK-18CM", "Disco Duck 18cm", "finished_good", 15.5),
                ("ITEM-WIZARD-20", "WIZARD-DUCK-20CM", "Wizard Duck 20cm", "finished_good", 16.0),
                ("ITEM-ASTRONAUT-22", "ASTRONAUT-DUCK-22CM", "Astronaut Duck 22cm", "finished_good", 19.0),
                ("ITEM-SUPERHERO-20", "SUPERHERO-DUCK-20CM", "Superhero Duck 20cm", "finished_good", 17.5),
                ("ITEM-ZOMBIE-15", "ZOMBIE-DUCK-15CM", "Zombie Duck 15cm", "finished_good", 11.5),
                ("ITEM-VIKING-18", "VIKING-DUCK-18CM", "Viking Duck 18cm", "finished_good", 16.5),
                ("ITEM-MERMAID-20", "MERMAID-DUCK-20CM", "Mermaid Duck 20cm", "finished_good", 14.0),
                ("ITEM-ROBOT-25", "ROBOT-DUCK-25CM", "Robot Duck 25cm", "finished_good", 22.0),
                ("ITEM-CHEF-15", "CHEF-DUCK-15CM", "Chef Duck 15cm", "finished_good", 13.5),
                ("ITEM-ROCKSTAR-20", "ROCKSTAR-DUCK-20CM", "Rockstar Duck 20cm", "finished_good", 15.0),
                ("ITEM-DETECTIVE-18", "DETECTIVE-DUCK-18CM", "Detective Duck 18cm", "finished_good", 14.5),
                ("ITEM-SURFER-15", "SURFER-DUCK-15CM", "Surfer Duck 15cm", "finished_good", 12.5),
                ("ITEM-COWBOY-20", "COWBOY-DUCK-20CM", "Cowboy Duck 20cm", "finished_good", 16.0),
                ("ITEM-BALLERINA-12", "BALLERINA-DUCK-12CM", "Ballerina Duck 12cm", "finished_good", 11.0),
                ("ITEM-GARDEN-GNOME-30", "GNOME-DUCK-30CM", "Garden Gnome Duck 30cm", "finished_good", 25.0),
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

        # Production orders (include one aligned to SO-1037 so production_get_production_order_status works for that id)
        conn.executemany(
            "INSERT INTO production_orders (id, item_id, qty_planned, qty_completed, current_operation, eta_finish, eta_ship) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("MO-555", "ITEM-ELVIS-20", 50, 20, "Paint Elvis Hair", "2026-01-19", "2026-01-20"),
                ("SO-1037", "ITEM-ELVIS-20", 50, 10, "Assemble and inspect", "2025-12-21", "2025-12-22"),
                ("MO-1000", "ITEM-PIRATE-15", 287, 98, "Curing process", "2026-01-03", "2026-01-04"),
                ("MO-1001", "ITEM-UNICORN-25", 156, 23, "Paint details", "2026-02-10", "2026-02-11"),
                ("MO-1002", "ITEM-ROBOT-25", 392, 174, "Mold injection", "2026-01-24", "2026-01-25"),
                ("MO-1003", "ITEM-NINJA-12", 245, 81, "Quality check", "2025-12-31", "2026-01-01"),
                ("MO-1004", "ITEM-DISCO-18", 178, 67, "Add accessories", "2026-02-24", "2026-02-25"),
                ("MO-1005", "ITEM-WIZARD-20", 321, 159, "Final coating", "2026-01-18", "2026-01-19"),
                ("MO-1006", "ITEM-ASTRONAUT-22", 89, 12, "Packaging prep", "2026-03-08", "2026-03-09"),
                ("MO-1007", "ITEM-SUPERHERO-20", 267, 122, "Assemble and inspect", "2026-02-03", "2026-02-04"),
                ("MO-1008", "ITEM-ZOMBIE-15", 143, 44, "Paint details", "2025-12-29", "2025-12-30"),
                ("MO-1009", "ITEM-VIKING-18", 398, 187, "Curing process", "2026-01-11", "2026-01-12"),
                ("MO-1010", "ITEM-MERMAID-20", 52, 8, "Mold injection", "2026-02-19", "2026-02-20"),
                ("MO-1011", "ITEM-CHEF-15", 215, 96, "Quality check", "2026-01-06", "2026-01-07"),
                ("MO-1012", "ITEM-ROCKSTAR-20", 334, 155, "Add accessories", "2026-03-02", "2026-03-03"),
                ("MO-1013", "ITEM-DETECTIVE-18", 127, 31, "Final coating", "2026-02-15", "2026-02-16"),
                ("MO-1014", "ITEM-SURFER-15", 276, 118, "Packaging prep", "2025-12-28", "2025-12-29"),
                ("MO-1015", "ITEM-COWBOY-20", 189, 72, "Assemble and inspect", "2026-01-22", "2026-01-23"),
                ("MO-1016", "ITEM-BALLERINA-12", 94, 19, "Paint details", "2026-03-11", "2026-03-12"),
                ("MO-1017", "ITEM-GARDEN-GNOME-30", 362, 176, "Curing process", "2026-02-07", "2026-02-08"),
                ("MO-1018", "ITEM-PIRATE-15", 118, 47, "Mold injection", "2026-01-15", "2026-01-16"),
                ("MO-1019", "ITEM-NINJA-12", 254, 101, "Quality check", "2026-02-28", "2026-03-01"),
                ("MO-1020", "ITEM-UNICORN-25", 387, 194, "Add accessories", "2026-01-04", "2026-01-05"),
                ("MO-1021", "ITEM-DISCO-18", 73, 14, "Final coating", "2026-03-13", "2026-03-14"),
                ("MO-1022", "ITEM-WIZARD-20", 201, 89, "Packaging prep", "2026-02-12", "2026-02-13"),
                ("MO-1023", "ITEM-ASTRONAUT-22", 345, 161, "Assemble and inspect", "2026-01-29", "2026-01-30"),
                ("MO-1024", "ITEM-SUPERHERO-20", 166, 56, "Paint details", "2025-12-26", "2025-12-27"),
                ("MO-1025", "ITEM-ZOMBIE-15", 298, 137, "Curing process", "2026-02-21", "2026-02-22"),
                ("MO-1026", "ITEM-VIKING-18", 42, 5, "Mold injection", "2026-01-09", "2026-01-10"),
                ("MO-1027", "ITEM-MERMAID-20", 223, 98, "Quality check", "2026-03-06", "2026-03-07"),
                ("MO-1028", "ITEM-ROBOT-25", 379, 183, "Add accessories", "2026-02-17", "2026-02-18"),
                ("MO-1029", "ITEM-CHEF-15", 135, 41, "Final coating", "2026-01-02", "2026-01-03"),
                ("MO-1030", "ITEM-ROCKSTAR-20", 267, 125, "Packaging prep", "2026-02-26", "2026-02-27"),
                ("MO-1031", "ITEM-DETECTIVE-18", 88, 18, "Assemble and inspect", "2026-01-20", "2026-01-21"),
                ("MO-1032", "ITEM-SURFER-15", 312, 148, "Paint details", "2026-03-09", "2026-03-10"),
                ("MO-1033", "ITEM-COWBOY-20", 174, 64, "Curing process", "2026-02-04", "2026-02-05"),
                ("MO-1034", "ITEM-BALLERINA-12", 401, 197, "Mold injection", "2025-12-30", "2025-12-31"),
                ("MO-1035", "ITEM-GARDEN-GNOME-30", 59, 9, "Quality check", "2026-01-27", "2026-01-28"),
                ("MO-1036", "ITEM-PIRATE-15", 238, 108, "Add accessories", "2026-03-04", "2026-03-05"),
                ("MO-1037", "ITEM-NINJA-12", 156, 52, "Final coating", "2026-02-14", "2026-02-15"),
                ("MO-1038", "ITEM-UNICORN-25", 323, 159, "Packaging prep", "2026-01-07", "2026-01-08"),
                ("MO-1039", "ITEM-DISCO-18", 97, 22, "Assemble and inspect", "2026-02-23", "2026-02-24"),
                ("MO-1040", "ITEM-WIZARD-20", 285, 131, "Paint details", "2026-01-13", "2026-01-14"),
                ("MO-1041", "ITEM-ASTRONAUT-22", 368, 179, "Curing process", "2026-03-01", "2026-03-02"),
                ("MO-1042", "ITEM-SUPERHERO-20", 121, 38, "Mold injection", "2026-02-09", "2026-02-10"),
                ("MO-1043", "ITEM-ZOMBIE-15", 247, 117, "Quality check", "2025-12-27", "2025-12-28"),
                ("MO-1044", "ITEM-VIKING-18", 392, 188, "Add accessories", "2026-01-25", "2026-01-26"),
                ("MO-1045", "ITEM-MERMAID-20", 64, 11, "Final coating", "2026-03-12", "2026-03-13"),
                ("MO-1046", "ITEM-ROBOT-25", 209, 93, "Packaging prep", "2026-02-06", "2026-02-07"),
                ("MO-1047", "ITEM-CHEF-15", 351, 167, "Assemble and inspect", "2026-01-18", "2026-01-19"),
                ("MO-1048", "ITEM-ROCKSTAR-20", 133, 44, "Paint details", "2026-02-27", "2026-02-28"),
                ("MO-1049", "ITEM-DETECTIVE-18", 276, 128, "Curing process", "2026-01-11", "2026-01-12"),
                ("MO-1050", "ITEM-SURFER-15", 45, 6, "Mold injection", "2026-03-07", "2026-03-08"),
                ("MO-1051", "ITEM-COWBOY-20", 198, 86, "Quality check", "2026-02-20", "2026-02-21"),
                ("MO-1052", "ITEM-BALLERINA-12", 367, 178, "Add accessories", "2026-01-05", "2026-01-06"),
                ("MO-1053", "ITEM-GARDEN-GNOME-30", 82, 17, "Final coating", "2026-02-25", "2026-02-26"),
                ("MO-1054", "ITEM-PIRATE-15", 254, 119, "Packaging prep", "2026-01-16", "2026-01-17"),
                ("MO-1055", "ITEM-NINJA-12", 389, 192, "Assemble and inspect", "2026-03-10", "2026-03-11"),
                ("MO-1056", "ITEM-UNICORN-25", 107, 29, "Paint details", "2026-02-02", "2026-02-03"),
                ("MO-1057", "ITEM-DISCO-18", 231, 104, "Curing process", "2025-12-28", "2025-12-29"),
                ("MO-1058", "ITEM-WIZARD-20", 376, 181, "Mold injection", "2026-01-23", "2026-01-24"),
                ("MO-1059", "ITEM-ASTRONAUT-22", 149, 49, "Quality check", "2026-03-05", "2026-03-06"),
                ("MO-1060", "ITEM-SUPERHERO-20", 294, 138, "Add accessories", "2026-02-16", "2026-02-17"),
                ("MO-1061", "ITEM-ZOMBIE-15", 68, 12, "Final coating", "2026-01-08", "2026-01-09"),
                ("MO-1062", "ITEM-VIKING-18", 217, 97, "Packaging prep", "2026-02-29", "2026-03-01"),
                ("MO-1063", "ITEM-MERMAID-20", 343, 164, "Assemble and inspect", "2026-01-14", "2026-01-15"),
                ("MO-1064", "ITEM-ROBOT-25", 125, 41, "Paint details", "2026-03-13", "2026-03-14"),
                ("MO-1065", "ITEM-CHEF-15", 268, 124, "Curing process", "2026-02-11", "2026-02-12"),
                ("MO-1066", "ITEM-ROCKSTAR-20", 91, 19, "Mold injection", "2025-12-26", "2025-12-27"),
                ("MO-1067", "ITEM-DETECTIVE-18", 356, 171, "Quality check", "2026-01-30", "2026-01-31"),
                ("MO-1068", "ITEM-SURFER-15", 182, 68, "Add accessories", "2026-03-02", "2026-03-03"),
                ("MO-1069", "ITEM-COWBOY-20", 309, 147, "Final coating", "2026-02-18", "2026-02-19"),
                ("MO-1070", "ITEM-BALLERINA-12", 53, 8, "Packaging prep", "2026-01-03", "2026-01-04"),
                ("MO-1071", "ITEM-GARDEN-GNOME-30", 241, 112, "Assemble and inspect", "2026-02-22", "2026-02-23"),
                ("MO-1072", "ITEM-PIRATE-15", 378, 184, "Paint details", "2026-01-19", "2026-01-20"),
                ("MO-1073", "ITEM-NINJA-12", 114, 34, "Curing process", "2026-03-08", "2026-03-09"),
                ("MO-1074", "ITEM-UNICORN-25", 287, 133, "Mold injection", "2026-02-05", "2026-02-06"),
                ("MO-1075", "ITEM-DISCO-18", 71, 14, "Quality check", "2025-12-29", "2025-12-30"),
                ("MO-1076", "ITEM-WIZARD-20", 203, 91, "Add accessories", "2026-01-26", "2026-01-27"),
                ("MO-1077", "ITEM-ASTRONAUT-22", 361, 176, "Final coating", "2026-03-11", "2026-03-12"),
                ("MO-1078", "ITEM-SUPERHERO-20", 138, 46, "Packaging prep", "2026-02-08", "2026-02-09"),
                ("MO-1079", "ITEM-ZOMBIE-15", 279, 131, "Assemble and inspect", "2026-01-12", "2026-01-13"),
                ("MO-1080", "ITEM-VIKING-18", 396, 193, "Paint details", "2026-02-24", "2026-02-25"),
                ("MO-1081", "ITEM-MERMAID-20", 86, 18, "Curing process", "2026-01-17", "2026-01-18"),
                ("MO-1082", "ITEM-ROBOT-25", 225, 103, "Mold injection", "2026-03-06", "2026-03-07"),
                ("MO-1083", "ITEM-CHEF-15", 348, 169, "Quality check", "2026-02-13", "2026-02-14"),
                ("MO-1084", "ITEM-ROCKSTAR-20", 161, 57, "Add accessories", "2026-01-01", "2026-01-02"),
                ("MO-1085", "ITEM-DETECTIVE-18", 292, 139, "Final coating", "2026-02-27", "2026-02-28"),
                ("MO-1086", "ITEM-SURFER-15", 47, 7, "Packaging prep", "2026-01-21", "2026-01-22"),
                ("MO-1087", "ITEM-COWBOY-20", 214, 96, "Assemble and inspect", "2026-03-09", "2026-03-10"),
                ("MO-1088", "ITEM-BALLERINA-12", 372, 181, "Paint details", "2026-02-01", "2026-02-02"),
                ("MO-1089", "ITEM-GARDEN-GNOME-30", 99, 24, "Curing process", "2025-12-27", "2025-12-28"),
                ("MO-1090", "ITEM-PIRATE-15", 256, 121, "Mold injection", "2026-01-28", "2026-01-29"),
                ("MO-1091", "ITEM-NINJA-12", 384, 189, "Quality check", "2026-03-14", "2026-03-15"),
                ("MO-1092", "ITEM-UNICORN-25", 127, 39, "Add accessories", "2026-02-19", "2026-02-20"),
                ("MO-1093", "ITEM-DISCO-18", 269, 126, "Final coating", "2026-01-10", "2026-01-11"),
                ("MO-1094", "ITEM-WIZARD-20", 62, 11, "Packaging prep", "2026-03-03", "2026-03-04"),
                ("MO-1095", "ITEM-ASTRONAUT-22", 198, 88, "Assemble and inspect", "2026-02-15", "2026-02-16"),
                ("MO-1096", "ITEM-SUPERHERO-20", 337, 162, "Paint details", "2026-01-06", "2026-01-07"),
                ("MO-1097", "ITEM-ZOMBIE-15", 153, 51, "Curing process", "2026-02-26", "2026-02-27"),
                ("MO-1098", "ITEM-VIKING-18", 281, 132, "Mold injection", "2026-01-24", "2026-01-25"),
                ("MO-1099", "ITEM-MERMAID-20", 76, 15, "Quality check", "2026-03-12", "2026-03-13"),
            ],
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
