"""Fulfillment service — order-to-cash cycle operations.

Covers the operational steps that move a confirmed sales order through to
completion: starting production, receiving purchased materials, shipping
finished goods, and invoicing / collecting payment.
"""

import logging
import random
from types import SimpleNamespace
from typing import List, Optional

from services._base import db_conn
from utils import ship_to_dict

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Production readiness
# ---------------------------------------------------------------------------

def start_ready_mos() -> int:
    """Find ready production orders and start them. Returns count started."""
    from services.production import production_service
    from services.activity import activity_service

    with db_conn() as conn:
        ready = conn.execute(
            "SELECT id FROM production_orders WHERE status = 'ready'"
        ).fetchall()
    started = 0
    for mo in ready:
        result = production_service.start_order(mo["id"])
        if result["status"] == "in_progress":
            started += 1
            activity_service.log_activity(
                "scenario", "production",
                "production_order.started",
                "production_order", mo["id"],
            )
    return started


# ---------------------------------------------------------------------------
# Purchase order receiving
# ---------------------------------------------------------------------------

def receive_due_pos(as_of_date: str) -> int:
    """Receive POs whose expected_delivery has passed. Returns count received.

    Args:
        as_of_date: ISO date string (YYYY-MM-DD) used as the cut-off.
    """
    from services.purchase import purchase_service
    from services.activity import activity_service

    with db_conn() as conn:
        due = conn.execute(
            "SELECT id FROM purchase_orders "
            "WHERE status = 'ordered' AND expected_delivery <= ?",
            (as_of_date,),
        ).fetchall()
    received = 0
    for po in due:
        try:
            purchase_service.receive(
                po["id"],
                warehouse=config.WAREHOUSE_DEFAULT,
                location=config.LOC_RAW_MATERIAL_RECV,
            )
            received += 1
            activity_service.log_activity(
                "scenario", "purchasing",
                "purchase_order.received",
                "purchase_order", po["id"],
            )
        except Exception as e:
            logger.debug("PO %s receive skipped: %s", po["id"], e)
    return received


# ---------------------------------------------------------------------------
# Shipping
# ---------------------------------------------------------------------------

def ship_ready_orders(
    so_ids: List[str],
    sim_date_fn=None,
    future_date_fn=None,
) -> List[str]:
    """Ship SOs whose items are in stock. Returns shipment IDs.

    Args:
        so_ids: Sales order IDs to consider for shipping.
        sim_date_fn: Callable returning current sim date (YYYY-MM-DD).
                     Required when called from a simulation context.
        future_date_fn: Callable(days) returning a future date string.
                        Required when called from a simulation context.
    """
    from services.logistics import logistics_service
    from services.activity import activity_service

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
            today = sim_date_fn() if sim_date_fn else None
            arrival = future_date_fn(random.randint(2, 4)) if future_date_fn else None
            ship = logistics_service.create_shipment(
                ship_from={"warehouse": config.WAREHOUSE_DEFAULT},
                ship_to=ship_to,
                planned_departure=today,
                planned_arrival=arrival,
                packages=pkgs,
                reference={"type": "sales_order", "id": so_id},
            )
            logistics_service.dispatch_shipment(ship["shipment_id"])
            ship_ids.append(ship["shipment_id"])
            activity_service.log_activity(
                "scenario", "logistics",
                "shipment.dispatched",
                "shipment", ship["shipment_id"],
                {"sales_order_id": so_id},
            )
        except Exception as e:
            logger.warning("Ship failed for %s: %s", so_id, e)
    return ship_ids


# ---------------------------------------------------------------------------
# Invoicing & payment
# ---------------------------------------------------------------------------

def invoice_shipped_orders(
    so_ids: List[str],
    pay_pct: float = 0.75,
    completed_set: Optional[set] = None,
) -> int:
    """Invoice SOs that have dispatched/delivered shipments. Returns count.

    Args:
        so_ids: Sales order IDs to consider for invoicing.
        pay_pct: Probability that payment is recorded immediately.
        completed_set: Optional set to which completed SO IDs are added.
    """
    from services.invoice import invoice_service
    from services.sales import sales_service
    from services.activity import activity_service

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
            activity_service.log_activity(
                "scenario", "billing",
                "invoice.issued",
                "invoice", inv["invoice_id"],
                {"sales_order_id": so_id, "total": inv["total"]},
            )
            if random.random() < pay_pct:
                invoice_service.record_payment(
                    invoice_id=inv["invoice_id"],
                    amount=inv["total"],
                    payment_method=random.choice([
                        "bank_transfer", "bank_transfer", "credit_card",
                    ]),
                    reference=f"VIR-{so_id}",
                )
                activity_service.log_activity(
                    "scenario", "billing",
                    "payment.recorded",
                    "invoice", inv["invoice_id"],
                    {"amount": inv["total"]},
                )
            sales_service.complete_order(so_id)
            activity_service.log_activity(
                "scenario", "sales",
                "sales_order.completed",
                "sales_order", so_id,
            )
            if completed_set is not None:
                completed_set.add(so_id)
        except Exception as e:
            logger.warning("Invoice/pay failed for %s: %s", so_id, e)
    return count


# ---------------------------------------------------------------------------
# Service singleton
# ---------------------------------------------------------------------------

fulfillment_service = SimpleNamespace(
    start_ready_mos=start_ready_mos,
    receive_due_pos=receive_due_pos,
    ship_ready_orders=ship_ready_orders,
    invoice_shipped_orders=invoice_shipped_orders,
)
FulfillmentService = fulfillment_service
