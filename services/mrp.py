"""MRP (Material Requirements Planning) service.

Textbook MRP net-requirements regeneration: for every finished-good with
unshipped sales demand, compute:

    net_req = gross_demand − on_hand − scheduled_receipts (open MOs)

and create production orders for any positive shortfall.
"""

import logging
from types import SimpleNamespace

from services._base import db_conn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def replan_unfulfilled_orders() -> int:
    """MRP net requirements: create MOs for the global shortfall across unshipped SOs.

    Scans all confirmed sales orders that have not yet been shipped,
    aggregates demand per finished-good item, and compares against on-hand
    stock plus scheduled receipts (open MOs).  Creates production orders for
    any positive net requirement, linked to the oldest waiting sales order
    for traceability.

    Returns count of MOs created.
    """
    # Lazy imports to avoid circular dependencies
    from services.production import production_service
    from services.activity import activity_service

    with db_conn() as conn:
        # All confirmed SOs that have no dispatched / delivered shipment
        unshipped = conn.execute(
            "SELECT so.id FROM sales_orders so "
            "WHERE so.status = 'confirmed' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM sales_order_shipments sos "
            "  JOIN shipments s ON s.id = sos.shipment_id "
            "  WHERE sos.sales_order_id = so.id "
            "  AND s.status IN ('in_transit','delivered')"
            ")",
        ).fetchall()
        unshipped_ids = [r["id"] for r in unshipped]

        if not unshipped_ids:
            return 0

        # Aggregate demand per item across all un-shipped SOs
        placeholders = ",".join("?" * len(unshipped_ids))
        demand_rows = conn.execute(
            f"SELECT sol.item_id, SUM(sol.qty) as total_qty, "
            f"MIN(sol.sales_order_id) as first_so_id "
            f"FROM sales_order_lines sol "
            f"WHERE sol.sales_order_id IN ({placeholders}) "
            f"GROUP BY sol.item_id",
            unshipped_ids,
        ).fetchall()

        mo_count = 0
        for row in demand_rows:
            item_id = row["item_id"]
            gross = int(row["total_qty"])
            so_id = row["first_so_id"]

            on_hand = conn.execute(
                "SELECT COALESCE(SUM(on_hand), 0) FROM stock WHERE item_id = ?",
                (item_id,),
            ).fetchone()[0]

            # Scheduled receipts: output from MOs still in the pipeline
            scheduled = conn.execute(
                "SELECT COALESCE(SUM(r.output_qty), 0) "
                "FROM production_orders po "
                "JOIN recipes r ON po.recipe_id = r.id "
                "WHERE po.status IN ('ready','waiting','in_progress') "
                "AND r.output_item_id = ?",
                (item_id,),
            ).fetchone()[0]

            net_req = gross - on_hand - scheduled
            if net_req <= 0:
                continue

            # Find recipe and batch size for this item
            recipe_row = conn.execute(
                "SELECT id, output_qty FROM recipes "
                "WHERE output_item_id = ? LIMIT 1",
                (item_id,),
            ).fetchone()
            if not recipe_row:
                continue

            batch_size = int(recipe_row["output_qty"])
            batches = max(1, -(-net_req // batch_size))  # ceiling division

            for _ in range(batches):
                mo = production_service.create_order(
                    recipe_id=recipe_row["id"],
                    sales_order_id=so_id,
                    notes=f"MRP re-plan for {so_id}",
                )
                mo_count += 1
                activity_service.log_activity(
                    "scenario", "production",
                    "production_order.created",
                    "production_order", mo["production_order_id"],
                    {"sales_order_id": so_id,
                     "recipe_id": recipe_row["id"],
                     "replan": True},
                )
                if mo["status"] == "ready":
                    production_service.start_order(mo["production_order_id"])
                    activity_service.log_activity(
                        "scenario", "production",
                        "production_order.started",
                        "production_order", mo["production_order_id"],
                    )

    if mo_count:
        logger.info("  MRP re-plan: created %d MOs for unshipped demand", mo_count)
    return mo_count


# ---------------------------------------------------------------------------
# Service singleton
# ---------------------------------------------------------------------------

mrp_service = SimpleNamespace(
    replan_unfulfilled_orders=replan_unfulfilled_orders,
)
MrpService = mrp_service
