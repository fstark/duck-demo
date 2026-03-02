"""S01 — Steady State: Normal operations Aug–Sep 2025.

Establishes the baseline that later scenarios contrast against.
Runs a day-by-day simulation where each day follows a natural rhythm:
  morning:   receive POs, promote & start MOs
  mid-day:   create new sales orders, trigger production
  afternoon: ship ready orders, restock materials
  evening:   invoice shipped orders, record payments
  end of day: advance 1 day (side-effects: complete MOs, deliver shipments, …)

Period: 2025-08-01 → 2025-09-30  (sim clock already at 08-01 from base_setup)
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
    sim_date,
    trigger_production_for_orders,
)
from utils import ship_to_dict
from services import (
    inventory_service,
    invoice_service,
    logistics_service,
    production_service,
    purchase_service,
    quote_service,
    sales_service,
)
import config
from services._base import db_conn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CORE_SKUS = [
    "CLASSIC-DUCK-10CM", "ELVIS-DUCK-20CM", "MARILYN-DUCK-20CM",
    "PIRATE-DUCK-15CM", "NINJA-DUCK-12CM", "UNICORN-DUCK-25CM",
    "DISCO-DUCK-18CM", "WIZARD-DUCK-20CM", "ASTRONAUT-DUCK-22CM",
    "SUPERHERO-DUCK-20CM", "ZOMBIE-DUCK-15CM", "VIKING-DUCK-18CM",
    "MERMAID-DUCK-20CM", "ROBOT-DUCK-25CM", "CHEF-DUCK-15CM",
    "ROCKSTAR-DUCK-20CM", "DETECTIVE-DUCK-18CM", "SURFER-DUCK-15CM",
    "COWBOY-DUCK-20CM", "BALLERINA-DUCK-12CM", "GNOME-DUCK-30CM",
    "PARROT-DUCK-18CM",
]

TOP_SELLERS = [
    "CLASSIC-DUCK-10CM", "ELVIS-DUCK-20CM", "PIRATE-DUCK-15CM",
    "NINJA-DUCK-12CM", "UNICORN-DUCK-25CM", "ROBOT-DUCK-25CM",
]

# Orders-per-day range for each week (week_number → (min, max))
# 9 weeks: Aug 01 → Sep 30
WEEKLY_ORDER_VOLUME = [
    (2, 3),   # W1  Aug 01–07
    (2, 4),   # W2  Aug 08–14
    (2, 4),   # W3  Aug 15–21
    (3, 4),   # W4  Aug 22–28  (summer peak)
    (2, 4),   # W5  Aug 29 – Sep 04
    (2, 3),   # W6  Sep 05–11
    (2, 4),   # W7  Sep 12–18
    (2, 3),   # W8  Sep 19–25
    (2, 3),   # W9  Sep 26–30  (partial)
]

# Total sim days: 61 (Aug 1 → Sep 30 inclusive)
TOTAL_DAYS = 61


def _weighted_sku_pool() -> List[str]:
    pool = list(CORE_SKUS)
    for sku in TOP_SELLERS:
        pool.extend([sku] * 2)
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
        n_lines = random.choices([1, 2, 3], weights=[50, 35, 15])[0]
        lines = pick_random_lines(sku_pool, n_lines=n_lines, qty_range=(5, 25))
        try:
            so_id = create_sales_order_only(
                customer_id=cust, lines=lines, ship_to=ship_to, confirm=True,
            )
            so_ids.append(so_id)
        except Exception as e:
            logger.warning("SO creation failed: %s", e)
    return so_ids


def _start_ready_mos() -> int:
    """Find ready production orders and start them. Returns count started."""
    with db_conn() as conn:
        ready = conn.execute(
            "SELECT id FROM production_orders WHERE status = 'ready'"
        ).fetchall()
    started = 0
    for mo in ready:
        result = production_service.start_order(mo["id"])
        if result["status"] == "in_progress":
            started += 1
    return started


def _receive_due_pos() -> int:
    """Receive POs whose expected_delivery has passed. Returns count received."""
    with db_conn() as conn:
        due = conn.execute(
            "SELECT id FROM purchase_orders "
            "WHERE status = 'ordered' AND expected_delivery <= ?",
            (sim_date(),),
        ).fetchall()
    received = 0
    for po in due:
        try:
            purchase_service.receive(po["id"], warehouse=config.WAREHOUSE_DEFAULT, location=config.LOC_RAW_MATERIAL_RECV)
            received += 1
        except Exception as e:
            logger.debug("PO %s receive skipped: %s", po["id"], e)
    return received


def _ship_ready_orders(so_ids: List[str]) -> List[str]:
    """Ship SOs whose items are in stock. Returns shipment IDs."""
    ship_ids: List[str] = []
    for so_id in so_ids:
        with db_conn() as conn:
            so = conn.execute(
                "SELECT * FROM sales_orders WHERE id = ?", (so_id,)
            ).fetchone()
            if not so or so["status"] == "completed":
                continue
            existing = conn.execute(
                "SELECT 1 FROM sales_order_shipments WHERE sales_order_id = ?",
                (so_id,),
            ).fetchone()
            if existing:
                continue
            lines = conn.execute(
                "SELECT i.sku, sol.qty FROM sales_order_lines sol "
                "JOIN items i ON sol.item_id = i.id "
                "WHERE sol.sales_order_id = ?", (so_id,)
            ).fetchall()

        # Use raw on_hand stock (not check_availability which includes
        # reservations from ALL open SOs, creating a death-spiral where
        # growing demand always exceeds produced supply).
        can_ship = True
        for ln in lines:
            with db_conn() as c2:
                on_hand = c2.execute(
                    "SELECT COALESCE(SUM(s.on_hand), 0) "
                    "FROM stock s JOIN items i ON s.item_id = i.id "
                    "WHERE i.sku = ?", (ln["sku"],)
                ).fetchone()[0]
            if on_hand < int(ln["qty"]):
                can_ship = False
                break
        if not can_ship:
            continue

        ship_to = ship_to_dict(so) or {
            "line1": "1 Rue du Commerce",
            "city": "Paris",
            "postal_code": "75001",
            "country": "FR",
        }
        pkgs = [{"contents": [{"sku": l["sku"], "qty": int(l["qty"])} for l in lines]}]
        try:
            ship = logistics_service.create_shipment(
                ship_from={"warehouse": config.WAREHOUSE_DEFAULT},
                ship_to=ship_to,
                planned_departure=sim_date(),
                planned_arrival=future_date(random.randint(2, 4)),
                packages=pkgs,
                reference={"type": "sales_order", "id": so_id},
            )
            logistics_service.dispatch_shipment(ship["shipment_id"])
            ship_ids.append(ship["shipment_id"])
        except Exception as e:
            logger.warning("Ship failed for %s: %s", so_id, e)
    return ship_ids


def _invoice_shipped_orders(so_ids: List[str], pay_pct: float = 0.75,
                            completed_set: set | None = None) -> int:
    """Invoice SOs that have dispatched/delivered shipments. Returns count."""
    count = 0
    for so_id in so_ids:
        with db_conn() as conn:
            already = conn.execute(
                "SELECT 1 FROM invoices WHERE sales_order_id = ?", (so_id,)
            ).fetchone()
            if already:
                continue
            has_ship = conn.execute(
                "SELECT 1 FROM sales_order_shipments sos "
                "JOIN shipments s ON s.id = sos.shipment_id "
                "WHERE sos.sales_order_id = ? "
                "AND s.status IN ('in_transit','delivered')",
                (so_id,),
            ).fetchone()
        if not has_ship:
            continue
        try:
            inv = invoice_service.create_invoice(so_id)
            invoice_service.issue_invoice(inv["invoice_id"])
            count += 1
            if random.random() < pay_pct:
                invoice_service.record_payment(
                    invoice_id=inv["invoice_id"],
                    amount=inv["total"],
                    payment_method=random.choice([
                        "bank_transfer", "bank_transfer", "credit_card",
                    ]),
                    reference=f"VIR-{so_id}",
                )
            sales_service.complete_order(so_id)
            if completed_set is not None:
                completed_set.add(so_id)
        except Exception as e:
            logger.warning("Invoice/pay failed for %s: %s", so_id, e)
    return count


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
    """Execute the Steady State scenario (Aug–Sep 2025).

    Runs a daily simulation loop over 61 days (Aug 1 → Sep 30).
    Each day follows a natural factory rhythm.
    """
    random.seed(42)
    customer_ids: List[str] = ctx["customer_ids"]
    sku_pool = _weighted_sku_pool()

    logger.info("=== S01 Steady State: Aug–Sep 2025 (daily loop, %d days) ===",
                TOTAL_DAYS)
    logger.info("Customers: %d, SKU pool: %d unique", len(customer_ids), len(CORE_SKUS))

    all_so_ids: List[str] = []
    _completed_so_ids: set = set()  # track completed SOs to skip in ship/invoice loops

    # Accumulators for weekly summary logging
    wk_sos = wk_mos = wk_shipped = wk_invoiced = wk_restocked = wk_received = 0

    # ------------------------------------------------------------------
    # Daily loop
    # ------------------------------------------------------------------
    for day in range(TOTAL_DAYS):
        opd = _orders_per_day_for_day(day)
        week_num = day // 7 + 1

        # Log weekly summary at week boundaries
        if day > 0 and day % 7 == 0:
            logger.info(
                "  Week %d summary — SOs: %d, MOs: %d, Shipped: %d, "
                "Invoiced: %d, Restocked: %d POs, Received: %d POs",
                week_num - 1, wk_sos, wk_mos, wk_shipped,
                wk_invoiced, wk_restocked, wk_received,
            )
            wk_sos = wk_mos = wk_shipped = wk_invoiced = 0
            wk_restocked = wk_received = 0

        with db_conn():  # reuse one connection per day

            # ----- Morning (08:00) — Receive & start production -----
            set_day_time(8)

            # 1. Receive POs that have arrived
            n_rcv = _receive_due_pos()
            wk_received += n_rcv

            # 2. Start any MOs that are ready (promoted overnight or new stock)
            started = _start_ready_mos()

            # ----- Mid-morning (10:00) — New sales orders -----
            set_day_time(10)

            # 3. Create today's sales orders
            day_sos = _create_day_orders(customer_ids, sku_pool, opd)
            all_so_ids.extend(day_sos)
            wk_sos += len(day_sos)

            # 4. Trigger + start production for new orders
            mo_ids = trigger_production_for_orders(day_sos, start=True)
            wk_mos += len(mo_ids)

            # ----- Afternoon (14:00) — Ship & restock -----
            set_day_time(14)

            # 5. Ship orders with available FG stock
            pending_ship = [sid for sid in all_so_ids if sid not in _completed_so_ids]
            ship_ids = _ship_ready_orders(pending_ship)
            wk_shipped += len(ship_ids)

            # 6. Restock raw materials (daily check)
            try:
                rs = restock_materials()
                n_po = rs.get("purchase_orders_created", 0)
                wk_restocked += n_po
            except Exception as e:
                logger.debug("Restock skipped: %s", e)

            # ----- Late afternoon (16:00) — Invoice & payment -----
            set_day_time(16)

            # 7. Invoice shipped orders
            pending_inv = [sid for sid in all_so_ids if sid not in _completed_so_ids]
            inv_n = _invoice_shipped_orders(pending_inv, completed_set=_completed_so_ids)
            wk_invoiced += inv_n

            # ----- End of day — advance clock by 1 day -----
            # Side-effects: complete MOs past ETA, deliver shipments,
            # expire quotes, promote waiting→ready MOs, mark overdue invoices
            set_day_time(18)
            advance_and_settle(hours=14)  # 18:00 → next day 08:00

        # Log daily status snapshot (every day for first week, then weekly)
        if day < 7 or day % 7 == 6:
            _log_daily_status(day)

    # Final weekly summary
    logger.info(
        "  Week %d summary — SOs: %d, MOs: %d, Shipped: %d, "
        "Invoiced: %d, Restocked: %d POs, Received: %d POs",
        (TOTAL_DAYS - 1) // 7 + 1, wk_sos, wk_mos, wk_shipped,
        wk_invoiced, wk_restocked, wk_received,
    )

    # ------------------------------------------------------------------
    # Standalone quotes (scattered over last 2 weeks of the period)
    # ------------------------------------------------------------------
    logger.info("Creating standalone quotes...")
    with db_conn():
        for _ in range(15):
            cust = random.choice(customer_ids)
            ship_to = get_customer_ship_to(cust)
            lines = pick_random_lines(CORE_SKUS, n_lines=random.randint(1, 2),
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
                logger.warning("Quote failed: %s", e)

    # ------------------------------------------------------------------
    # Emails
    # ------------------------------------------------------------------
    logger.info("Creating emails...")
    templates = [
        ("Order Confirmation - {so_id}",
         "Dear {name},\n\nThank you for your order {so_id}. "
         "It is being processed.\n\nBest regards,\nDuck Inc Sales Team"),
        ("Welcome to Duck Inc!",
         "Dear {name},\n\nWelcome aboard! Browse our premium rubber "
         "ducks at any time.\n\nBest regards,\nDuck Inc Sales Team"),
        ("Your Shipment is on its Way",
         "Dear {name},\n\nGreat news! Your order {so_id} has been "
         "dispatched.\n\nBest regards,\nDuck Inc Logistics"),
    ]
    with db_conn() as conn:
        sample = conn.execute(
            "SELECT so.id, so.customer_id, c.name FROM sales_orders so "
            "JOIN customers c ON so.customer_id = c.id "
            "ORDER BY RANDOM() LIMIT 10",
        ).fetchall()
    for row in sample:
        t = random.choice(templates)
        subj = t[0].format(so_id=row["id"], name=row["name"])
        body = t[1].format(so_id=row["id"], name=row["name"])
        try:
            send_email(customer_id=row["customer_id"], subject=subj,
                       body=body, sales_order_id=row["id"])
        except Exception as e:
            logger.warning("Email failed: %s", e)

    # ------------------------------------------------------------------
    # Final settle (2 days for in-flight deliveries)
    # ------------------------------------------------------------------
    advance_and_settle(days=2)

    with db_conn() as conn:
        counts = {}
        for tbl in ["sales_orders", "production_orders", "invoices", "quotes",
                     "shipments", "purchase_orders", "emails", "payments"]:
            counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]

    logger.info("=== S01 Complete ===")
    for k, v in counts.items():
        logger.info("  %-22s %d", k, v)
    logger.info("  Sim time:          %s", current_time())

    return {
        "s01_so_ids": all_so_ids,
        "core_skus": CORE_SKUS,
    }
