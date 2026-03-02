"""Reusable story primitives for scenario scripts.

High-level functions that chain service calls to drive common business flows:
full sales cycles, customer batches, demand bursts, supply disruptions, etc.
"""

import random
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from services import (
    simulation_service,
    customer_service,
    sales_service,
    quote_service,
    production_service,
    logistics_service,
    invoice_service,
    recipe_service,
    purchase_service,
    messaging_service,
)
from services._base import db_conn

import config
from utils import customer_to_ship_to, ship_to_dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def advance_and_settle(days: int = 0, hours: float = 0) -> Dict[str, Any]:
    """Advance simulation time and let side-effects process.

    Wraps SimulationService.advance_time with side_effects=True.
    Returns the result dict including any auto-completed production orders,
    delivered shipments, expired quotes, etc.
    """
    kwargs: Dict[str, Any] = {"side_effects": True}
    if days:
        kwargs["days"] = days
    if hours:
        kwargs["hours"] = hours
    if not days and not hours:
        raise ValueError("Must specify days or hours")
    return simulation_service.advance_time(**kwargs)


def set_time(iso_time: str) -> Dict[str, Any]:
    """Jump to an absolute simulation time (no side-effects)."""
    return simulation_service.advance_time(to_time=iso_time, side_effects=False)


def current_time() -> str:
    """Return current simulation time as ISO string."""
    return simulation_service.get_current_time()


def sim_date() -> str:
    """Return current simulation date (YYYY-MM-DD)."""
    return current_time()[:10]


def future_date(days: int) -> str:
    """Return a date N days from current sim time."""
    now = datetime.fromisoformat(current_time())
    return (now + timedelta(days=days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Customer helpers
# ---------------------------------------------------------------------------

_FRENCH_FIRST_NAMES = [
    "Alexandre", "Amélie", "Antoine", "Camille", "Charlotte", "Clara",
    "Clément", "Emma", "Gabriel", "Hugo", "Jade", "Jules",
    "Léa", "Louis", "Lucas", "Manon", "Marie", "Nathan",
    "Nicolas", "Pauline", "Pierre", "Raphaël", "Sophie", "Thomas",
    "Valentin", "Zoé", "Inès", "Mathilde", "Arthur", "Chloé",
]

_FRENCH_LAST_NAMES = [
    "Bernard", "Bonnet", "Dubois", "Durand", "Fontaine", "Fournier",
    "Garnier", "Girard", "Lambert", "Laurent", "Lefebvre", "Lemaire",
    "Martin", "Mercier", "Moreau", "Morel", "Petit", "Richard",
    "Robert", "Rousseau", "Simon", "Thomas", "Dupont", "Leroy",
]

_FRENCH_CITIES = [
    ("Paris", "75001"), ("Lyon", "69001"), ("Marseille", "13001"),
    ("Toulouse", "31000"), ("Bordeaux", "33000"), ("Nantes", "44000"),
    ("Strasbourg", "67000"), ("Lille", "59000"), ("Nice", "06000"),
    ("Montpellier", "34000"), ("Rennes", "35000"), ("Grenoble", "38000"),
    ("Dijon", "21000"), ("Angers", "49000"), ("Reims", "51100"),
    ("Le Havre", "76600"), ("Tours", "37000"), ("Clermont-Ferrand", "63000"),
    ("Brest", "29200"), ("Orléans", "45000"),
]

_GERMAN_CITIES = [
    ("Berlin", "10115"), ("München", "80331"), ("Hamburg", "20095"),
    ("Frankfurt", "60311"), ("Köln", "50667"), ("Stuttgart", "70173"),
    ("Düsseldorf", "40213"), ("Dresden", "01067"), ("Nürnberg", "90402"),
    ("Leipzig", "04109"),
]

_COMPANY_TEMPLATES_FR = [
    "Jouets {last}", "Canard & {last}", "La Maison du Canard {city}",
    "{first} Distribution", "Les Canards de {city}", "Boutique {last}",
    "Cadeaux {last}", "{last} & Fils", "Comptoir du Jouet {city}",
]

_COMPANY_TEMPLATES_DE = [
    "Spielwaren {last}", "Enten-Shop {city}", "{last} GmbH",
    "{first} Handel", "Das Entenhaus {city}", "Spielzeug {last}",
]


def _random_company(first: str, last: str, city: str, country: str) -> Optional[str]:
    """Generate a plausible company name (~60% chance)."""
    if random.random() < 0.4:
        return None
    templates = _COMPANY_TEMPLATES_DE if country == "DE" else _COMPANY_TEMPLATES_FR
    template = random.choice(templates)
    return template.format(first=first, last=last, city=city)


def create_customer_batch(
    count: int,
    country: str = "FR",
    payment_terms_choices: Optional[List[int]] = None,
) -> List[str]:
    """Create a batch of customers and return their IDs.

    Args:
        count: Number of customers to create.
        country: 'FR' or 'DE'.
        payment_terms_choices: e.g. [15, 30, 45, 60]. Defaults to [30].

    Returns:
        List of customer_id strings.
    """
    payment_terms_choices = payment_terms_choices or [30]
    cities = _GERMAN_CITIES if country == "DE" else _FRENCH_CITIES
    customer_ids: List[str] = []

    for _ in range(count):
        first = random.choice(_FRENCH_FIRST_NAMES)
        last = random.choice(_FRENCH_LAST_NAMES)
        city, postal = random.choice(cities)
        company = _random_company(first, last, city, country)
        email = f"{first.lower()}.{last.lower()}@{(company or f'{last}-shop').lower().replace(' ', '').replace('&', '').replace("'", '')}.example"
        phone = f"+33 {random.randint(1,9)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}" if country == "FR" else f"+49 {random.randint(100,999)} {random.randint(1000000,9999999)}"
        terms = random.choice(payment_terms_choices)

        result = customer_service.create_customer(
            name=f"{first} {last}",
            company=company,
            email=email,
            phone=phone,
            address_line1=f"{random.randint(1,120)} {'Rue' if country == 'FR' else 'Straße'} du Commerce",
            city=city,
            postal_code=postal,
            country=country,
            payment_terms=terms,
            currency="EUR",
        )
        customer_ids.append(result["customer_id"])

    logger.info("Created %d %s customers", count, country)
    return customer_ids


# ---------------------------------------------------------------------------
# Recipe lookup
# ---------------------------------------------------------------------------

def find_recipe_for_sku(sku: str) -> Optional[str]:
    """Return the recipe_id for a given SKU, or None."""
    result = recipe_service.list_recipes(output_item_sku=sku, limit=1)
    recipes = result.get("recipes", [])
    return recipes[0]["id"] if recipes else None


# ---------------------------------------------------------------------------
# Full lifecycle helpers
# ---------------------------------------------------------------------------

def run_full_sales_cycle(
    customer_id: str,
    lines: List[Dict[str, Any]],
    ship_to: Dict[str, Any],
    requested_delivery_date: Optional[str] = None,
    pay: bool = True,
    production_advance_days: int = 2,
    shipping_advance_days: int = 2,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Drive one order through the complete lifecycle.

    quote → send → accept (creates SO) → confirm SO → produce → ship → invoice → pay.

    Args:
        customer_id: Target customer.
        lines: [{"sku": "...", "qty": N}, ...].
        ship_to: {"line1": ..., "city": ..., "postal_code": ..., "country": ...}.
        requested_delivery_date: Optional ISO date. Defaults to sim_time + 14d.
        pay: Whether to record payment at the end.
        production_advance_days: Days to advance for production to complete.
        shipping_advance_days: Days to advance for shipment to deliver.
        note: Optional note on the order.

    Returns:
        Dict with all created entity IDs.
    """
    if not requested_delivery_date:
        requested_delivery_date = future_date(14)

    result: Dict[str, Any] = {}

    # 1. Quote
    quote = quote_service.create_quote(
        customer_id=customer_id,
        requested_delivery_date=requested_delivery_date,
        ship_to=ship_to,
        lines=lines,
        note=note,
    )
    result["quote_id"] = quote["quote_id"]

    # 2. Send quote
    quote_service.send_quote(quote["quote_id"])

    # 3. Accept quote (auto-creates SO)
    accept = quote_service.accept_quote(quote["quote_id"])
    so_id = accept["sales_order_id"]
    result["sales_order_id"] = so_id

    # 4. Confirm SO
    sales_service.confirm_order(so_id)

    # 5. Production — one order per line's recipe
    mo_ids = []
    for line in lines:
        recipe_id = find_recipe_for_sku(line["sku"])
        if not recipe_id:
            logger.warning("No recipe for SKU %s — skipping production", line["sku"])
            continue
        # Create enough production orders for the requested qty
        recipe_data = recipe_service.get_recipe(recipe_id)
        output_qty = recipe_data["output_qty"]  # units per batch
        batches_needed = max(1, -(-int(line["qty"]) // output_qty))  # ceil division
        for _ in range(batches_needed):
            mo = production_service.create_order(recipe_id=recipe_id, sales_order_id=so_id, notes=f"For {so_id}")
            mo_ids.append(mo["production_order_id"])
            # Start if ready
            if mo["status"] == "ready":
                production_service.start_order(mo["production_order_id"])
    result["production_order_ids"] = mo_ids

    # 6. Advance time for production to complete
    if production_advance_days:
        advance_and_settle(days=production_advance_days)

    # 7. Shipment
    packages = [{"contents": [{"sku": l["sku"], "qty": l["qty"]} for l in lines]}]
    departure = sim_date()
    arrival = future_date(shipping_advance_days)
    ship = logistics_service.create_shipment(
        ship_from={"warehouse": config.WAREHOUSE_DEFAULT},
        ship_to=ship_to,
        planned_departure=departure,
        planned_arrival=arrival,
        packages=packages,
        reference={"type": "sales_order", "id": so_id},
    )
    result["shipment_id"] = ship["shipment_id"]

    # Dispatch (deducts stock)
    try:
        logistics_service.dispatch_shipment(ship["shipment_id"])
    except ValueError as e:
        logger.warning("Could not dispatch %s: %s", ship["shipment_id"], e)

    # 8. Advance time for delivery
    if shipping_advance_days:
        advance_and_settle(days=shipping_advance_days)

    # 9. Invoice
    inv = invoice_service.create_invoice(so_id)
    result["invoice_id"] = inv["invoice_id"]
    invoice_service.issue_invoice(inv["invoice_id"])

    # 10. Payment
    if pay:
        invoice_service.record_payment(
            invoice_id=inv["invoice_id"],
            amount=inv["total"],
            payment_method="bank_transfer",
            reference=f"VIR-{so_id}",
        )

    # 11. Complete SO
    sales_service.complete_order(so_id)

    return result


def create_sales_order_only(
    customer_id: str,
    lines: List[Dict[str, Any]],
    ship_to: Dict[str, Any],
    requested_delivery_date: Optional[str] = None,
    note: Optional[str] = None,
    confirm: bool = True,
) -> str:
    """Create a sales order via quote flow (optionally confirmed).

    Every SO must originate from a quote. This helper creates a quote,
    sends it, accepts it (which creates the SO), and optionally confirms.
    Returns the sales_order_id.
    """
    if not requested_delivery_date:
        requested_delivery_date = future_date(14)
    q = quote_service.create_quote(
        customer_id=customer_id,
        requested_delivery_date=requested_delivery_date,
        ship_to=ship_to,
        lines=lines,
        note=note,
    )
    quote_service.send_quote(q["quote_id"])
    accept = quote_service.accept_quote(q["quote_id"])
    so_id = accept["sales_order_id"]
    if confirm:
        sales_service.confirm_order(so_id)
    return so_id


def create_quote_only(
    customer_id: str,
    lines: List[Dict[str, Any]],
    ship_to: Dict[str, Any],
    requested_delivery_date: Optional[str] = None,
    note: Optional[str] = None,
    send: bool = True,
    valid_days: int = 30,
) -> str:
    """Create (and optionally send) a quote. Returns quote_id."""
    if not requested_delivery_date:
        requested_delivery_date = future_date(21)
    q = quote_service.create_quote(
        customer_id=customer_id,
        requested_delivery_date=requested_delivery_date,
        ship_to=ship_to,
        lines=lines,
        note=note,
        valid_days=valid_days,
    )
    if send:
        quote_service.send_quote(q["quote_id"])
    return q["quote_id"]


# ---------------------------------------------------------------------------
# Bulk / burst helpers
# ---------------------------------------------------------------------------

def create_demand_burst(
    sku_list: List[str],
    qty_range: Tuple[int, int],
    customer_pool: List[str],
    over_days: int,
    orders_per_day: Tuple[int, int] = (1, 3),
    full_cycle: bool = False,
) -> List[str]:
    """Scatter sales orders across a time window.

    Args:
        sku_list: SKUs to randomly pick from.
        qty_range: (min_qty, max_qty) per line.
        customer_pool: Customer IDs to distribute across.
        over_days: Number of days to spread orders over.
        orders_per_day: (min, max) orders per simulated day.
        full_cycle: If True, run full lifecycle; otherwise just create+confirm SOs.

    Returns:
        List of sales_order_ids or lifecycle result dicts.
    """
    results: List[str] = []

    for day in range(over_days):
        n_orders = random.randint(*orders_per_day)
        for _ in range(n_orders):
            cust = random.choice(customer_pool)
            # 1-3 line items per order
            n_lines = random.randint(1, min(3, len(sku_list)))
            skus = random.sample(sku_list, n_lines)
            lines = [{"sku": s, "qty": random.randint(*qty_range)} for s in skus]

            # Look up customer address for ship_to
            ship_to = get_customer_ship_to(cust)

            if full_cycle:
                r = run_full_sales_cycle(
                    customer_id=cust,
                    lines=lines,
                    ship_to=ship_to,
                    production_advance_days=0,  # don't advance per order
                    shipping_advance_days=0,
                    pay=random.random() < 0.7,
                )
                results.append(r["sales_order_id"])
            else:
                so_id = create_sales_order_only(
                    customer_id=cust,
                    lines=lines,
                    ship_to=ship_to,
                    confirm=True,
                )
                results.append(so_id)

        # Advance one day between batches
        if day < over_days - 1:
            advance_and_settle(days=1)

    logger.info("Demand burst: %d orders over %d days", len(results), over_days)
    return results


def trigger_production_for_orders(
    sales_order_ids: List[str],
    start: bool = True,
) -> List[str]:
    """Create and optionally start production orders for a list of SOs.

    Returns list of production_order_ids.
    """
    mo_ids: List[str] = []
    for so_id in sales_order_ids:
        with db_conn() as conn:
            lines = conn.execute(
                "SELECT i.sku, sol.qty FROM sales_order_lines sol "
                "JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?",
                (so_id,)
            ).fetchall()
        for line in lines:
            recipe_id = find_recipe_for_sku(line["sku"])
            if not recipe_id:
                continue
            recipe_data = recipe_service.get_recipe(recipe_id)
            batches = int(max(1, -(-int(line["qty"]) // int(recipe_data["output_qty"]))))
            for _ in range(batches):
                mo = production_service.create_order(recipe_id=recipe_id, sales_order_id=so_id, notes=f"For {so_id}")
                mo_ids.append(mo["production_order_id"])
                if start and mo["status"] == "ready":
                    production_service.start_order(mo["production_order_id"])
    return mo_ids


def create_supply_disruption(material_sku: str, delay_days: int) -> int:
    """Delay all open purchase orders for a material.

    Adds delay_days to expected_delivery for POs with status='ordered'
    matching the given material SKU.

    Returns count of POs affected.
    """
    with db_conn() as conn:
        item = conn.execute("SELECT id FROM items WHERE sku = ?", (material_sku,)).fetchone()
        if not item:
            raise ValueError(f"Material {material_sku} not found")
        count = conn.execute(
            "UPDATE purchase_orders SET expected_delivery = date(expected_delivery, ? || ' days') "
            "WHERE item_id = ? AND status = 'ordered'",
            (f"+{delay_days}", item["id"]),
        ).rowcount
        conn.commit()
    logger.info("Supply disruption: delayed %d POs for %s by %d days", count, material_sku, delay_days)
    return count


def restock_materials() -> Dict[str, Any]:
    """Trigger automatic restock check for all materials below reorder point."""
    return purchase_service.restock_materials()


def send_email(
    customer_id: str,
    subject: str,
    body: str,
    sales_order_id: Optional[str] = None,
) -> str:
    """Create and send an email. Returns email_id."""
    result = messaging_service.create_email(
        customer_id=customer_id,
        subject=subject,
        body=body,
        sales_order_id=sales_order_id,
    )
    messaging_service.send_email(result["email_id"])
    return result["email_id"]


# ---------------------------------------------------------------------------
# Customer address lookup
# ---------------------------------------------------------------------------

def get_customer_ship_to(customer_id: str) -> Dict[str, str]:
    """Look up a customer's address for use as ship_to."""
    with db_conn() as conn:
        row = conn.execute(
            "SELECT address_line1, address_line2, city, postal_code, country FROM customers WHERE id = ?",
            (customer_id,)
        ).fetchone()
    if not row:
        raise ValueError(f"Customer {customer_id} not found")
    st = customer_to_ship_to(row)
    # Ensure required fields have fallback values for scenario use
    st.setdefault("line1", "1 Rue du Commerce")
    if not st["line1"]:
        st["line1"] = "1 Rue du Commerce"
    if not st["city"]:
        st["city"] = "Paris"
    if not st["postal_code"]:
        st["postal_code"] = "75001"
    if not st["country"]:
        st["country"] = "FR"
    return st


def pick_random_lines(
    sku_pool: List[str],
    n_lines: int = 1,
    qty_range: Tuple[int, int] = (5, 30),
) -> List[Dict[str, Any]]:
    """Build random order lines from a pool of SKUs."""
    n = min(n_lines, len(sku_pool))
    skus = random.sample(sku_pool, n)
    return [{"sku": s, "qty": random.randint(*qty_range)} for s in skus]
