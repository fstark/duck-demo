"""Foundation layer — catalog, suppliers, recipes, customers, starting stock.

Sets simulation clock to 2025-08-01 and populates all standing data needed
before individual story scenarios run.
"""

import logging
import random
from typing import List

from services._base import db_conn
from services import customer_service, simulation_service

import config

logger = logging.getLogger(__name__)

# ============================================================================
# DATA DEFINITIONS
# ============================================================================

# -- Raw materials & components ----------------------------------------------
MATERIALS = [
    # (id, sku, name, type, unit_price, cost_price, uom, reorder_qty, default_supplier_id)
    ("ITEM-PVC",        "PVC-PELLETS",   "PVC Pellets",               "raw_material", None, 0.012, "g",  1500000, "SUP-001"),
    ("ITEM-BLACK-DYE",  "BLACK-DYE",     "Black Dye",                 "raw_material", None, 0.08,  "ml",  800,  "SUP-002"),
    ("ITEM-YELLOW-DYE", "YELLOW-DYE",    "Yellow Dye",                "raw_material", None, 0.09,  "ml",  800,  "SUP-002"),
    ("ITEM-RED-DYE",    "RED-DYE",       "Red Dye",                   "raw_material", None, 0.10,  "ml",  600,  "SUP-002"),
    ("ITEM-GREEN-DYE",  "GREEN-DYE",     "Green Dye",                 "raw_material", None, 0.09,  "ml",  500,  "SUP-002"),
    ("ITEM-WHITE-DYE",  "WHITE-DYE",     "White Dye",                 "raw_material", None, 0.07,  "ml",  600,  "SUP-002"),
    ("ITEM-ORANGE-DYE", "ORANGE-DYE",    "Orange Dye",                "raw_material", None, 0.09,  "ml",  500,  "SUP-002"),
    ("ITEM-BLUE-DYE",   "BLUE-DYE",      "Blue Dye",                  "raw_material", None, 0.10,  "ml",  500,  "SUP-002"),
    ("ITEM-PINK-DYE",   "PINK-DYE",      "Pink Dye",                  "raw_material", None, 0.11,  "ml",  400,  "SUP-002"),
    ("ITEM-BOX-SMALL",  "BOX-SMALL",     "Small Box",                 "raw_material", None, 0.45,  "ea",  1000, "SUP-003"),
    ("ITEM-BOX-MEDIUM", "BOX-MEDIUM",    "Medium Box",                "raw_material", None, 0.65,  "ea",  500,  "SUP-003"),
    ("ITEM-FOAM-SHEET", "FOAM-SHEET",    "Foam Padding Sheet",        "raw_material", None, 0.30,  "ea",  600,  "SUP-003"),
    ("ITEM-PAINT-GLOSS","PAINT-GLOSS",   "Gloss Finish Paint",        "raw_material", None, 0.15,  "ml",  400,  "SUP-002"),
]

# -- Finished goods ----------------------------------------------------------
FINISHED_GOODS = [
    # (id, sku, name, unit_price, size_cm)
    # Original ducks from seed
    ("ITEM-ELVIS-20",       "ELVIS-DUCK-20CM",      "Elvis Duck 20cm",              12.0,  20),
    ("ITEM-MARILYN-20",     "MARILYN-DUCK-20CM",    "Marilyn Duck 20cm",            12.0,  20),
    ("ITEM-CLASSIC-10",     "CLASSIC-DUCK-10CM",    "Classic Duck 10cm",            10.0,  10),
    ("ITEM-PIRATE-15",      "PIRATE-DUCK-15CM",     "Pirate Duck 15cm",             14.5,  15),
    ("ITEM-NINJA-12",       "NINJA-DUCK-12CM",      "Ninja Duck 12cm",              13.0,  12),
    ("ITEM-UNICORN-25",     "UNICORN-DUCK-25CM",    "Unicorn Duck 25cm",            18.0,  25),
    ("ITEM-DISCO-18",       "DISCO-DUCK-18CM",      "Disco Duck 18cm",              15.5,  18),
    ("ITEM-WIZARD-20",      "WIZARD-DUCK-20CM",     "Wizard Duck 20cm",             16.0,  20),
    ("ITEM-ASTRONAUT-22",   "ASTRONAUT-DUCK-22CM",  "Astronaut Duck 22cm",          19.0,  22),
    ("ITEM-SUPERHERO-20",   "SUPERHERO-DUCK-20CM",  "Superhero Duck 20cm",          17.5,  20),
    ("ITEM-ZOMBIE-15",      "ZOMBIE-DUCK-15CM",     "Zombie Duck 15cm",             11.5,  15),
    ("ITEM-VIKING-18",      "VIKING-DUCK-18CM",     "Viking Duck 18cm",             16.5,  18),
    ("ITEM-MERMAID-20",     "MERMAID-DUCK-20CM",    "Mermaid Duck 20cm",            14.0,  20),
    ("ITEM-ROBOT-25",       "ROBOT-DUCK-25CM",      "Robot Duck 25cm",              22.0,  25),
    ("ITEM-CHEF-15",        "CHEF-DUCK-15CM",       "Chef Duck 15cm",               13.5,  15),
    ("ITEM-ROCKSTAR-20",    "ROCKSTAR-DUCK-20CM",   "Rockstar Duck 20cm",           15.0,  20),
    ("ITEM-DETECTIVE-18",   "DETECTIVE-DUCK-18CM",  "Detective Duck 18cm",          14.5,  18),
    ("ITEM-SURFER-15",      "SURFER-DUCK-15CM",     "Surfer Duck 15cm",             12.5,  15),
    ("ITEM-COWBOY-20",      "COWBOY-DUCK-20CM",     "Cowboy Duck 20cm",             16.0,  20),
    ("ITEM-BALLERINA-12",   "BALLERINA-DUCK-12CM",  "Ballerina Duck 12cm",          11.0,  12),
    ("ITEM-GARDEN-GNOME-30","GNOME-DUCK-30CM",      "Garden Gnome Duck 30cm",       25.0,  30),
    ("ITEM-PARROT-18",      "PARROT-DUCK-18CM",     "Parrot Duck 18cm",             16.5,  18),
    # Seasonal & expansion ducks
    ("ITEM-WITCH-15",       "WITCH-DUCK-15CM",      "Witch Duck 15cm",              13.5,  15),
    ("ITEM-PUMPKIN-12",     "PUMPKIN-DUCK-12CM",    "Pumpkin Duck 12cm",            12.0,  12),
    ("ITEM-SANTA-20",       "SANTA-DUCK-20CM",      "Santa Duck 20cm",              16.0,  20),
    ("ITEM-SNOWMAN-18",     "SNOWMAN-DUCK-18CM",    "Snowman Duck 18cm",            14.5,  18),
    ("ITEM-REINDEER-15",    "REINDEER-DUCK-15CM",   "Reindeer Duck 15cm",           14.0,  15),
    ("ITEM-LEDERHOSEN-20",  "LEDERHOSEN-DUCK-20CM", "Lederhosen Duck 20cm",         17.0,  20),
    ("ITEM-OKTOBERFEST-18", "OKTOBERFEST-DUCK-18CM","Oktoberfest Duck 18cm",        16.0,  18),
    ("ITEM-VAMPIRE-15",     "VAMPIRE-DUCK-15CM",    "Vampire Duck 15cm",            13.0,  15),
    ("ITEM-GHOST-12",       "GHOST-DUCK-12CM",      "Ghost Duck 12cm",              11.0,  12),
    ("ITEM-FRANKENSTEIN-20","FRANKENSTEIN-DUCK-20CM","Frankenstein Duck 20cm",       15.5,  20),
    ("ITEM-ELF-12",         "ELF-DUCK-12CM",        "Elf Duck 12cm",                11.5,  12),
    ("ITEM-GINGERBREAD-15", "GINGERBREAD-DUCK-15CM","Gingerbread Duck 15cm",        13.0,  15),
    ("ITEM-CUPID-12",       "CUPID-DUCK-12CM",      "Cupid Duck 12cm",              12.0,  12),
    ("ITEM-LEPRECHAUN-15",  "LEPRECHAUN-DUCK-15CM", "Leprechaun Duck 15cm",         13.5,  15),
    ("ITEM-BUNNY-12",       "BUNNY-DUCK-12CM",      "Bunny Duck 12cm",              11.5,  12),
]

# -- Suppliers ---------------------------------------------------------------
SUPPLIERS = [
    # (id, name, contact_email, lead_time_days)
    ("SUP-001", "PlasticCorp",              "orders@plasticcorp.example",          10),
    ("SUP-002", "ColorMaster",               "sales@colormaster.example",           7),
    ("SUP-003", "PackagingPlus",            "contact@packagingplus.example",       5),
    ("SUP-004", "EuroPlast GmbH",           "bestellung@europlast.example",       12),
    ("SUP-005", "Pigment Express",          "orders@pigmentexpress.example",       6),
    ("SUP-006", "BoxFactory Direct",        "sales@boxfactory.example",            4),
    ("SUP-007", "Rhine Chemical Supply",    "info@rhinechemical.example",          9),
    ("SUP-008", "QuickPack Logistics",      "orders@quickpack.example",            3),
    ("SUP-009", "DuraPoly Industries",      "procurement@durapoly.example",       14),
    ("SUP-010", "ChemiColor France",        "commandes@chemicolor.example",        8),
]


# -- Recipe template: maps output_item_id → recipe definition ----------------
# Each recipe: (recipe_id, output_qty, output_uom, production_time_hours, notes, ingredients, operations)
# ingredients: [(input_item_id, input_qty, input_uom), ...]
# operations:  [(operation_name, duration_hours), ...]

def _std_recipe(item_id: str, size_cm: int, dyes: list, extra_materials: list = None,
                extra_ops: list = None, notes: str = "") -> dict:
    """Build a standardised recipe dict based on duck size.

    Scales PVC, box size, and production time by duck size.
    """
    # PVC scales roughly with size; stored in grams
    pvc_g = round(size_cm * 0.12 * 1000)
    box = "ITEM-BOX-MEDIUM" if size_cm >= 20 else "ITEM-BOX-SMALL"
    base_time = round(1.5 + size_cm * 0.1, 1)

    ingredients = [("ITEM-PVC", pvc_g, "g")]
    ingredients.extend(dyes)
    ingredients.extend(extra_materials or [])
    ingredients.append((box, 1, "ea"))

    operations = [
        ("Mold injection", round(0.5 + size_cm * 0.05, 2), "MOLDING"),
        ("Cooling", 0.5, "CURING"),
    ]
    # Paint operations per dye
    for item_id_dye, qty, _uom in dyes:
        colour = item_id_dye.replace("ITEM-", "").replace("-DYE", "").replace("-", " ").title()
        operations.append((f"Paint {colour.lower()}", round(0.3 + qty / 300, 2), "PAINTING"))
    operations.extend(extra_ops or [])
    operations.append(("Quality check", 0.25, "QC"))
    operations.append(("Pack into box", 0.25, "PACKAGING"))

    total_hours = round(sum(op[1] for op in operations), 1)
    output_qty = max(6, 24 - size_cm)  # larger ducks → smaller batch

    return {
        "output_qty": output_qty,
        "prod_hours": total_hours,
        "notes": notes,
        "ingredients": ingredients,
        "operations": operations,
    }


# Map item_id → recipe definition overrides or auto-generated
def _build_recipe_defs():
    """Return dict of item_id → recipe dict."""
    defs = {}

    # --- Original 6 recipes (keep close to seed_demo quantities) ---
    defs["ITEM-ELVIS-20"] = {
        "output_qty": 12, "prod_hours": 3.5,
        "notes": "Elvis Duck 20cm - signature black hair and white jumpsuit",
        "ingredients": [("ITEM-PVC", 2400, "g"), ("ITEM-BLACK-DYE", 180, "ml"), ("ITEM-YELLOW-DYE", 50, "ml"), ("ITEM-BOX-MEDIUM", 1, "ea")],
        "operations": [("Mold injection", 1.5, "MOLDING"), ("Cooling", 0.5, "CURING"), ("Paint hair black", 0.75, "PAINTING"), ("Paint details yellow", 0.5, "PAINTING"), ("Pack into box", 0.25, "PACKAGING")],
    }
    defs["ITEM-CLASSIC-10"] = {
        "output_qty": 24, "prod_hours": 2.5,
        "notes": "Classic yellow duck - high volume simple design",
        "ingredients": [("ITEM-PVC", 1200, "g"), ("ITEM-YELLOW-DYE", 150, "ml"), ("ITEM-BOX-SMALL", 2, "ea")],
        "operations": [("Mold injection", 1.0, "MOLDING"), ("Paint yellow", 0.75, "PAINTING"), ("Quality check", 0.5, "QC"), ("Pack into boxes", 0.25, "PACKAGING")],
    }
    defs["ITEM-ROBOT-25"] = {
        "output_qty": 8, "prod_hours": 6.5,
        "notes": "Robot Duck - metallic finish, most complex design",
        "ingredients": [("ITEM-PVC", 3200, "g"), ("ITEM-BLACK-DYE", 200, "ml"), ("ITEM-YELLOW-DYE", 80, "ml"), ("ITEM-BOX-MEDIUM", 1, "ea")],
        "operations": [("Mold injection", 2.0, "MOLDING"), ("Curing process", 1.0, "CURING"), ("Base coat", 1.5, "PAINTING"), ("Paint robot details", 1.0, "PAINTING"), ("Assemble parts", 0.5, "ASSEMBLY"), ("Quality check", 0.25, "QC"), ("Pack into box", 0.25, "PACKAGING")],
    }
    defs["ITEM-PIRATE-15"] = {
        "output_qty": 12, "prod_hours": 4.0,
        "notes": "Pirate Duck with eye patch and hat",
        "ingredients": [("ITEM-PVC", 1800, "g"), ("ITEM-BLACK-DYE", 150, "ml"), ("ITEM-YELLOW-DYE", 60, "ml"), ("ITEM-BOX-SMALL", 1, "ea")],
        "operations": [("Mold injection", 1.5, "MOLDING"), ("Cooling", 0.5, "CURING"), ("Paint base yellow", 0.75, "PAINTING"), ("Paint pirate details", 0.75, "PAINTING"), ("Quality check", 0.25, "QC"), ("Pack into box", 0.25, "PACKAGING")],
    }
    defs["ITEM-NINJA-12"] = {
        "output_qty": 12, "prod_hours": 3.75,
        "notes": "Ninja Duck with mask and ninja outfit",
        "ingredients": [("ITEM-PVC", 1400, "g"), ("ITEM-BLACK-DYE", 160, "ml"), ("ITEM-YELLOW-DYE", 40, "ml"), ("ITEM-BOX-SMALL", 1, "ea")],
        "operations": [("Mold injection", 1.25, "MOLDING"), ("Cooling", 0.5, "CURING"), ("Paint ninja outfit", 1.0, "PAINTING"), ("Quality check", 0.75, "QC"), ("Pack into box", 0.25, "PACKAGING")],
    }
    defs["ITEM-UNICORN-25"] = {
        "output_qty": 10, "prod_hours": 5.0,
        "notes": "Unicorn Duck with horn and rainbow colors",
        "ingredients": [("ITEM-PVC", 2500, "g"), ("ITEM-BLACK-DYE", 100, "ml"), ("ITEM-YELLOW-DYE", 120, "ml"), ("ITEM-BOX-MEDIUM", 1, "ea")],
        "operations": [("Mold injection", 1.75, "MOLDING"), ("Cooling", 0.75, "CURING"), ("Paint rainbow colors", 1.5, "PAINTING"), ("Attach horn", 0.5, "ASSEMBLY"), ("Quality check", 0.25, "QC"), ("Pack into box", 0.25, "PACKAGING")],
    }

    # --- Auto-generated recipes for remaining ducks ---
    auto = {
        "ITEM-MARILYN-20":      (20, [("ITEM-YELLOW-DYE", 120, "ml"), ("ITEM-WHITE-DYE", 80, "ml"), ("ITEM-RED-DYE", 40, "ml")], "Marilyn Duck - blonde hair, red lips"),
        "ITEM-DISCO-18":        (18, [("ITEM-YELLOW-DYE", 80, "ml"), ("ITEM-PINK-DYE", 100, "ml"), ("ITEM-PAINT-GLOSS", 60, "ml")], "Disco Duck - sparkly gloss finish"),
        "ITEM-WIZARD-20":       (20, [("ITEM-BLUE-DYE", 140, "ml"), ("ITEM-BLACK-DYE", 60, "ml")], "Wizard Duck - blue robe and hat"),
        "ITEM-ASTRONAUT-22":    (22, [("ITEM-WHITE-DYE", 180, "ml"), ("ITEM-BLACK-DYE", 40, "ml")], "Astronaut Duck - white suit, visor"),
        "ITEM-SUPERHERO-20":    (20, [("ITEM-RED-DYE", 120, "ml"), ("ITEM-BLUE-DYE", 80, "ml")], "Superhero Duck - cape and mask"),
        "ITEM-ZOMBIE-15":       (15, [("ITEM-GREEN-DYE", 100, "ml"), ("ITEM-BLACK-DYE", 40, "ml")], "Zombie Duck - green tint, torn look"),
        "ITEM-VIKING-18":       (18, [("ITEM-YELLOW-DYE", 80, "ml"), ("ITEM-BLACK-DYE", 80, "ml")], "Viking Duck - helmet and fur"),
        "ITEM-MERMAID-20":      (20, [("ITEM-BLUE-DYE", 100, "ml"), ("ITEM-GREEN-DYE", 80, "ml"), ("ITEM-PINK-DYE", 40, "ml")], "Mermaid Duck - shimmery tail"),
        "ITEM-CHEF-15":         (15, [("ITEM-WHITE-DYE", 100, "ml"), ("ITEM-BLACK-DYE", 20, "ml")], "Chef Duck - toque and apron"),
        "ITEM-ROCKSTAR-20":     (20, [("ITEM-BLACK-DYE", 140, "ml"), ("ITEM-RED-DYE", 60, "ml")], "Rockstar Duck - leather jacket"),
        "ITEM-DETECTIVE-18":    (18, [("ITEM-BLACK-DYE", 120, "ml"), ("ITEM-YELLOW-DYE", 40, "ml")], "Detective Duck - trench coat and magnifier"),
        "ITEM-SURFER-15":       (15, [("ITEM-YELLOW-DYE", 80, "ml"), ("ITEM-BLUE-DYE", 60, "ml")], "Surfer Duck - board and shades"),
        "ITEM-COWBOY-20":       (20, [("ITEM-YELLOW-DYE", 60, "ml"), ("ITEM-BLACK-DYE", 80, "ml"), ("ITEM-RED-DYE", 40, "ml")], "Cowboy Duck - hat, boots, bandana"),
        "ITEM-BALLERINA-12":    (12, [("ITEM-PINK-DYE", 100, "ml"), ("ITEM-WHITE-DYE", 40, "ml")], "Ballerina Duck - tutu and slippers"),
        "ITEM-GARDEN-GNOME-30": (30, [("ITEM-RED-DYE", 120, "ml"), ("ITEM-WHITE-DYE", 80, "ml"), ("ITEM-GREEN-DYE", 60, "ml")], "Garden Gnome Duck - pointy hat, beard"),
        "ITEM-PARROT-18":       (18, [("ITEM-GREEN-DYE", 80, "ml"), ("ITEM-RED-DYE", 80, "ml"), ("ITEM-YELLOW-DYE", 60, "ml")], "Parrot Duck - tropical multicolor"),
        # Seasonal
        "ITEM-WITCH-15":        (15, [("ITEM-BLACK-DYE", 120, "ml"), ("ITEM-GREEN-DYE", 40, "ml")], "Witch Duck - pointy hat and broom"),
        "ITEM-PUMPKIN-12":      (12, [("ITEM-ORANGE-DYE", 140, "ml"), ("ITEM-GREEN-DYE", 20, "ml")], "Pumpkin Duck - jack-o-lantern face"),
        "ITEM-SANTA-20":        (20, [("ITEM-RED-DYE", 140, "ml"), ("ITEM-WHITE-DYE", 80, "ml")], "Santa Duck - red suit, white beard"),
        "ITEM-SNOWMAN-18":      (18, [("ITEM-WHITE-DYE", 160, "ml"), ("ITEM-ORANGE-DYE", 20, "ml"), ("ITEM-BLACK-DYE", 20, "ml")], "Snowman Duck - carrot nose, top hat"),
        "ITEM-REINDEER-15":     (15, [("ITEM-RED-DYE", 40, "ml"), ("ITEM-BLACK-DYE", 80, "ml")], "Reindeer Duck - antlers and red nose"),
        "ITEM-LEDERHOSEN-20":   (20, [("ITEM-YELLOW-DYE", 80, "ml"), ("ITEM-GREEN-DYE", 60, "ml"), ("ITEM-WHITE-DYE", 40, "ml")], "Lederhosen Duck - Bavarian outfit"),
        "ITEM-OKTOBERFEST-18":  (18, [("ITEM-BLUE-DYE", 80, "ml"), ("ITEM-WHITE-DYE", 60, "ml"), ("ITEM-YELLOW-DYE", 40, "ml")], "Oktoberfest Duck - dirndl / pretzel"),
        "ITEM-VAMPIRE-15":      (15, [("ITEM-BLACK-DYE", 100, "ml"), ("ITEM-RED-DYE", 60, "ml")], "Vampire Duck - cape and fangs"),
        "ITEM-GHOST-12":        (12, [("ITEM-WHITE-DYE", 120, "ml")], "Ghost Duck - translucent sheet look"),
        "ITEM-FRANKENSTEIN-20": (20, [("ITEM-GREEN-DYE", 140, "ml"), ("ITEM-BLACK-DYE", 60, "ml")], "Frankenstein Duck - bolts and stitches"),
        "ITEM-ELF-12":          (12, [("ITEM-GREEN-DYE", 80, "ml"), ("ITEM-RED-DYE", 40, "ml")], "Elf Duck - pointy ears and hat"),
        "ITEM-GINGERBREAD-15":  (15, [("ITEM-RED-DYE", 40, "ml"), ("ITEM-WHITE-DYE", 60, "ml"), ("ITEM-BLACK-DYE", 20, "ml")], "Gingerbread Duck - icing details"),
        "ITEM-CUPID-12":        (12, [("ITEM-PINK-DYE", 100, "ml"), ("ITEM-RED-DYE", 40, "ml"), ("ITEM-WHITE-DYE", 30, "ml")], "Cupid Duck - wings, bow and arrow"),
        "ITEM-LEPRECHAUN-15":   (15, [("ITEM-GREEN-DYE", 120, "ml"), ("ITEM-YELLOW-DYE", 40, "ml")], "Leprechaun Duck - top hat and shamrock"),
        "ITEM-BUNNY-12":        (12, [("ITEM-WHITE-DYE", 80, "ml"), ("ITEM-PINK-DYE", 40, "ml")], "Bunny Duck - floppy ears and cotton tail"),
    }

    for item_id, (size, dyes, notes) in auto.items():
        if item_id not in defs:
            defs[item_id] = _std_recipe(item_id, size, dyes, notes=notes)

    return defs


# -- Initial stock (raw materials) -------------------------------------------
INITIAL_STOCK = [
    # (item_id, warehouse, location, on_hand)
    ("ITEM-PVC",        config.WAREHOUSE_DEFAULT, "RM/BULK-01",  2500000),
    ("ITEM-BLACK-DYE",  config.WAREHOUSE_DEFAULT, "RM/SHELF-01", 1200),
    ("ITEM-YELLOW-DYE", config.WAREHOUSE_DEFAULT, "RM/SHELF-02", 1200),
    ("ITEM-RED-DYE",    config.WAREHOUSE_DEFAULT, "RM/SHELF-03",  800),
    ("ITEM-GREEN-DYE",  config.WAREHOUSE_DEFAULT, "RM/SHELF-04",  700),
    ("ITEM-WHITE-DYE",  config.WAREHOUSE_DEFAULT, "RM/SHELF-05",  900),
    ("ITEM-ORANGE-DYE", config.WAREHOUSE_DEFAULT, "RM/SHELF-06",  600),
    ("ITEM-BLUE-DYE",   config.WAREHOUSE_DEFAULT, "RM/SHELF-07",  700),
    ("ITEM-PINK-DYE",   config.WAREHOUSE_DEFAULT, "RM/SHELF-08",  500),
    ("ITEM-BOX-SMALL",  config.WAREHOUSE_DEFAULT, "PK/BIN-01",   2000),
    ("ITEM-BOX-MEDIUM", config.WAREHOUSE_DEFAULT, "PK/BIN-02",   1000),
    ("ITEM-FOAM-SHEET", config.WAREHOUSE_DEFAULT, "PK/BIN-03",    800),
    ("ITEM-PAINT-GLOSS",config.WAREHOUSE_DEFAULT, "PK/BIN-04",    500),
]


# -- Customer definitions for base pool --------------------------------------
BASE_CUSTOMERS = [
    # (name, company, email, phone, addr, city, postal, country, tax_id, terms, notes)
    ("Sarah Martin",          None,                     "sarah@martin-retail.example",      "+33 6 12 34 56 78",  "15 Rue de la Paix",          "Paris",       "75002", "FR", None,              30,  None),
    ("Jean-Pierre Dubois",    "Canard & Fils",          "jp@canard-fils.example",           "+33 4 78 00 11 22",  "42 Avenue Jean Jaurès",      "Lyon",        "69007", "FR", "FR12345678901",   45,  "Key account"),
    ("Marie Laurent",         "Jouets Laurent",         "marie@jouetslaurent.example",      "+33 1 42 33 44 55",  "8 Boulevard Haussmann",      "Paris",       "75009", "FR", "FR98765432109",   30,  None),
    ("Daisy Paddlesworth",    "Splash & Co",            "daisy@splashco.example",           "+33 4 93 12 34 56",  "22 Promenade des Anglais",   "Nice",        "06000", "FR", "FR55566677788",   30,  None),
    ("Quentin Maréchal",      None,                     "quentin@mare.example",              None,                "17 Rue du Vieux Port",       "Marseille",   "13001", "FR", None,              30,  "Prefers email"),
    ("Bella Featherstone",    "The Duck Emporium",      "bella@duckemporium.example",       "+33 5 61 22 33 44",  "5 Place du Capitole",        "Toulouse",    "31000", "FR", "FR11122233344",   60,  "Large orders"),
    ("Puddles O'Mallory",     None,                      None,                              "+33 5 56 78 90 12",   None,                        "Bordeaux",     None,   "FR", None,              30,  "No email"),
    ("Drake Fluffington",     "Fluff & Feathers",       "drake@fluffnfeathers.example",     "+33 3 88 11 22 33",  "28 Rue des Hallebardes",     "Strasbourg",  "67000", "FR", "FR77788899900",   30,  None),
    ("Mallory Beakworth",     None,                     "mallory@beakmail.example",         "+33 2 40 55 66 77",   None,                        "Nantes",       None,   "FR", None,              15,  "COD preferred"),
    ("Hugo Canard",           "Waddle Inc",             "hugo@waddleinc.example",           "+33 3 20 44 55 66",  "12 Rue Faidherbe",           "Lille",       "59000", "FR", "FR44455566677",   30,  None),
    ("Sophie Leclerc",        None,                     "sophie@leclerc-toys.example",       None,                "7 Place de la Comédie",      "Montpellier", "34000", "FR", None,              30,  None),
    ("Antoine Rivière",       "Aquatic Adventures",     "antoine@aquatic.example",          "+33 2 99 33 44 55",  "3 Quai Émile Zola",          "Rennes",      "35000", "FR", "FR22233344455",   30,  None),
    ("Camille Fontaine",      None,                     "camille@fontaine-jouets.example",  "+33 4 76 22 33 44",  "19 Avenue Alsace-Lorraine",  "Grenoble",    "38000", "FR", None,              30,  None),
    ("Louis Moreau",          "Bath Time Boutique",     "louis@bathtime.example",           "+33 3 80 11 22 33",  "45 Rue de la Liberté",       "Dijon",       "21000", "FR", "FR66677788899",   30,  None),
    ("Raphaël Petit",         "Quack Squadron",         "raphael@quacksquadron.example",    "+33 2 41 55 66 77",  "6 Boulevard du Roi René",    "Angers",      "49000", "FR", "FR33344455566",   30,  "Military discount"),
    ("Charlotte Bonnard",     None,                     "charlotte@bonnard.example",        "+33 2 35 22 33 44",   None,                        "Le Havre",     None,   "FR", None,              30,  None),
    ("Nicolas Garnier",       "Webfoot Wonders",        "nicolas@webfoot.example",          "+33 3 26 44 55 66",  "14 Place Drouet d'Erlon",    "Reims",       "51100", "FR", "FR88899900011",   30,  None),
    ("Emma Dupont",           "La Maison du Canard",    "emma@maisondcanard.example",       "+33 4 72 33 44 55",  "25 Rue de la République",    "Lyon",        "69002", "FR", "FR11223344556",   30,  None),
    ("Pierre Rousseau",       None,                     "pierre@rousseau.example",          "+33 1 55 66 77 88",  "33 Avenue des Champs-Élysées","Paris",      "75008", "FR", None,              45,  "Premium client"),
    ("Mathilde Simon",        "Canards en Fête",        "mathilde@canardsfete.example",     "+33 5 57 88 99 00",  "9 Cours de l'Intendance",    "Bordeaux",    "33000", "FR", "FR99887766554",   30,  None),
    ("Thomas Bernard",        "Le Comptoir du Jouet",   "thomas@comptoir-jouet.example",    "+33 4 91 22 33 44",  "18 La Canebière",            "Marseille",   "13001", "FR", "FR66778899001",   60,  "Quarterly invoicing"),
    ("Léa Mercier",           None,                     "lea@mercier.example",              "+33 2 98 77 66 55",  "5 Rue de Siam",              "Brest",       "29200", "FR", None,              30,  None),
    ("Gabriel Martin",        "Jouets du Marais",       "gabriel@jouetsmarais.example",     "+33 1 44 55 66 77",  "12 Rue des Francs-Bourgeois","Paris",       "75003", "FR", "FR55443322110",   30,  None),
    ("Inès Lefebvre",         "Cadeaux Inès",           "ines@cadeaux-ines.example",        "+33 3 87 66 55 44",  "7 Place Kléber",             "Strasbourg",  "67000", "FR", "FR33221100998",   30,  None),
    ("Clément Durand",        None,                     "clement@durand-toys.example",      "+33 4 42 55 66 77",  "22 Cours Mirabeau",          "Aix-en-Provence","13100","FR", None,             30,  None),
    ("Zoé Lambert",           "Comptoir des Canards",   "zoe@comptoircanards.example",      "+33 2 40 88 99 00",  "15 Passage Pommeraye",       "Nantes",      "44000", "FR", "FR11009988776",   30,  None),
    ("Arthur Morel",          None,                     "arthur@morel.example",             "+33 4 67 88 99 11",  "3 Place de la Comédie",      "Montpellier", "34000", "FR", None,              15,  None),
    ("Jade Bonnet",           "Boutique Bonnet",        "jade@boutique-bonnet.example",     "+33 5 62 33 44 55",  "8 Rue Saint-Rome",           "Toulouse",    "31000", "FR", "FR44556677883",   30,  None),
    ("Jules Lemaire",         "Canard Express",         "jules@canardexpress.example",      "+33 1 34 55 66 77",  "44 Rue du Commerce",         "Paris",       "75015", "FR", "FR88776655443",   60,  "Express shipping required"),
    ("Clara Girard",          None,                     "clara@girard.example",             "+33 4 73 44 55 66",  "10 Place de Jaude",          "Clermont-Ferrand","63000","FR", None,            30,  None),
]


# ============================================================================
# POPULATE FUNCTION
# ============================================================================

def populate() -> dict:
    """Insert all base/foundation data. Returns summary counts."""
    logger.info("Starting base_setup.populate()")

    # --- Set simulation clock to 2025-08-01 ---
    simulation_service.advance_time(to_time="2025-08-01 08:00:00", side_effects=False)
    logger.info("Simulation clock set to 2025-08-01 08:00:00")

    with db_conn() as conn:
        # ---- Items (materials) ----
        for item_id, sku, name, itype, price, cost, uom, reorder, default_supplier_id in MATERIALS:
            conn.execute(
                "INSERT INTO items (id, sku, name, type, unit_price, cost_price, uom, reorder_qty, default_supplier_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (item_id, sku, name, itype, price, cost, uom, reorder, default_supplier_id),
            )
        logger.info("Inserted %d raw materials", len(MATERIALS))

        # ---- Items (finished goods) ----
        # Try loading images from images/ directory if available
        from pathlib import Path
        images_dir = Path(__file__).resolve().parent.parent / "images"

        for item_id, sku, name, price, _size in FINISHED_GOODS:
            image_data = None
            image_path = images_dir / f"{sku}.png"
            if image_path.exists():
                try:
                    from PIL import Image
                    from io import BytesIO
                    with Image.open(image_path) as img:
                        img_resized = img.resize((256, 256), Image.Resampling.LANCZOS)
                        buf = BytesIO()
                        img_resized.save(buf, format="PNG")
                        image_data = buf.getvalue()
                except Exception as e:
                    logger.debug("Could not load image for %s: %s", sku, e)
            conn.execute(
                "INSERT INTO items (id, sku, name, type, unit_price, uom, reorder_qty, image) VALUES (?,?,?,?,?,?,?,?)",
                (item_id, sku, name, "finished_good", price, "ea", 0, image_data),
            )
        logger.info("Inserted %d finished goods", len(FINISHED_GOODS))

        # ---- Suppliers ----
        conn.executemany(
            "INSERT INTO suppliers (id, name, contact_email, lead_time_days) VALUES (?,?,?,?)",
            SUPPLIERS,
        )
        logger.info("Inserted %d suppliers", len(SUPPLIERS))

        # ---- Recipes ----
        recipe_defs = _build_recipe_defs()
        ing_counter = 0
        op_counter = 0
        for item_id, rdef in recipe_defs.items():
            # Derive recipe_id from item_id: ITEM-ELVIS-20 → RCP-ELVIS-20
            rcp_id = item_id.replace("ITEM-", "RCP-")
            conn.execute(
                "INSERT INTO recipes (id, output_item_id, output_qty, output_uom, production_time_hours, notes) VALUES (?,?,?,?,?,?)",
                (rcp_id, item_id, rdef["output_qty"], "ea", rdef["prod_hours"], rdef.get("notes", "")),
            )
            for seq, (inp_item_id, inp_qty, inp_uom) in enumerate(rdef["ingredients"], start=1):
                ing_counter += 1
                conn.execute(
                    "INSERT INTO recipe_ingredients (id, recipe_id, sequence_order, input_item_id, input_qty, input_uom) VALUES (?,?,?,?,?,?)",
                    (f"ING-{ing_counter:04d}", rcp_id, seq, inp_item_id, inp_qty, inp_uom),
                )
            for seq, (op_name, dur, wc) in enumerate(rdef["operations"], start=1):
                op_counter += 1
                conn.execute(
                    "INSERT INTO recipe_operations (id, recipe_id, sequence_order, operation_name, duration_hours, work_center) VALUES (?,?,?,?,?,?)",
                    (f"OP-{op_counter:04d}", rcp_id, seq, op_name, dur, wc),
                )
        logger.info("Inserted %d recipes (%d ingredients, %d operations)",
                     len(recipe_defs), ing_counter, op_counter)

        # ---- Work centers ----
        for wc_name, max_conc in config.WORK_CENTER_CAPACITY.items():
            conn.execute(
                "INSERT INTO work_centers (id, name, max_concurrent, description) VALUES (?,?,?,?)",
                (f"WC-{wc_name}", wc_name, max_conc, f"{wc_name.title()} work center"),
            )
        logger.info("Inserted %d work centers", len(config.WORK_CENTER_CAPACITY))

        # ---- Initial raw material stock ----
        for idx, (item_id, wh, loc, qty) in enumerate(INITIAL_STOCK, start=1):
            conn.execute(
                "INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?,?,?,?,?)",
                (f"STK-{idx:04d}", item_id, wh, loc, qty),
            )
        logger.info("Inserted %d initial stock rows", len(INITIAL_STOCK))

        conn.commit()

    # ---- Customers (via service layer for proper ID generation) ----
    customer_ids: List[str] = []
    for (name, company, email, phone, addr, city, postal, country, tax_id, terms, notes) in BASE_CUSTOMERS:
        result = customer_service.create_customer(
            name=name, company=company, email=email, phone=phone,
            address_line1=addr, city=city, postal_code=postal, country=country,
            tax_id=tax_id, payment_terms=terms, notes=notes,
        )
        customer_ids.append(result["customer_id"])
    logger.info("Created %d base customers", len(customer_ids))

    summary = {
        "materials": len(MATERIALS),
        "finished_goods": len(FINISHED_GOODS),
        "suppliers": len(SUPPLIERS),
        "recipes": len(recipe_defs),
        "initial_stock_rows": len(INITIAL_STOCK),
        "customers": len(customer_ids),
        "customer_ids": customer_ids,
        "sim_time": simulation_service.get_current_time(),
    }
    logger.info("base_setup complete: %s", {k: v for k, v in summary.items() if k != "customer_ids"})
    return summary
