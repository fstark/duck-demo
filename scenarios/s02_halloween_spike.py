"""S02 — Halloween Spike: Massive demand surge Oct 2025.

Spooky-themed ducks (Witch, Pumpkin, Vampire, Ghost, Frankenstein, Zombie)
see 2–3× normal order volume.  Ninja and Pirate also spike (costume season).
Production capacity is stressed: material consumption outpaces restocking in
the second half of the month, stranding MOs in ``waiting``.  Orders placed in
the last few days of October won't complete before month end.
Customer inquiry emails add realistic drama.

Period: 2025-10-01 → 2025-10-31  (31 days)
"""

import logging
import random
from typing import Any, Dict, List

from scenarios.helpers import (
    advance_and_settle,
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
    fulfillment_service,
    mrp_service,
)
from services._base import db_conn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HALLOWEEN_SKUS = [
    "WITCH-DUCK-15CM",
    "PUMPKIN-DUCK-12CM",
    "VAMPIRE-DUCK-15CM",
    "GHOST-DUCK-12CM",
    "FRANKENSTEIN-DUCK-20CM",
    "ZOMBIE-DUCK-15CM",
]

COSTUME_SKUS = [
    "NINJA-DUCK-12CM",
    "PIRATE-DUCK-15CM",
]

# Orders-per-day range for each week
# 5 weeks: Oct 01–07, 08–14, 15–21, 22–28, 29–31
WEEKLY_ORDER_VOLUME = [
    (4, 6),   # W1  ramp-up
    (5, 8),   # W2  peak building
    (6, 9),   # W3  peak
    (6, 8),   # W4  peak sustained
    (4, 6),   # W5  tail-off (these orders won't complete)
]

TOTAL_DAYS = 31

# Day index after which we stop restocking → creates material stress
RESTOCK_CUTOFF_DAY = 21


def _halloween_sku_pool(core_skus: List[str]) -> List[str]:
    """Build a weighted SKU pool biased toward Halloween & costume ducks."""
    pool: List[str] = []
    # Halloween heavyweights (4× each)
    for sku in HALLOWEEN_SKUS:
        pool.extend([sku] * 4)
    # Costume season boost (3× each)
    for sku in COSTUME_SKUS:
        pool.extend([sku] * 3)
    # Baseline core demand (1× each)
    pool.extend(core_skus)
    return pool


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
        lines = pick_random_lines(sku_pool, n_lines=n_lines, qty_range=(8, 30))
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
    """Execute the Halloween Spike scenario (Oct 2025).

    Runs a daily simulation loop over 31 days (Oct 1 → Oct 31).
    Higher volume, Halloween-weighted SKU pool, and deliberate restock
    cutoff in the second half to create production stress.
    """
    random.seed(202)
    customer_ids: List[str] = ctx["customer_ids"]
    core_skus: List[str] = ctx.get("core_skus", [])
    sku_pool = _halloween_sku_pool(core_skus)

    # Jump to Oct 1st (S01 settle may have moved clock past this)
    set_time("2025-10-01 08:00:00")

    logger.info("=== S02 Halloween Spike: Oct 2025 (daily loop, %d days) ===",
                TOTAL_DAYS)
    logger.info("Customers: %d, Halloween SKUs: %d, Costume SKUs: %d, "
                "Pool size: %d",
                len(customer_ids), len(HALLOWEEN_SKUS), len(COSTUME_SKUS),
                len(sku_pool))

    all_so_ids: List[str] = []
    # Include S01 SO IDs so we can continue shipping/invoicing them
    s01_so_ids: List[str] = ctx.get("s01_so_ids", [])
    trackable_so_ids: List[str] = list(s01_so_ids) + all_so_ids
    _completed_so_ids: set = set()

    # Accumulators for weekly summary logging
    wk_sos = wk_mos = wk_shipped = wk_invoiced = wk_restocked = wk_received = 0
    wk_replan = 0

    # ------------------------------------------------------------------
    # Daily loop
    # ------------------------------------------------------------------
    for day in range(TOTAL_DAYS):
        opd = _orders_per_day_for_day(day)
        week_num = day // 7 + 1
        allow_restock = day < RESTOCK_CUTOFF_DAY

        # Log weekly summary at week boundaries
        if day > 0 and day % 7 == 0:
            logger.info(
                "  Week %d summary — SOs: %d, MOs: %d (replan: %d), Shipped: %d, "
                "Invoiced: %d, Restocked: %d POs, Received: %d POs",
                week_num - 1, wk_sos, wk_mos, wk_replan, wk_shipped,
                wk_invoiced, wk_restocked, wk_received,
            )
            wk_sos = wk_mos = wk_shipped = wk_invoiced = 0
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

            # 2c. Restock after re-plan (only in first 3 weeks)
            if n_replan and allow_restock:
                try:
                    rs2 = restock_materials()
                    wk_restocked += rs2.get("purchase_orders_created", 0)
                except Exception:
                    pass

            # ----- Mid-morning (10:00) — New sales orders -----
            set_day_time(10)

            # 3. Create today's sales orders (heavier Halloween mix)
            day_sos = _create_day_orders(customer_ids, sku_pool, opd)
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

            # 6. Restock raw materials (only in first 3 weeks)
            if allow_restock:
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
        "Invoiced: %d, Restocked: %d POs, Received: %d POs",
        (TOTAL_DAYS - 1) // 7 + 1, wk_sos, wk_mos, wk_replan, wk_shipped,
        wk_invoiced, wk_restocked, wk_received,
    )

    # ------------------------------------------------------------------
    # Customer inquiry emails ("Where is my order?")
    # ------------------------------------------------------------------
    logger.info("Creating customer inquiry emails...")
    inquiry_templates = [
        ("Where is my order {so_id}?",
         "Dear Duck Inc,\n\nI placed order {so_id} some time ago and have not "
         "received any shipping notification yet. Could you please provide an "
         "update on the delivery status?\n\nThank you,\n{name}"),
        ("Order {so_id} — delivery update?",
         "Hello,\n\nI would like to check on the status of my order {so_id}. "
         "When can I expect delivery?\n\nBest regards,\n{name}"),
        ("Urgent: Halloween event approaching, need order {so_id} ASAP",
         "Dear team,\n\nOur Halloween event is fast approaching and we still "
         "haven't received order {so_id}. This is becoming urgent — please "
         "let us know the expected delivery date.\n\nRegards,\n{name}"),
        ("Disappointed with delivery time for {so_id}",
         "Dear Duck Inc,\n\nI am disappointed with the delivery time for "
         "order {so_id}. We ordered well in advance for our Halloween "
         "display, yet there is still no shipment.\n\n{name}"),
    ]
    with db_conn() as conn:
        # Find SOs that are still confirmed (not completed) — delayed orders
        delayed = conn.execute(
            "SELECT so.id, so.customer_id, c.name "
            "FROM sales_orders so "
            "JOIN customers c ON so.customer_id = c.id "
            "WHERE so.status = 'confirmed' "
            "AND so.id IN ({}) "
            "ORDER BY RANDOM() LIMIT 10".format(
                ",".join("?" for _ in all_so_ids)
            ),
            all_so_ids,
        ).fetchall()

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
    # Short settle (1 day — preserve backlog for S03)
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

    logger.info("=== S02 Complete ===")
    for k, v in counts.items():
        logger.info("  %-22s %d", k, v)
    logger.info("  MOs still waiting:   %d", waiting_mos)
    logger.info("  SOs still confirmed: %d", confirmed_sos)
    logger.info("  Sim time:            %s", current_time())

    return {
        "s02_so_ids": all_so_ids,
        "halloween_skus": HALLOWEEN_SKUS,
        "costume_skus": COSTUME_SKUS,
    }
