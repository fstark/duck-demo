"""S03 — Material Shortage: PVC supply disruption Nov 2025.

PlasticCorp (SUP-001) experiences PVC delivery delays (+3 weeks).  Production
orders pile up in ``waiting`` as PVC-PELLETS stock runs dry.  Expedited POs
are placed with EuroPlast GmbH (SUP-004) and DuraPoly Industries (SUP-009) at
higher cost.  Mid-month, some expedited POs arrive and partially unblock
production.  Customer complaint emails accumulate.  Visible production dip in
charts.

Normal demand continues throughout (~2–3 SOs/day on core SKU pool — Halloween
season is over).  The restock system keeps ordering from the default supplier
(SUP-001) but those POs also get delayed by the ongoing disruption.

Period: 2025-11-01 → 2025-11-30  (30 days)
"""

import logging
import random
from typing import Any, Dict, List

from scenarios.helpers import (
    advance_and_settle,
    create_sales_order_only,
    create_supply_disruption,
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
    purchase_service,
)
from services._base import db_conn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOTAL_DAYS = 30

# Supply disruption parameters
DISRUPTION_MATERIAL = "PVC-PELLETS"
DISRUPTION_DELAY_DAYS = 21

# Alternate suppliers for expedited POs
EXPEDITED_SUPPLIER_1 = "EuroPlast GmbH"       # SUP-004, 12-day lead time
EXPEDITED_SUPPLIER_2 = "DuraPoly Industries"   # SUP-009, 14-day lead time

# Quantity per expedited PO (grams — generous enough to partially unblock)
EXPEDITED_PO_QTY = 500_000

# Day indices when expedited POs are placed (0-based)
EXPEDITED_PO_SCHEDULE = [
    (2,  EXPEDITED_SUPPLIER_1),   # Day 3  — first reaction
    (5,  EXPEDITED_SUPPLIER_2),   # Day 6  — spread risk
    (8,  EXPEDITED_SUPPLIER_1),   # Day 9  — second wave
    (12, EXPEDITED_SUPPLIER_2),   # Day 13 — mid-month push
    (16, EXPEDITED_SUPPLIER_1),   # Day 17 — keep pipeline flowing
    (20, EXPEDITED_SUPPLIER_2),   # Day 21 — late top-up
]

# Days on which the disruption is (re-)applied to catch new POs to SUP-001
DISRUPTION_REAPPLY_DAYS = [0, 7, 14]

# Orders-per-day range for each week — back to S01 baseline levels
# 5 weeks: Nov 01–07, 08–14, 15–21, 22–28, 29–30
WEEKLY_ORDER_VOLUME = [
    (2, 3),   # W1
    (2, 3),   # W2
    (2, 4),   # W3
    (2, 3),   # W4
    (2, 3),   # W5
]


def _orders_per_day_for_day(day_index: int) -> tuple:
    """Return the (min, max) order range for a given day index (0-based)."""
    week_index = min(day_index // 7, len(WEEKLY_ORDER_VOLUME) - 1)
    return WEEKLY_ORDER_VOLUME[week_index]


# ---------------------------------------------------------------------------
# Daily helpers
# ---------------------------------------------------------------------------

def _create_day_orders(
    customer_ids: List[str],
    sku_pool: List[str],
    orders_per_day: tuple,
) -> List[str]:
    """Create confirmed SOs for a single day. Returns list of SO IDs."""
    so_ids: List[str] = []
    n = random.randint(*orders_per_day)
    for _ in range(n):
        cust = random.choice(customer_ids)
        ship_to = get_customer_ship_to(cust)
        n_lines = random.choices([1, 2, 3], weights=[40, 40, 20])[0]
        lines = pick_random_lines(sku_pool, n_lines=n_lines, qty_range=(5, 25))
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
    """Execute the Material Shortage scenario (Nov 2025).

    Runs a daily simulation loop over 30 days (Nov 1 → Nov 30).
    PVC supply disruption blocks production, expedited POs to alternate
    suppliers partially restore flow mid-month.
    """
    random.seed(303)
    customer_ids: List[str] = ctx["customer_ids"]
    core_skus: List[str] = ctx.get("core_skus", [])

    # Jump to Nov 1st
    set_time("2025-11-01 08:00:00")

    logger.info("=== S03 Material Shortage: Nov 2025 (daily loop, %d days) ===",
                TOTAL_DAYS)
    logger.info("Customers: %d, Core SKU pool: %d", len(customer_ids), len(core_skus))

    all_so_ids: List[str] = []
    # Carry forward prior scenario SO IDs for continued shipping/invoicing
    s01_so_ids: List[str] = ctx.get("s01_so_ids", [])
    s02_so_ids: List[str] = ctx.get("s02_so_ids", [])
    trackable_so_ids: List[str] = list(s01_so_ids) + list(s02_so_ids)
    _completed_so_ids: set = set()

    # Accumulators for weekly summary logging
    wk_sos = wk_mos = wk_shipped = wk_invoiced = wk_restocked = wk_received = 0
    wk_replan = 0
    wk_expedited = 0
    total_expedited = 0

    # Build lookup for expedited PO schedule
    expedited_schedule: Dict[int, str] = {
        day: supplier for day, supplier in EXPEDITED_PO_SCHEDULE
    }

    # ------------------------------------------------------------------
    # Daily loop
    # ------------------------------------------------------------------
    for day in range(TOTAL_DAYS):
        opd = _orders_per_day_for_day(day)
        week_num = day // 7 + 1

        # Log weekly summary at week boundaries
        if day > 0 and day % 7 == 0:
            logger.info(
                "  Week %d summary — SOs: %d, MOs: %d (replan: %d), Shipped: %d, "
                "Invoiced: %d, Restocked: %d POs, Received: %d POs, "
                "Expedited: %d POs",
                week_num - 1, wk_sos, wk_mos, wk_replan, wk_shipped,
                wk_invoiced, wk_restocked, wk_received, wk_expedited,
            )
            wk_sos = wk_mos = wk_shipped = wk_invoiced = 0
            wk_restocked = wk_received = wk_replan = wk_expedited = 0

        with db_conn():  # reuse one connection per day

            # ----- Morning (08:00) — Receive & start production -----
            set_day_time(8)

            # Apply / re-apply supply disruption on scheduled days
            if day in DISRUPTION_REAPPLY_DAYS:
                n_disrupted = create_supply_disruption(
                    DISRUPTION_MATERIAL, DISRUPTION_DELAY_DAYS,
                )
                logger.info(
                    "  Day %d: supply disruption applied — %d PVC POs delayed +%d days",
                    day + 1, n_disrupted, DISRUPTION_DELAY_DAYS,
                )

            # 1. Receive POs that have arrived
            n_rcv = fulfillment_service.receive_due_pos(sim_date())
            wk_received += n_rcv

            # 2. Start any MOs that are ready
            fulfillment_service.start_ready_mos()

            # 2b. MRP re-plan
            n_replan = mrp_service.replan_unfulfilled_orders()
            wk_replan += n_replan
            wk_mos += n_replan

            # 2c. Restock materials (keeps running — but PVC POs to SUP-001 get
            # delayed by the disruption re-application above)
            if n_replan:
                try:
                    rs2 = restock_materials()
                    wk_restocked += rs2.get("purchase_orders_created", 0)
                except Exception:
                    pass

            # ----- Expedited PO placement (08:30) -----
            if day in expedited_schedule:
                set_day_time(8, 30)
                supplier = expedited_schedule[day]
                try:
                    po = purchase_service.create_order(
                        DISRUPTION_MATERIAL, EXPEDITED_PO_QTY, supplier,
                    )
                    wk_expedited += 1
                    total_expedited += 1
                    activity_service.log_activity(
                        "scenario", "purchasing",
                        "purchase_order.expedited",
                        "purchase_order", po["purchase_order_id"],
                        {"supplier": supplier, "material": DISRUPTION_MATERIAL,
                         "qty": EXPEDITED_PO_QTY},
                    )
                    logger.info(
                        "  Day %d: expedited PO %s → %s (%d g PVC, ETA %s)",
                        day + 1, po["purchase_order_id"], supplier,
                        EXPEDITED_PO_QTY, po["expected_delivery"],
                    )
                except Exception as e:
                    logger.warning("Expedited PO failed on day %d: %s", day + 1, e)

            # ----- Mid-morning (10:00) — New sales orders -----
            set_day_time(10)

            # 3. Create today's sales orders (core SKU pool — Halloween is over)
            day_sos = _create_day_orders(customer_ids, core_skus, opd)
            all_so_ids.extend(day_sos)
            trackable_so_ids.extend(day_sos)
            wk_sos += len(day_sos)

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

            # 6. Restock raw materials (continues throughout — realistic)
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
        "  Week %d summary — SOs: %d, MOs: %d (replan: %d), Shipped: %d, "
        "Invoiced: %d, Restocked: %d POs, Received: %d POs, Expedited: %d POs",
        (TOTAL_DAYS - 1) // 7 + 1, wk_sos, wk_mos, wk_replan, wk_shipped,
        wk_invoiced, wk_restocked, wk_received, wk_expedited,
    )

    # ------------------------------------------------------------------
    # Customer complaint emails about production / shipping delays
    # ------------------------------------------------------------------
    logger.info("Creating customer complaint emails...")
    complaint_templates = [
        ("Production delay on order {so_id}?",
         "Dear Duck Inc,\n\nI placed order {so_id} and was told it would ship "
         "within two weeks, but I have not received any tracking information. "
         "Is there a production issue causing the delay?\n\nPlease advise,"
         "\n{name}"),
        ("When will order {so_id} ship? Running out of stock",
         "Hello,\n\nWe are running low on inventory and urgently need order "
         "{so_id} delivered. Could you provide an estimated shipping date? "
         "This is becoming critical for our business.\n\nBest regards,"
         "\n{name}"),
        ("Urgent: Need delivery update for {so_id}",
         "Dear team,\n\nOrder {so_id} has been pending for far too long. "
         "Our customers are asking us for stock and we cannot fulfil their "
         "requests without your delivery. Please escalate this.\n\n"
         "Regards,\n{name}"),
        ("Disappointed — order {so_id} still not shipped after weeks",
         "Dear Duck Inc,\n\nIt has been weeks since I placed order {so_id} "
         "and there is still no sign of shipment. This is unacceptable. "
         "I need a concrete delivery date or I will have to look for "
         "alternative suppliers.\n\n{name}"),
        ("Material shortage affecting my order {so_id}?",
         "Hello,\n\nI heard through the grapevine that you are experiencing "
         "material supply issues. Is this affecting my order {so_id}? "
         "I would appreciate transparency on the situation and an updated "
         "timeline.\n\nThank you,\n{name}"),
    ]

    # Include both s03 and s02 SOs that are still confirmed (backlogged)
    complaint_so_pool = all_so_ids + list(s02_so_ids)
    with db_conn() as conn:
        if complaint_so_pool:
            delayed = conn.execute(
                "SELECT so.id, so.customer_id, c.name "
                "FROM sales_orders so "
                "JOIN customers c ON so.customer_id = c.id "
                "WHERE so.status = 'confirmed' "
                "AND so.id IN ({}) "
                "ORDER BY RANDOM() LIMIT 12".format(
                    ",".join("?" for _ in complaint_so_pool)
                ),
                complaint_so_pool,
            ).fetchall()
        else:
            delayed = []

    for row in delayed:
        t = random.choice(complaint_templates)
        subj = t[0].format(so_id=row["id"], name=row["name"])
        body = t[1].format(so_id=row["id"], name=row["name"])
        try:
            send_email(customer_id=row["customer_id"], subject=subj,
                       body=body, sales_order_id=row["id"])
        except Exception as e:
            logger.warning("Complaint email failed: %s", e)

    # ------------------------------------------------------------------
    # Short settle (2 days — let some in-flight expedited POs arrive)
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

        # PVC-specific stats
        pvc_pos = conn.execute(
            "SELECT po.status, COUNT(*) as cnt "
            "FROM purchase_orders po "
            "JOIN items i ON po.item_id = i.id "
            "WHERE i.sku = ? "
            "GROUP BY po.status",
            (DISRUPTION_MATERIAL,),
        ).fetchall()
        pvc_stock = conn.execute(
            "SELECT COALESCE(SUM(s.on_hand), 0) "
            "FROM stock s JOIN items i ON s.item_id = i.id "
            "WHERE i.sku = ?",
            (DISRUPTION_MATERIAL,),
        ).fetchone()[0]

    logger.info("=== S03 Complete ===")
    for k, v in counts.items():
        logger.info("  %-22s %d", k, v)
    logger.info("  MOs still waiting:   %d", waiting_mos)
    logger.info("  SOs still confirmed: %d", confirmed_sos)
    logger.info("  Expedited POs placed: %d", total_expedited)
    logger.info("  PVC PO status:       %s",
                " ".join(f"{r['status']}={r['cnt']}" for r in pvc_pos))
    logger.info("  PVC stock on hand:   %d g", pvc_stock)
    logger.info("  Sim time:            %s", current_time())

    return {
        "s03_so_ids": all_so_ids,
        "disruption_material": DISRUPTION_MATERIAL,
    }
