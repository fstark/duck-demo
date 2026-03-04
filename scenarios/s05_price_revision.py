"""S05 — Price Revision: 8 % price increase across all finished goods, Jan 2026.

Duck Inc raises prices by 8 % on all finished goods effective 1 January 2026.
Pre-existing quotes still in the pipeline carry old (lower) prices — some get
accepted, creating a visible margin dip.  New quotes at the new prices see a
higher-than-normal rejection rate (~40 %).  Order volume drops in Week 1 (price
shock) then partially recovers in Week 2.

Customer complaint emails about the increase add to the narrative.

Period: 2026-01-01 → 2026-01-15  (15 days)
"""

import logging
import random
from typing import Any, Dict, List

from scenarios.helpers import (
    advance_and_settle,
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
    sales_service,
)
from services._base import db_conn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOTAL_DAYS = 15
PRICE_INCREASE_PCT = 8  # percent

# Weekly order volumes — reduced in W1 (price shock), partial recovery W2+
WEEKLY_ORDER_VOLUME_FR = [
    (1, 2),   # W1  Jan 01–07  — price shock, lower demand
    (2, 3),   # W2  Jan 08–14  — partial recovery
    (2, 3),   # W3  Jan 15     — single day
]

WEEKLY_ORDER_VOLUME_DE = [
    (0, 1),   # W1  — German customers even more cautious
    (1, 2),   # W2  — picking back up
    (1, 2),   # W3  — single day
]

# Post-loop: new quotes at new prices with higher rejection
NEW_QUOTE_COUNT_FR = 8
NEW_QUOTE_COUNT_DE = 8
NEW_QUOTE_REJECTION_RATE = 0.40  # 40 % — higher than normal 30 %

# Email counts
PRICE_ANNOUNCEMENT_EMAILS = 6
PRICE_COMPLAINT_EMAILS = 10


# ---------------------------------------------------------------------------
# SKU pool builder
# ---------------------------------------------------------------------------

def _winter_pool(core_skus: List[str], christmas_skus: List[str]) -> List[str]:
    """Core (1×) + Christmas leftovers (1×) — no seasonal uplift."""
    pool = list(core_skus)
    pool.extend(christmas_skus)  # de-weighted from S04's 3×
    return pool


def _german_winter_pool(
    core_skus: List[str],
    german_skus: List[str],
    christmas_skus: List[str],
) -> List[str]:
    """Core (1×) + German (2×) + Christmas (1×)."""
    pool = list(core_skus)
    for sku in german_skus:
        pool.extend([sku] * 2)
    pool.extend(christmas_skus)
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
    qty_range: tuple = (5, 20),
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
# Email templates
# ---------------------------------------------------------------------------

PRICE_ANNOUNCEMENT_TEMPLATES = [
    ("Important: 2026 Price Update",
     "Dear {name},\n\nWe are writing to inform you that effective 1 January "
     "2026, Duck Inc will be implementing an 8% price adjustment across our "
     "entire product range. This reflects increased raw material costs and "
     "our continued investment in product quality.\n\nExisting confirmed "
     "orders will not be affected. Please contact us if you have any "
     "questions.\n\nBest regards,\nDuck Inc Sales Team"),
    ("Neue Preise ab Januar 2026",
     "Sehr geehrte(r) {name},\n\nWir möchten Sie darüber informieren, dass "
     "Duck Inc ab dem 1. Januar 2026 eine Preisanpassung von 8% auf unser "
     "gesamtes Sortiment vornimmt. Diese Maßnahme ist notwendig aufgrund "
     "gestiegener Rohstoffkosten.\n\nBereits bestätigte Bestellungen sind "
     "davon nicht betroffen.\n\nMit freundlichen Grüßen,\nDuck Inc Vertrieb"),
    ("Duck Inc — Price Adjustment Notice",
     "Dear {name},\n\nAs we begin 2026, we want to be transparent about a "
     "necessary price adjustment. Starting January 1st, our prices will "
     "increase by 8% to reflect current market conditions.\n\nWe value your "
     "partnership and are committed to maintaining the quality you expect. "
     "Please don't hesitate to reach out to discuss volume pricing.\n\n"
     "Warm regards,\nDuck Inc Commercial Team"),
]

PRICE_COMPLAINT_TEMPLATES = [
    ("Regarding your recent price increase",
     "Dear Duck Inc,\n\nWe received your notice about the 8% price increase "
     "and frankly, we are disappointed. Our budget for Q1 2026 was finalized "
     "months ago and this increase puts significant pressure on our margins.\n\n"
     "Can we discuss volume-based discounts to offset this increase?\n\n"
     "Regards,\n{name}"),
    ("We need to discuss the new pricing for 2026",
     "Hello,\n\nThe 8% price increase is quite steep. We have been loyal "
     "customers and would appreciate some form of transition period or "
     "graduated pricing. Otherwise we may need to evaluate alternatives.\n\n"
     "Best regards,\n{name}"),
    ("Preiserhöhung — Bitte um Erklärung",
     "Sehr geehrtes Duck Inc Team,\n\nDie angekündigte Preiserhöhung von 8% "
     "ist für uns schwer nachvollziehbar. Könnten Sie uns bitte die Gründe "
     "genauer erklären? Wir müssen unsere eigenen Preise entsprechend "
     "anpassen und brauchen eine detaillierte Begründung.\n\nMit freundlichen "
     "Grüßen,\n{name}"),
    ("Can we negotiate volume pricing at the old rates?",
     "Dear team,\n\nWe understand costs go up, but 8% is a significant jump. "
     "We'd like to propose a volume commitment in exchange for maintaining "
     "closer to the 2025 pricing. We currently order {qty} units per month "
     "and could increase that by 20%.\n\nLet's discuss.\n{name}"),
    ("Budget impact of price increase — order {so_id}",
     "Dear Duck Inc,\n\nWith reference to order {so_id}, we notice the new "
     "pricing is already in effect. Our procurement team has flagged this as "
     "a concern for our Q1 planning. Please advise if there are any loyalty "
     "discounts available.\n\nThank you,\n{name}"),
    ("Our Q1 budget doesn't accommodate the 8% increase",
     "Hello,\n\nWe've reviewed the new pricing and unfortunately it exceeds "
     "our allocated budget for Q1 2026. We may need to reduce order volumes "
     "or delay purchases unless we can find a middle ground.\n\n"
     "Please let us know what options are available.\n\nKind regards,\n{name}"),
]


# ---------------------------------------------------------------------------
# Scenario entry point
# ---------------------------------------------------------------------------

def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the Price Revision scenario (Jan 1–15, 2026).

    Applies an 8% price increase on all finished goods.  Accepts some
    pre-existing old-price quotes (margin dip), creates new orders at the
    higher prices with reduced volume (price shock), and sends customer
    complaint emails about the increase.
    """
    random.seed(505)
    fr_customer_ids: List[str] = [
        cid for cid in ctx["customer_ids"]
        if cid not in ctx.get("de_customer_ids", [])
    ]
    de_customer_ids: List[str] = ctx.get("de_customer_ids", [])
    all_customer_ids: List[str] = ctx["customer_ids"]
    core_skus: List[str] = ctx.get("core_skus", [])
    german_skus: List[str] = ctx.get("german_skus", [])
    christmas_skus: List[str] = ctx.get("christmas_skus", [])

    # Jump to Jan 1st
    set_time("2026-01-01 08:00:00")

    logger.info("=== S05 Price Revision: Jan 2026 (daily loop, %d days) ===",
                TOTAL_DAYS)

    # ------------------------------------------------------------------
    # Phase 0: Apply 8 % price increase
    # ------------------------------------------------------------------
    with db_conn() as conn:
        # Snapshot old prices for logging & downstream context
        old_rows = conn.execute(
            "SELECT id, sku, unit_price FROM items WHERE type = 'finished_good'"
        ).fetchall()
        old_prices: Dict[str, float] = {r["id"]: float(r["unit_price"]) for r in old_rows}

        # Apply the increase
        conn.execute(
            "UPDATE items SET unit_price = ROUND(unit_price * ?, 2) "
            "WHERE type = 'finished_good'",
            (1 + PRICE_INCREASE_PCT / 100,),
        )
        conn.commit()

        items_affected = len(old_prices)
        sample = conn.execute(
            "SELECT sku, unit_price FROM items WHERE type = 'finished_good' "
            "ORDER BY sku LIMIT 5"
        ).fetchall()

    activity_service.log_activity(
        "scenario", "catalog", "price_revision.applied", "item", None,
        {"pct": PRICE_INCREASE_PCT, "items_affected": items_affected},
    )

    logger.info("Applied +%d%% price increase to %d finished goods",
                PRICE_INCREASE_PCT, items_affected)
    for s in sample:
        # Look up old price by matching row SKU → item ID → old_prices dict
        item_id = next((r["id"] for r in old_rows if r["sku"] == s["sku"]), None)
        old_p = old_prices.get(item_id, 0)
        logger.info("  %s: %.2f → %.2f", s["sku"], old_p, s["unit_price"])

    # ------------------------------------------------------------------
    # Phase 0b: Accept pre-existing old-price quotes
    # ------------------------------------------------------------------
    with db_conn() as conn:
        sent_quotes = conn.execute(
            "SELECT id FROM quotes WHERE status = 'sent'"
        ).fetchall()
    sent_quote_ids = [r["id"] for r in sent_quotes]
    random.shuffle(sent_quote_ids)

    old_price_so_ids: List[str] = []
    accepted_old = 0
    rejected_old = 0

    for qid in sent_quote_ids:
        if random.random() < 0.65:
            # Accept at old price — margin dip
            try:
                result = quote_service.accept_quote(qid)
                so_id = result["sales_order_id"]
                old_price_so_ids.append(so_id)
                sales_service.confirm_order(so_id)
                activity_service.log_activity(
                    "scenario", "sales", "quote.accepted_old_price",
                    "quote", qid, {"sales_order_id": so_id},
                )
                accepted_old += 1
            except Exception as e:
                logger.debug("Old-price quote accept failed (%s): %s", qid, e)
        else:
            # Let them expire or reject
            try:
                quote_service.reject_quote(qid, reason=random.choice([
                    "Budget already allocated",
                    "Switching supplier",
                    "Project cancelled",
                ]))
                rejected_old += 1
            except Exception as e:
                logger.debug("Old-price quote reject failed (%s): %s", qid, e)

    logger.info("Old-price quotes: %d accepted (→ SOs), %d rejected, %d total",
                accepted_old, rejected_old, len(sent_quote_ids))

    # ------------------------------------------------------------------
    # Phase 0c: Price-announcement emails
    # ------------------------------------------------------------------
    logger.info("Sending price-announcement emails...")
    announcement_sample = random.sample(
        all_customer_ids,
        min(PRICE_ANNOUNCEMENT_EMAILS, len(all_customer_ids)),
    )
    with db_conn() as conn:
        for cid in announcement_sample:
            cust = conn.execute(
                "SELECT name FROM customers WHERE id = ?", (cid,)
            ).fetchone()
            if not cust:
                continue
            t = random.choice(PRICE_ANNOUNCEMENT_TEMPLATES)
            subj = t[0].format(name=cust["name"])
            body = t[1].format(name=cust["name"])
            try:
                send_email(customer_id=cid, subject=subj, body=body)
            except Exception as e:
                logger.warning("Announcement email failed: %s", e)

    # ------------------------------------------------------------------
    # Build SKU pools & tracking structures
    # ------------------------------------------------------------------
    fr_sku_pool = _winter_pool(core_skus, christmas_skus)
    de_sku_pool = _german_winter_pool(core_skus, german_skus, christmas_skus)

    logger.info("FR pool: %d weighted SKUs, DE pool: %d weighted SKUs",
                len(fr_sku_pool), len(de_sku_pool))

    # Carry forward prior scenario SO IDs for continued shipping/invoicing
    prior_so_keys = ["s01_so_ids", "s02_so_ids", "s03_so_ids", "s04_so_ids"]
    trackable_so_ids: List[str] = []
    for key in prior_so_keys:
        trackable_so_ids.extend(ctx.get(key, []))
    trackable_so_ids.extend(old_price_so_ids)
    _completed_so_ids: set = set()

    all_so_ids: List[str] = list(old_price_so_ids)  # include old-price SOs
    fr_so_ids: List[str] = []
    de_so_ids: List[str] = []

    # Accumulators for weekly summary
    wk_sos_fr = wk_sos_de = 0
    wk_mos = wk_shipped = wk_invoiced = wk_restocked = wk_received = 0
    wk_replan = 0

    # ------------------------------------------------------------------
    # Daily loop (15 days)
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

            day_fr_sos = _create_day_orders(
                fr_customer_ids, fr_sku_pool, fr_opd,
            )
            fr_so_ids.extend(day_fr_sos)
            wk_sos_fr += len(day_fr_sos)

            # ----- Late morning (11:00) — German sales orders -----
            set_day_time(11)

            day_de_sos = _create_day_orders(
                de_customer_ids, de_sku_pool, de_opd,
            ) if de_customer_ids else []
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

            # 6. Restock raw materials
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
    # Post-loop: New quotes at new prices (higher rejection)
    # ------------------------------------------------------------------
    logger.info("Creating new quotes at new prices...")
    new_quote_ids: List[str] = []
    quote_sku_pool = core_skus + christmas_skus + german_skus

    with db_conn():
        # French quotes
        for _ in range(NEW_QUOTE_COUNT_FR):
            cust = random.choice(fr_customer_ids)
            ship_to = get_customer_ship_to(cust)
            lines = pick_random_lines(
                core_skus + christmas_skus,
                n_lines=random.randint(1, 3),
                qty_range=(5, 30),
            )
            try:
                q_id = create_quote_only(
                    customer_id=cust, lines=lines, ship_to=ship_to,
                    send=True, valid_days=30,
                )
                new_quote_ids.append(q_id)
                if random.random() < NEW_QUOTE_REJECTION_RATE:
                    quote_service.reject_quote(q_id, reason=random.choice([
                        "Price too high after increase",
                        "Budget constraints — new pricing",
                        "Evaluating alternative suppliers",
                        "Order volume reduced due to costs",
                    ]))
            except Exception as e:
                logger.warning("FR new quote failed: %s", e)

        # German quotes
        for _ in range(NEW_QUOTE_COUNT_DE):
            cust = random.choice(de_customer_ids) if de_customer_ids else random.choice(fr_customer_ids)
            ship_to = get_customer_ship_to(cust)
            lines = pick_random_lines(
                german_skus + christmas_skus + core_skus[:5],
                n_lines=random.randint(1, 2),
                qty_range=(5, 25),
            )
            try:
                q_id = create_quote_only(
                    customer_id=cust, lines=lines, ship_to=ship_to,
                    send=True, valid_days=30,
                )
                new_quote_ids.append(q_id)
                if random.random() < NEW_QUOTE_REJECTION_RATE:
                    quote_service.reject_quote(q_id, reason=random.choice([
                        "Preis zu hoch nach Erhöhung",
                        "Budget reicht nicht aus",
                        "Suchen alternativen Anbieter",
                        "Price increase not acceptable",
                    ]))
            except Exception as e:
                logger.warning("DE new quote failed: %s", e)

    logger.info("Created %d new quotes at new prices", len(new_quote_ids))

    # ------------------------------------------------------------------
    # Customer complaint emails about the price increase
    # ------------------------------------------------------------------
    logger.info("Creating price-complaint emails...")
    with db_conn() as conn:
        # Pick recent SOs for email context
        recent_sos = conn.execute(
            "SELECT so.id, so.customer_id, c.name "
            "FROM sales_orders so "
            "JOIN customers c ON so.customer_id = c.id "
            "WHERE so.created_at >= '2026-01-01' "
            "ORDER BY RANDOM() LIMIT ?",
            (PRICE_COMPLAINT_EMAILS,),
        ).fetchall()

        # Fall back to any customers if not enough recent SOs
        if len(recent_sos) < PRICE_COMPLAINT_EMAILS:
            extra_custs = conn.execute(
                "SELECT c.id as customer_id, c.name "
                "FROM customers c "
                "ORDER BY RANDOM() LIMIT ?",
                (PRICE_COMPLAINT_EMAILS - len(recent_sos),),
            ).fetchall()
        else:
            extra_custs = []

    for row in recent_sos:
        t = random.choice(PRICE_COMPLAINT_TEMPLATES)
        subj = t[0].format(
            name=row["name"], so_id=row["id"], qty=random.randint(50, 200),
        )
        body = t[1].format(
            name=row["name"], so_id=row["id"], qty=random.randint(50, 200),
        )
        try:
            send_email(
                customer_id=row["customer_id"], subject=subj,
                body=body, sales_order_id=row["id"],
            )
        except Exception as e:
            logger.warning("Complaint email failed: %s", e)

    for row in extra_custs:
        t = random.choice(PRICE_COMPLAINT_TEMPLATES)
        subj = t[0].format(
            name=row["name"], so_id="(pending)", qty=random.randint(50, 200),
        )
        body = t[1].format(
            name=row["name"], so_id="(pending)", qty=random.randint(50, 200),
        )
        try:
            send_email(customer_id=row["customer_id"], subject=subj, body=body)
        except Exception as e:
            logger.warning("Complaint email failed: %s", e)

    # ------------------------------------------------------------------
    # Short settle (1 day)
    # ------------------------------------------------------------------
    advance_and_settle(days=1)

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

        # Price verification
        price_sample = conn.execute(
            "SELECT sku, unit_price FROM items WHERE type = 'finished_good' "
            "ORDER BY sku LIMIT 3"
        ).fetchall()

    logger.info("=== S05 Complete ===")
    for k, v in counts.items():
        logger.info("  %-22s %d", k, v)
    logger.info("  MOs still waiting:   %d", waiting_mos)
    logger.info("  SOs still confirmed: %d", confirmed_sos)
    logger.info("  Old-price SOs:       %d", len(old_price_so_ids))
    logger.info("  New FR SOs:          %d", len(fr_so_ids))
    logger.info("  New DE SOs:          %d", len(de_so_ids))
    logger.info("  New quotes:          %d", len(new_quote_ids))
    logger.info("  Price samples:       %s",
                ", ".join(f"{r['sku']}={r['unit_price']:.2f}" for r in price_sample))
    logger.info("  Sim time:            %s", current_time())

    return {
        "s05_so_ids": all_so_ids,
        "old_prices": old_prices,
        "price_increase_pct": PRICE_INCREASE_PCT,
        "s05_sent_quotes": [q for q in new_quote_ids],
    }
