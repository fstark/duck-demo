"""S04 — Geo Expansion: Duck Inc expands into Germany, Dec 2025.

Duck Inc launches in the German market with 12 new B2B customers.  Lederhosen
and Oktoberfest ducks are promoted alongside a Christmas seasonal push (Santa,
Snowman, Reindeer, Elf, Gingerbread).  French customers also see a Christmas
wave.  Cross-border shipments (country="DE") become visible in logistics data.
New revenue stream by country appears in analytics.

Materials flow normally (PVC supply restored post-S03), so production runs
smoothly — the contrast with the November dip is part of the story.

Period: 2025-12-01 → 2025-12-31  (31 days)
"""

import logging
import random
from typing import Any, Dict, List

from scenarios.helpers import (
    advance_and_settle,
    create_customer_batch,
    create_quote_only,
    create_sales_order_only,
    current_time,
    future_date,
    get_customer_ship_to,
    pick_random_lines,
    restock_materials,
    send_email,
    set_day_time,
    set_time,
    sim_date,
    trigger_production_for_orders,
)
from services import (
    activity_service,
    fulfillment_service,
    mrp_service,
    quote_service,
)
from services._base import db_conn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOTAL_DAYS = 31

# Germany-themed SKUs (already in catalog from base_setup)
GERMAN_SKUS = [
    "LEDERHOSEN-DUCK-20CM",
    "OKTOBERFEST-DUCK-18CM",
]

# Christmas seasonal SKUs
CHRISTMAS_SKUS = [
    "SANTA-DUCK-20CM",
    "SNOWMAN-DUCK-18CM",
    "REINDEER-DUCK-15CM",
    "ELF-DUCK-12CM",
    "GINGERBREAD-DUCK-15CM",
]

# New German customers
DE_CUSTOMER_COUNT = 12
DE_PAYMENT_TERMS = [45, 60]

# French order volume per week (Christmas ramp in W3)
WEEKLY_ORDER_VOLUME_FR = [
    (2, 3),   # W1  Dec 01–07  — normal
    (2, 4),   # W2  Dec 08–14  — building
    (3, 5),   # W3  Dec 15–21  — Christmas rush
    (3, 4),   # W4  Dec 22–28  — last-minute Christmas
    (2, 3),   # W5  Dec 29–31  — post-Christmas cool-down
]

# German order volume per week (starts cautious, ramps for Christmas)
WEEKLY_ORDER_VOLUME_DE = [
    (1, 2),   # W1  launch week
    (2, 3),   # W2  picking up
    (2, 4),   # W3  Christmas rush
    (2, 3),   # W4  last-minute Christmas
    (1, 2),   # W5  post-Christmas
]


# ---------------------------------------------------------------------------
# SKU pool builders
# ---------------------------------------------------------------------------

def _french_christmas_pool(core_skus: List[str]) -> List[str]:
    """Core (1×) + Christmas (3×) — seasonal uplift for French market."""
    pool = list(core_skus)
    for sku in CHRISTMAS_SKUS:
        pool.extend([sku] * 3)
    return pool


def _german_sku_pool(core_skus: List[str]) -> List[str]:
    """Core (1×) + German (4×) + Christmas (3×) — German launch mix."""
    pool = list(core_skus)
    for sku in GERMAN_SKUS:
        pool.extend([sku] * 4)
    for sku in CHRISTMAS_SKUS:
        pool.extend([sku] * 3)
    return pool


def _orders_per_day_for_day(day_index: int, is_de: bool) -> tuple:
    """Return the (min, max) order range for a given day index (0-based)."""
    table = WEEKLY_ORDER_VOLUME_DE if is_de else WEEKLY_ORDER_VOLUME_FR
    week_index = min(day_index // 7, len(table) - 1)
    return table[week_index]


# ---------------------------------------------------------------------------
# Daily helpers
# ---------------------------------------------------------------------------

def _create_day_orders(
    customer_ids: List[str],
    sku_pool: List[str],
    orders_per_day: tuple,
    qty_range: tuple = (5, 25),
) -> List[str]:
    """Create confirmed SOs for a single day. Returns list of SO IDs."""
    so_ids: List[str] = []
    n = random.randint(*orders_per_day)
    for _ in range(n):
        cust = random.choice(customer_ids)
        ship_to = get_customer_ship_to(cust)
        n_lines = random.choices([1, 2, 3], weights=[40, 40, 20])[0]
        lines = pick_random_lines(sku_pool, n_lines=n_lines, qty_range=qty_range)
        try:
            so_id = create_sales_order_only(
                customer_id=cust, lines=lines, ship_to=ship_to, confirm=True,
            )
            so_ids.append(so_id)
        except Exception as e:
            logger.warning("SO creation failed: %s", e)
    return so_ids


def _log_daily_status(day_index: int) -> None:
    """Log a snapshot of entity status counts for the current sim day."""
    with db_conn() as conn:
        so_counts = {r["status"]: r["cnt"] for r in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM sales_orders GROUP BY status"
        ).fetchall()}
        mo_counts = {r["status"]: r["cnt"] for r in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM production_orders GROUP BY status"
        ).fetchall()}
        ship_counts = {r["status"]: r["cnt"] for r in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM shipments GROUP BY status"
        ).fetchall()}
        inv_counts = {r["status"]: r["cnt"] for r in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM invoices GROUP BY status"
        ).fetchall()}
        po_counts = {r["status"]: r["cnt"] for r in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM purchase_orders GROUP BY status"
        ).fetchall()}

    def _fmt(counts: dict) -> str:
        return " ".join(f"{s}={n}" for s, n in sorted(counts.items()))

    logger.info(
        "  [Day %d  %s]  SO: %s | MO: %s | Ship: %s | Inv: %s | PO: %s",
        day_index + 1, sim_date(),
        _fmt(so_counts), _fmt(mo_counts), _fmt(ship_counts),
        _fmt(inv_counts), _fmt(po_counts),
    )


# ---------------------------------------------------------------------------
# Scenario entry point
# ---------------------------------------------------------------------------

def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the Geo Expansion scenario (Dec 2025).

    Creates 12 German customers, then runs a 31-day daily loop with two
    parallel order streams (French + German).  Christmas seasonal SKUs are
    promoted in both markets; German-themed ducks are heavily weighted in
    the DE stream.  Supply chain runs normally (post-S03 recovery).
    """
    random.seed(404)
    fr_customer_ids: List[str] = ctx["customer_ids"]
    core_skus: List[str] = ctx.get("core_skus", [])

    # Jump to Dec 1st
    set_time("2025-12-01 08:00:00")

    logger.info("=== S04 Geo Expansion: Dec 2025 (daily loop, %d days) ===",
                TOTAL_DAYS)

    # ------------------------------------------------------------------
    # Phase 0: Create German customers
    # ------------------------------------------------------------------
    de_customer_ids = create_customer_batch(
        DE_CUSTOMER_COUNT,
        country="DE",
        payment_terms_choices=DE_PAYMENT_TERMS,
    )
    # Add DE customers to the master list for downstream scenarios
    all_customer_ids = list(fr_customer_ids) + de_customer_ids

    logger.info("Created %d German customers (IDs: %s … %s)",
                len(de_customer_ids), de_customer_ids[0], de_customer_ids[-1])

    # Build SKU pools
    fr_sku_pool = _french_christmas_pool(core_skus)
    de_sku_pool = _german_sku_pool(core_skus)

    logger.info("FR pool: %d weighted SKUs, DE pool: %d weighted SKUs",
                len(fr_sku_pool), len(de_sku_pool))

    # Carry forward prior scenario SO IDs for continued shipping/invoicing
    s01_so_ids: List[str] = ctx.get("s01_so_ids", [])
    s02_so_ids: List[str] = ctx.get("s02_so_ids", [])
    s03_so_ids: List[str] = ctx.get("s03_so_ids", [])
    trackable_so_ids: List[str] = list(s01_so_ids) + list(s02_so_ids) + list(s03_so_ids)
    _completed_so_ids: set = set()

    all_so_ids: List[str] = []       # SOs created in this scenario
    fr_so_ids: List[str] = []
    de_so_ids: List[str] = []

    # Accumulators for weekly summary logging
    wk_sos_fr = wk_sos_de = 0
    wk_mos = wk_shipped = wk_invoiced = wk_restocked = wk_received = 0
    wk_replan = 0

    # ------------------------------------------------------------------
    # Daily loop
    # ------------------------------------------------------------------
    for day in range(TOTAL_DAYS):
        fr_opd = _orders_per_day_for_day(day, is_de=False)
        de_opd = _orders_per_day_for_day(day, is_de=True)
        week_num = day // 7 + 1

        # Log weekly summary at week boundaries
        if day > 0 and day % 7 == 0:
            logger.info(
                "  Week %d summary — FR SOs: %d, DE SOs: %d, MOs: %d "
                "(replan: %d), Shipped: %d, Invoiced: %d, Restocked: %d POs, "
                "Received: %d POs",
                week_num - 1, wk_sos_fr, wk_sos_de, wk_mos, wk_replan,
                wk_shipped, wk_invoiced, wk_restocked, wk_received,
            )
            wk_sos_fr = wk_sos_de = wk_mos = wk_shipped = wk_invoiced = 0
            wk_restocked = wk_received = wk_replan = 0

        with db_conn():  # reuse one connection per day

            # ----- Morning (08:00) — Receive & start production -----
            set_day_time(8)

            # 1. Receive POs that have arrived
            n_rcv = fulfillment_service.receive_due_pos(sim_date())
            wk_received += n_rcv

            # 2. Start any MOs that are ready
            fulfillment_service.start_ready_mos()

            # 2b. MRP re-plan
            n_replan = mrp_service.replan_unfulfilled_orders()
            wk_replan += n_replan
            wk_mos += n_replan

            # 2c. Restock materials after re-plan
            if n_replan:
                try:
                    rs2 = restock_materials()
                    wk_restocked += rs2.get("purchase_orders_created", 0)
                except Exception:
                    pass

            # ----- Mid-morning (10:00) — French sales orders -----
            set_day_time(10)

            day_fr_sos = _create_day_orders(fr_customer_ids, fr_sku_pool, fr_opd)
            fr_so_ids.extend(day_fr_sos)
            wk_sos_fr += len(day_fr_sos)

            # ----- Late morning (11:00) — German sales orders -----
            set_day_time(11)

            day_de_sos = _create_day_orders(de_customer_ids, de_sku_pool, de_opd)
            de_so_ids.extend(day_de_sos)
            wk_sos_de += len(day_de_sos)

            # Combine today's SOs
            day_sos = day_fr_sos + day_de_sos
            all_so_ids.extend(day_sos)
            trackable_so_ids.extend(day_sos)

            # 4. Trigger + start production for new orders
            mo_ids = trigger_production_for_orders(day_sos, start=True)
            wk_mos += len(mo_ids)

            # ----- Afternoon (14:00) — Ship & restock -----
            set_day_time(14)

            # 5. Ship orders with available FG stock
            pending_ship = [sid for sid in trackable_so_ids
                           if sid not in _completed_so_ids]
            ship_ids = fulfillment_service.ship_ready_orders(
                pending_ship, sim_date_fn=sim_date, future_date_fn=future_date,
            )
            wk_shipped += len(ship_ids)

            # 6. Restock raw materials (runs normally — supply restored)
            try:
                rs = restock_materials()
                n_po = rs.get("purchase_orders_created", 0)
                wk_restocked += n_po
            except Exception as e:
                logger.debug("Restock skipped: %s", e)

            # ----- Late afternoon (16:00) — Invoice & payment -----
            set_day_time(16)

            # 7. Invoice shipped orders
            pending_inv = [sid for sid in trackable_so_ids
                          if sid not in _completed_so_ids]
            inv_n = fulfillment_service.invoice_shipped_orders(
                pending_inv, completed_set=_completed_so_ids,
            )
            wk_invoiced += inv_n

            # ----- End of day — advance clock by 1 day -----
            set_day_time(18)
            advance_and_settle(hours=14)  # 18:00 → next day 08:00

        # Log daily status snapshot (every day for first week, then weekly)
        if day < 7 or day % 7 == 6:
            _log_daily_status(day)

    # Final weekly summary
    logger.info(
        "  Week %d summary — FR SOs: %d, DE SOs: %d, MOs: %d (replan: %d), "
        "Shipped: %d, Invoiced: %d, Restocked: %d POs, Received: %d POs",
        (TOTAL_DAYS - 1) // 7 + 1, wk_sos_fr, wk_sos_de, wk_mos,
        wk_replan, wk_shipped, wk_invoiced, wk_restocked, wk_received,
    )

    # ------------------------------------------------------------------
    # Welcome & onboarding emails to German customers
    # ------------------------------------------------------------------
    logger.info("Creating welcome emails for German customers...")
    welcome_templates = [
        ("Willkommen bei Duck Inc!",
         "Sehr geehrte(r) {name},\n\nWir freuen uns, Sie als neuen Kunden "
         "begrüßen zu dürfen! Duck Inc liefert jetzt auch nach Deutschland. "
         "Entdecken Sie unsere exklusiven Lederhosen- und Oktoberfest-Enten "
         "sowie unser gesamtes Sortiment.\n\nMit freundlichen Grüßen,\n"
         "Duck Inc Vertriebsteam"),
        ("Your first order has shipped — {so_id}",
         "Dear {name},\n\nGreat news! Your first order {so_id} with Duck Inc "
         "is on its way to Germany. You can expect delivery within the next "
         "few days.\n\nBest regards,\nDuck Inc Logistics"),
        ("Frohe Weihnachten from Duck Inc 🎄",
         "Sehr geehrte(r) {name},\n\nWir wünschen Ihnen und Ihrem Team frohe "
         "Weihnachten! Vielen Dank, dass Sie sich für Duck Inc entschieden "
         "haben. Wir freuen uns auf die Zusammenarbeit im neuen Jahr.\n\n"
         "Beste Grüße,\nDuck Inc Team"),
    ]
    with db_conn() as conn:
        de_so_sample = conn.execute(
            "SELECT so.id, so.customer_id, c.name "
            "FROM sales_orders so "
            "JOIN customers c ON so.customer_id = c.id "
            "WHERE c.country = 'DE' "
            "ORDER BY RANDOM() LIMIT 8",
        ).fetchall()
    for row in de_so_sample:
        t = random.choice(welcome_templates)
        subj = t[0].format(so_id=row["id"], name=row["name"])
        body = t[1].format(so_id=row["id"], name=row["name"])
        try:
            send_email(customer_id=row["customer_id"], subject=subj,
                       body=body, sales_order_id=row["id"])
        except Exception as e:
            logger.warning("Welcome email failed: %s", e)

    # ------------------------------------------------------------------
    # Christmas inquiry emails (FR + DE customers)
    # ------------------------------------------------------------------
    logger.info("Creating Christmas inquiry emails...")
    inquiry_templates = [
        ("Will my order {so_id} arrive before Christmas?",
         "Dear Duck Inc,\n\nI placed order {so_id} and Christmas is fast "
         "approaching. Will the delivery arrive in time for the holidays? "
         "This is for our Christmas display and we cannot afford delays."
         "\n\nThank you,\n{name}"),
        ("Delivery tracking for holiday order {so_id}",
         "Hello,\n\nCould you provide a tracking update for order {so_id}? "
         "We need these items for our Christmas stock and our customers are "
         "already asking.\n\nBest regards,\n{name}"),
        ("Urgent: Christmas deadline for {so_id}",
         "Dear team,\n\nOrder {so_id} absolutely must arrive before December "
         "24th. Please confirm that this will happen or we will need to make "
         "alternative arrangements.\n\nRegards,\n{name}"),
        ("Wann wird Bestellung {so_id} geliefert?",
         "Sehr geehrtes Duck Inc Team,\n\nIch möchte mich nach dem Status "
         "meiner Bestellung {so_id} erkundigen. Weihnachten steht vor der "
         "Tür und wir brauchen die Ware dringend.\n\nMit freundlichen "
         "Grüßen,\n{name}"),
    ]
    with db_conn() as conn:
        if all_so_ids:
            delayed = conn.execute(
                "SELECT so.id, so.customer_id, c.name "
                "FROM sales_orders so "
                "JOIN customers c ON so.customer_id = c.id "
                "WHERE so.status = 'confirmed' "
                "AND so.id IN ({}) "
                "ORDER BY RANDOM() LIMIT 8".format(
                    ",".join("?" for _ in all_so_ids)
                ),
                all_so_ids,
            ).fetchall()
        else:
            delayed = []
    for row in delayed:
        t = random.choice(inquiry_templates)
        subj = t[0].format(so_id=row["id"], name=row["name"])
        body = t[1].format(so_id=row["id"], name=row["name"])
        try:
            send_email(customer_id=row["customer_id"], subject=subj,
                       body=body, sales_order_id=row["id"])
        except Exception as e:
            logger.warning("Inquiry email failed: %s", e)

    # ------------------------------------------------------------------
    # Standalone quotes (mix of FR Christmas + DE expansion)
    # ------------------------------------------------------------------
    logger.info("Creating standalone quotes...")
    with db_conn():
        # 5 quotes for German customers
        for _ in range(5):
            cust = random.choice(de_customer_ids)
            ship_to = get_customer_ship_to(cust)
            sku_choice = GERMAN_SKUS + CHRISTMAS_SKUS
            lines = pick_random_lines(sku_choice, n_lines=random.randint(1, 2),
                                      qty_range=(10, 40))
            try:
                q_id = create_quote_only(
                    customer_id=cust, lines=lines, ship_to=ship_to,
                    send=True, valid_days=30,
                )
                # ~30% rejection
                if random.random() < 0.3:
                    quote_service.reject_quote(q_id, reason=random.choice([
                        "Preis zu hoch", "Anderes Angebot gefunden",
                        "Projekt verschoben", "Budget constraints",
                    ]))
            except Exception as e:
                logger.warning("DE quote failed: %s", e)

        # 5 quotes for French customers
        for _ in range(5):
            cust = random.choice(fr_customer_ids)
            ship_to = get_customer_ship_to(cust)
            lines = pick_random_lines(CHRISTMAS_SKUS, n_lines=random.randint(1, 2),
                                      qty_range=(10, 40))
            try:
                q_id = create_quote_only(
                    customer_id=cust, lines=lines, ship_to=ship_to,
                    send=True, valid_days=30,
                )
                if random.random() < 0.3:
                    quote_service.reject_quote(q_id, reason=random.choice([
                        "Price too high", "Found a better offer",
                        "Project postponed", "Budget constraints",
                    ]))
            except Exception as e:
                logger.warning("FR quote failed: %s", e)

    # ------------------------------------------------------------------
    # Short settle (2 days — let in-flight deliveries arrive)
    # ------------------------------------------------------------------
    advance_and_settle(days=2)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    with db_conn() as conn:
        counts = {}
        for tbl in ["sales_orders", "production_orders", "invoices", "quotes",
                     "shipments", "purchase_orders", "emails", "payments"]:
            counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]

        waiting_mos = conn.execute(
            "SELECT COUNT(*) FROM production_orders WHERE status = 'waiting'"
        ).fetchone()[0]
        confirmed_sos = conn.execute(
            "SELECT COUNT(*) FROM sales_orders WHERE status = 'confirmed'"
        ).fetchone()[0]

        # Country breakdown
        de_sos = conn.execute(
            "SELECT COUNT(*) FROM sales_orders so "
            "JOIN customers c ON so.customer_id = c.id "
            "WHERE c.country = 'DE'"
        ).fetchone()[0]
        de_customers = conn.execute(
            "SELECT COUNT(*) FROM customers WHERE country = 'DE'"
        ).fetchone()[0]

    logger.info("=== S04 Complete ===")
    for k, v in counts.items():
        logger.info("  %-22s %d", k, v)
    logger.info("  MOs still waiting:   %d", waiting_mos)
    logger.info("  SOs still confirmed: %d", confirmed_sos)
    logger.info("  DE customers:        %d", de_customers)
    logger.info("  DE sales orders:     %d", de_sos)
    logger.info("  FR SOs this period:  %d", len(fr_so_ids))
    logger.info("  DE SOs this period:  %d", len(de_so_ids))
    logger.info("  Sim time:            %s", current_time())

    return {
        "s04_so_ids": all_so_ids,
        "de_customer_ids": de_customer_ids,
        "customer_ids": all_customer_ids,
        "german_skus": GERMAN_SKUS,
        "christmas_skus": CHRISTMAS_SKUS,
    }
