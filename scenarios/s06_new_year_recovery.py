"""S06 — New Year Recovery: Operations normalize, backlog clears, Feb 2026.

After the price shock of S05, demand gradually recovers to normal levels.
Material supply is fully restored (post-S03 disruption long resolved).
Production backlog from previous months clears.  Overdue invoices get paid.
The database reaches a clean, demo-ready state suitable for live demo.

Period: 2026-01-16 → 2026-02-28  (44 days)
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
    invoice_service,
    mrp_service,
    quote_service,
    sales_service,
)
from services._base import db_conn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOTAL_DAYS = 44  # Jan 16 → Feb 28

# Weekly order volumes — gradual recovery from S05 price shock
WEEKLY_ORDER_VOLUME_FR = [
    (2, 3),   # W1  Jan 16–22  — still cautious
    (2, 4),   # W2  Jan 23–29  — recovering
    (2, 4),   # W3  Jan 30 – Feb 05  — back to normal
    (2, 4),   # W4  Feb 06–12  — steady
    (2, 3),   # W5  Feb 13–19  — steady
    (2, 3),   # W6  Feb 20–28  — tapering to month end
    (2, 3),   # W7  (safety — partial week)
]

WEEKLY_ORDER_VOLUME_DE = [
    (1, 2),   # W1  — cautious
    (1, 2),   # W2  — recovering
    (1, 3),   # W3  — normal
    (1, 3),   # W4  — steady
    (1, 2),   # W5  — steady
    (1, 2),   # W6  — tapering
    (1, 2),   # W7  (safety)
]

# Overdue invoice catch-up
OVERDUE_PAY_PCT = 0.85      # pay 85% of overdue invoices
OLD_ISSUED_PAY_PCT = 0.60   # pay 60% of stale issued invoices (>30 days old)

# Post-loop quotes
QUOTE_COUNT_FR = 5
QUOTE_COUNT_DE = 5
QUOTE_REJECTION_RATE = 0.30  # back to normal 30%

# Emails
THANK_YOU_EMAIL_COUNT = 4   # FR
PLANNING_EMAIL_COUNT = 4    # DE


# ---------------------------------------------------------------------------
# SKU pool builder
# ---------------------------------------------------------------------------

def _recovery_pool(core_skus: List[str]) -> List[str]:
    """Core SKUs only (1×) — no seasonal weighting.  Clean baseline."""
    return list(core_skus)


def _german_recovery_pool(
    core_skus: List[str],
    german_skus: List[str],
) -> List[str]:
    """Core (1×) + German (2×) — no seasonal additions."""
    pool = list(core_skus)
    for sku in german_skus:
        pool.extend([sku] * 2)
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
# Email templates
# ---------------------------------------------------------------------------

THANK_YOU_TEMPLATES = [
    ("Thank you for the great service!",
     "Dear Duck Inc team,\n\nWe wanted to take a moment to express our "
     "appreciation for your continued support. Despite the pricing "
     "adjustments, the quality of your products remains excellent. Our "
     "customers love the new designs.\n\nLooking forward to another great "
     "year of partnership.\n\nBest regards,\n{name}"),
    ("Satisfied with recent orders",
     "Hello,\n\nJust a quick note to say that our recent orders (including "
     "{so_id}) arrived on time and in perfect condition. The new packaging "
     "is a nice touch.\n\nKeep up the great work!\n\n{name}"),
    ("Retour positif de nos clients",
     "Bonjour,\n\nNous tenions à vous faire part des retours très positifs "
     "de nos clients sur vos canards. Les modèles de cette saison sont "
     "particulièrement appréciés. Nous sommes satisfaits de notre "
     "partenariat.\n\nCordialement,\n{name}"),
    ("Great start to 2026",
     "Dear team,\n\nAfter a bumpy Q4 with the supply issues and price "
     "changes, we're pleased to say that things are running smoothly now. "
     "Deliveries are on schedule and product quality is consistent.\n\n"
     "Thank you for working through those challenges with us.\n\n"
     "Warm regards,\n{name}"),
]

PLANNING_TEMPLATES = [
    ("2026 Produktplanung — Anfrage",
     "Sehr geehrtes Duck Inc Team,\n\nWir planen bereits unsere "
     "Bestellungen für das Frühjahr 2026. Könnten Sie uns bitte den "
     "aktuellen Katalog mit allen verfügbaren Modellen zusenden? "
     "Insbesondere interessieren uns die deutschen Enten-Editionen.\n\n"
     "Mit freundlichen Grüßen,\n{name}"),
    ("Volume commitment inquiry for Q2 2026",
     "Dear Duck Inc,\n\nWe are planning our Q2 purchasing and would like "
     "to discuss volume-based pricing. We expect to order approximately "
     "{qty} units per month. Could you prepare a proposal?\n\n"
     "Best regards,\n{name}"),
    ("Neue Modelle für 2026?",
     "Hallo,\n\nWir würden gerne wissen, ob Sie für 2026 neue Enten-Modelle "
     "planen. Unsere Kunden fragen häufig nach Neuheiten. Besonders beliebt "
     "sind die thematischen Editionen.\n\nBitte lassen Sie uns wissen, "
     "was in der Pipeline ist.\n\nViele Grüße,\n{name}"),
    ("Partnership review — looking ahead",
     "Dear team,\n\nAs we settle into 2026, we'd like to schedule a "
     "partnership review to discuss product roadmap, delivery schedules, "
     "and pricing for bulk orders. Our market in Germany is growing and "
     "we see strong potential for expansion.\n\nPlease let us know your "
     "availability.\n\nKind regards,\n{name}"),
]


# ---------------------------------------------------------------------------
# Scenario entry point
# ---------------------------------------------------------------------------

def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the New Year Recovery scenario (Jan 16 – Feb 28, 2026).

    Operations normalize after the S05 price shock.  Overdue invoices get
    paid, production backlog clears, demand recovers to baseline levels.
    The database ends in a clean, demo-ready state.
    """
    random.seed(606)
    fr_customer_ids: List[str] = [
        cid for cid in ctx["customer_ids"]
        if cid not in ctx.get("de_customer_ids", [])
    ]
    de_customer_ids: List[str] = ctx.get("de_customer_ids", [])
    all_customer_ids: List[str] = ctx["customer_ids"]
    core_skus: List[str] = ctx.get("core_skus", [])
    german_skus: List[str] = ctx.get("german_skus", [])

    # Jump to Jan 16
    set_time("2026-01-16 08:00:00")

    logger.info("=== S06 New Year Recovery: Jan 16 – Feb 28 2026 (%d days) ===",
                TOTAL_DAYS)

    # ------------------------------------------------------------------
    # Phase 0: Accept/reject remaining sent quotes
    # ------------------------------------------------------------------
    with db_conn() as conn:
        sent_quotes = conn.execute(
            "SELECT id FROM quotes WHERE status = 'sent'"
        ).fetchall()
    sent_quote_ids = [r["id"] for r in sent_quotes]
    random.shuffle(sent_quote_ids)

    accepted_quotes_so_ids: List[str] = []
    accepted_q = 0
    rejected_q = 0

    for qid in sent_quote_ids:
        if random.random() < 0.70:
            # Accept — volume recovery signal
            try:
                result = quote_service.accept_quote(qid)
                so_id = result["sales_order_id"]
                accepted_quotes_so_ids.append(so_id)
                sales_service.confirm_order(so_id)
                activity_service.log_activity(
                    "scenario", "sales", "quote.accepted_recovery",
                    "quote", qid, {"sales_order_id": so_id},
                )
                accepted_q += 1
            except Exception as e:
                logger.debug("Quote accept failed (%s): %s", qid, e)
        else:
            try:
                quote_service.reject_quote(qid, reason=random.choice([
                    "Budget finalized without this order",
                    "Decided to use existing stock",
                    "Project postponed to Q2",
                ]))
                rejected_q += 1
            except Exception as e:
                logger.debug("Quote reject failed (%s): %s", qid, e)

    logger.info("Phase 0 — Quotes: %d accepted (→ SOs), %d rejected, %d total",
                accepted_q, rejected_q, len(sent_quote_ids))

    # ------------------------------------------------------------------
    # Phase 1: Overdue invoice payment catch-up
    # ------------------------------------------------------------------
    set_day_time(9)

    overdue_paid = 0
    issued_paid = 0

    with db_conn() as conn:
        # Pay overdue invoices
        overdue_rows = conn.execute(
            "SELECT id, total FROM invoices WHERE status = 'overdue'"
        ).fetchall()

    random.shuffle(overdue_rows)
    for row in overdue_rows:
        if random.random() < OVERDUE_PAY_PCT:
            try:
                invoice_service.record_payment(
                    invoice_id=row["id"],
                    amount=float(row["total"]),
                    payment_method=random.choice([
                        "bank_transfer", "bank_transfer", "credit_card",
                    ]),
                    reference=f"LATE-{row['id']}",
                )
                activity_service.log_activity(
                    "scenario", "billing", "invoice.overdue_paid",
                    "invoice", row["id"],
                    {"amount": float(row["total"])},
                )
                overdue_paid += 1
            except Exception as e:
                logger.debug("Overdue payment failed (%s): %s", row["id"], e)

    # Pay old issued invoices (issued > 30 days ago)
    with db_conn() as conn:
        old_issued = conn.execute(
            "SELECT id, total FROM invoices "
            "WHERE status = 'issued' "
            "AND issued_at < date(?, '-30 days')",
            (sim_date(),),
        ).fetchall()

    random.shuffle(old_issued)
    for row in old_issued:
        if random.random() < OLD_ISSUED_PAY_PCT:
            try:
                invoice_service.record_payment(
                    invoice_id=row["id"],
                    amount=float(row["total"]),
                    payment_method="bank_transfer",
                    reference=f"CATCHUP-{row['id']}",
                )
                activity_service.log_activity(
                    "scenario", "billing", "invoice.catchup_paid",
                    "invoice", row["id"],
                    {"amount": float(row["total"])},
                )
                issued_paid += 1
            except Exception as e:
                logger.debug("Issued payment failed (%s): %s", row["id"], e)

    logger.info("Phase 1 — Overdue paid: %d/%d, Old issued paid: %d/%d",
                overdue_paid, len(overdue_rows), issued_paid, len(old_issued))

    # ------------------------------------------------------------------
    # Build SKU pools & tracking structures
    # ------------------------------------------------------------------
    fr_sku_pool = _recovery_pool(core_skus)
    de_sku_pool = _german_recovery_pool(core_skus, german_skus)

    logger.info("FR pool: %d weighted SKUs, DE pool: %d weighted SKUs",
                len(fr_sku_pool), len(de_sku_pool))

    # Carry forward prior scenario SO IDs for continued shipping/invoicing
    prior_so_keys = [
        "s01_so_ids", "s02_so_ids", "s03_so_ids", "s04_so_ids", "s05_so_ids",
    ]
    trackable_so_ids: List[str] = []
    for key in prior_so_keys:
        trackable_so_ids.extend(ctx.get(key, []))
    trackable_so_ids.extend(accepted_quotes_so_ids)
    _completed_so_ids: set = set()

    all_so_ids: List[str] = list(accepted_quotes_so_ids)
    fr_so_ids: List[str] = []
    de_so_ids: List[str] = []

    # Accumulators for weekly summary
    wk_sos_fr = wk_sos_de = 0
    wk_mos = wk_shipped = wk_invoiced = wk_restocked = wk_received = 0
    wk_replan = 0

    # ------------------------------------------------------------------
    # Phase 2: Daily loop (44 days)
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

            # 7. Invoice shipped orders (pay_pct=0.75 — good payment behaviour)
            pending_inv = [sid for sid in trackable_so_ids
                          if sid not in _completed_so_ids]
            inv_n = fulfillment_service.invoice_shipped_orders(
                pending_inv, completed_set=_completed_so_ids,
                pay_pct=0.75,
            )
            wk_invoiced += inv_n

            # ----- End of day — advance clock by 1 day -----
            set_day_time(18)
            advance_and_settle(hours=14)  # 18:00 → next day 08:00

        # Log daily status snapshot (first week daily, then weekly)
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
    # Phase 3: Backlog clearance sweep
    # ------------------------------------------------------------------
    logger.info("Phase 3 — Backlog clearance sweep...")

    # 3a. Receive any remaining due POs and start ready MOs
    with db_conn():
        n_rcv = fulfillment_service.receive_due_pos(sim_date())
        n_started = fulfillment_service.start_ready_mos()
        mrp_service.replan_unfulfilled_orders()
        try:
            restock_materials()
        except Exception:
            pass

    # 3b. Advance 3 days to let side-effects clear in-progress MOs & shipments
    advance_and_settle(days=1)
    with db_conn():
        fulfillment_service.receive_due_pos(sim_date())
        fulfillment_service.start_ready_mos()
    advance_and_settle(days=1)
    with db_conn():
        fulfillment_service.receive_due_pos(sim_date())
        fulfillment_service.start_ready_mos()
    advance_and_settle(days=1)

    # 3c. Ship remaining confirmed SOs
    with db_conn():
        pending_ship = [sid for sid in trackable_so_ids
                       if sid not in _completed_so_ids]
        ship_ids = fulfillment_service.ship_ready_orders(
            pending_ship, sim_date_fn=sim_date, future_date_fn=future_date,
        )
        logger.info("  Backlog shipped: %d orders", len(ship_ids))

    # 3d. Invoice + pay remaining shipped SOs
    with db_conn():
        pending_inv = [sid for sid in trackable_so_ids
                      if sid not in _completed_so_ids]
        inv_n = fulfillment_service.invoice_shipped_orders(
            pending_inv, completed_set=_completed_so_ids,
            pay_pct=0.80,
        )
        logger.info("  Backlog invoiced: %d orders", inv_n)

    # 3e. Final payment sweep — pay remaining issued/overdue invoices
    final_paid = 0
    with db_conn() as conn:
        unpaid = conn.execute(
            "SELECT id, total FROM invoices WHERE status IN ('issued', 'overdue')"
        ).fetchall()
    for row in unpaid:
        if random.random() < 0.80:
            try:
                invoice_service.record_payment(
                    invoice_id=row["id"],
                    amount=float(row["total"]),
                    payment_method="bank_transfer",
                    reference=f"FINAL-{row['id']}",
                )
                final_paid += 1
            except Exception as e:
                logger.debug("Final payment failed (%s): %s", row["id"], e)
    logger.info("  Final payment sweep: %d/%d invoices paid", final_paid, len(unpaid))

    # ------------------------------------------------------------------
    # Phase 4: Post-loop emails
    # ------------------------------------------------------------------
    logger.info("Phase 4 — Post-loop emails...")

    # 4a. Thank-you emails from FR customers
    with db_conn() as conn:
        recent_completed = conn.execute(
            "SELECT so.id, so.customer_id, c.name "
            "FROM sales_orders so "
            "JOIN customers c ON so.customer_id = c.id "
            "WHERE so.status = 'completed' "
            "AND c.country = 'FR' "
            "ORDER BY RANDOM() LIMIT ?",
            (THANK_YOU_EMAIL_COUNT,),
        ).fetchall()

    for row in recent_completed:
        t = random.choice(THANK_YOU_TEMPLATES)
        subj = t[0].format(name=row["name"], so_id=row["id"],
                           qty=random.randint(50, 200))
        body = t[1].format(name=row["name"], so_id=row["id"],
                           qty=random.randint(50, 200))
        try:
            send_email(
                customer_id=row["customer_id"], subject=subj,
                body=body, sales_order_id=row["id"],
            )
        except Exception as e:
            logger.warning("Thank-you email failed: %s", e)

    # 4b. Planning emails from DE customers
    with db_conn() as conn:
        de_cust_rows = conn.execute(
            "SELECT id as customer_id, name FROM customers "
            "WHERE country = 'DE' ORDER BY RANDOM() LIMIT ?",
            (PLANNING_EMAIL_COUNT,),
        ).fetchall()

    for row in de_cust_rows:
        t = random.choice(PLANNING_TEMPLATES)
        subj = t[0].format(name=row["name"], qty=random.randint(80, 300))
        body = t[1].format(name=row["name"], qty=random.randint(80, 300))
        try:
            send_email(customer_id=row["customer_id"], subject=subj, body=body)
        except Exception as e:
            logger.warning("Planning email failed: %s", e)

    # ------------------------------------------------------------------
    # Phase 5: Standalone quotes (normal rejection rate)
    # ------------------------------------------------------------------
    logger.info("Phase 5 — Standalone quotes...")
    new_quote_ids: List[str] = []

    with db_conn():
        # French quotes
        for _ in range(QUOTE_COUNT_FR):
            cust = random.choice(fr_customer_ids)
            ship_to = get_customer_ship_to(cust)
            lines = pick_random_lines(
                core_skus,
                n_lines=random.randint(1, 3),
                qty_range=(5, 30),
            )
            try:
                q_id = create_quote_only(
                    customer_id=cust, lines=lines, ship_to=ship_to,
                    send=True, valid_days=30,
                )
                new_quote_ids.append(q_id)
                if random.random() < QUOTE_REJECTION_RATE:
                    quote_service.reject_quote(q_id, reason=random.choice([
                        "Budget already committed",
                        "Postponing order to Q2",
                        "Will reorder next month",
                    ]))
            except Exception as e:
                logger.warning("FR quote failed: %s", e)

        # German quotes
        for _ in range(QUOTE_COUNT_DE):
            cust = random.choice(de_customer_ids) if de_customer_ids else random.choice(fr_customer_ids)
            ship_to = get_customer_ship_to(cust)
            lines = pick_random_lines(
                german_skus + core_skus[:5] if german_skus else core_skus,
                n_lines=random.randint(1, 2),
                qty_range=(5, 25),
            )
            try:
                q_id = create_quote_only(
                    customer_id=cust, lines=lines, ship_to=ship_to,
                    send=True, valid_days=30,
                )
                new_quote_ids.append(q_id)
                if random.random() < QUOTE_REJECTION_RATE:
                    quote_service.reject_quote(q_id, reason=random.choice([
                        "Bestellung verschoben",
                        "Budget nicht verfügbar",
                        "Will evaluate alternatives first",
                    ]))
            except Exception as e:
                logger.warning("DE quote failed: %s", e)

    logger.info("Created %d standalone quotes", len(new_quote_ids))

    # ------------------------------------------------------------------
    # Phase 6: Final settle (2 days)
    # ------------------------------------------------------------------
    advance_and_settle(days=1)
    advance_and_settle(days=1)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    with db_conn() as conn:
        counts = {}
        for tbl in ["sales_orders", "production_orders", "invoices", "quotes",
                     "shipments", "purchase_orders", "emails", "payments"]:
            counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]

        # Status breakdowns for key entities
        waiting_mos = conn.execute(
            "SELECT COUNT(*) FROM production_orders WHERE status = 'waiting'"
        ).fetchone()[0]
        confirmed_sos = conn.execute(
            "SELECT COUNT(*) FROM sales_orders WHERE status = 'confirmed'"
        ).fetchone()[0]
        overdue_inv = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'overdue'"
        ).fetchone()[0]
        completed_sos = conn.execute(
            "SELECT COUNT(*) FROM sales_orders WHERE status = 'completed'"
        ).fetchone()[0]
        paid_inv = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'paid'"
        ).fetchone()[0]

    logger.info("=== S06 Complete ===")
    for k, v in counts.items():
        logger.info("  %-22s %d", k, v)
    logger.info("  ---")
    logger.info("  SOs completed:       %d", completed_sos)
    logger.info("  SOs still confirmed: %d", confirmed_sos)
    logger.info("  MOs still waiting:   %d", waiting_mos)
    logger.info("  Invoices paid:       %d", paid_inv)
    logger.info("  Invoices overdue:    %d", overdue_inv)
    logger.info("  ---")
    logger.info("  Accepted quotes:     %d → SOs", accepted_q)
    logger.info("  New FR SOs:          %d", len(fr_so_ids))
    logger.info("  New DE SOs:          %d", len(de_so_ids))
    logger.info("  Overdue paid (P1):   %d", overdue_paid)
    logger.info("  Old issued paid (P1):%d", issued_paid)
    logger.info("  Final sweep paid:    %d", final_paid)
    logger.info("  Post-loop quotes:    %d", len(new_quote_ids))
    logger.info("  Sim time:            %s", current_time())

    return {
        "s06_so_ids": all_so_ids,
        "final_sim_time": current_time(),
    }
