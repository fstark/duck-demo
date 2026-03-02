"""Service for managing simulated time."""

from types import SimpleNamespace
from typing import Any, Dict, Optional

import config
from services._base import db_conn


def get_current_time() -> str:
    """Get current simulation time."""
    with db_conn() as conn:
        result = conn.execute(
            "SELECT sim_time FROM simulation_state WHERE id = 1"
        ).fetchone()
        return result[0]

def advance_time(
    hours: Optional[float] = None,
    days: Optional[int] = None,
    to_time: Optional[str] = None,
    side_effects: bool = True,
) -> Dict[str, Any]:
    """
    Advance the simulated time forward.

    Args:
        hours: Number of hours to advance
        days: Number of days to advance
        to_time: ISO datetime to set time to
        side_effects: When True (default) auto-process business events:
            - complete in_progress production orders whose eta_finish has passed
            - deliver in_transit shipments whose planned_arrival has passed
            - expire sent quotes whose valid_until has passed
            - promote waiting production orders to ready when materials available
            - mark overdue invoices

    Returns:
        Dictionary with old_time, new_time, and side-effect counts
    """
    with db_conn() as conn:
        old_time = conn.execute(
            "SELECT sim_time FROM simulation_state WHERE id = 1"
        ).fetchone()[0]

        if to_time:
            conn.execute(
                "UPDATE simulation_state SET sim_time = ? WHERE id = 1",
                (to_time,)
            )
        elif hours:
            conn.execute(
                "UPDATE simulation_state SET sim_time = datetime(sim_time, ? || ' hours') WHERE id = 1",
                (f'+{hours}',)
            )
        elif days:
            conn.execute(
                "UPDATE simulation_state SET sim_time = datetime(sim_time, ? || ' days') WHERE id = 1",
                (f'+{days}',)
            )
        else:
            raise ValueError("Must specify hours, days, or to_time")

        conn.commit()

        new_time = conn.execute(
            "SELECT sim_time FROM simulation_state WHERE id = 1"
        ).fetchone()[0]

        result: Dict[str, Any] = {
            "old_time": old_time,
            "new_time": new_time,
        }

        if not side_effects:
            return result

        new_date = new_time[:10]

        # --- Side-effect 1: mark overdue invoices ---
        from services.invoice import invoice_service
        overdue_count = invoice_service.mark_overdue(new_time)
        if overdue_count > 0:
            result["invoices_marked_overdue"] = overdue_count

        # --- Side-effect 2: auto-complete production orders ---
        # Phase A: tick operations for all in-progress MOs based on elapsed time
        from services.production import advance_operations
        from db import generate_id
        completed_mos = []
        all_in_progress = conn.execute(
            "SELECT po.id, po.item_id, r.output_qty "
            "FROM production_orders po "
            "JOIN recipes r ON po.recipe_id = r.id "
            "WHERE po.status = 'in_progress' "
            "ORDER BY po.started_at",
        ).fetchall()
        for mo in all_in_progress:
            result = advance_operations(mo["id"], new_time, conn=conn)
            if result["all_done"]:
                conn.execute(
                    "UPDATE production_orders SET status = 'completed', "
                    "completed_at = ?, qty_produced = ?, current_operation = NULL WHERE id = ?",
                    (new_time, mo["output_qty"], mo["id"]),
                )
                stock_id = generate_id(conn, "STK", "stock")
                conn.execute(
                    "INSERT INTO stock (id, item_id, warehouse, location, on_hand) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (stock_id, mo["item_id"], config.LOC_FINISHED_GOODS, config.LOC_PRODUCTION_OUT, mo["output_qty"]),
                )
                completed_mos.append(mo["id"])

        # Phase B: safety-net — force-complete MOs past eta_finish that
        # weren't caught by operation ticking (e.g. missing operation rows)
        stragglers = conn.execute(
            "SELECT po.id, po.item_id, po.started_at, r.output_qty "
            "FROM production_orders po "
            "JOIN recipes r ON po.recipe_id = r.id "
            "WHERE po.status = 'in_progress' AND po.eta_finish IS NOT NULL AND po.eta_finish <= ?",
            (new_date,)
        ).fetchall()
        for mo in stragglers:
            from services.production import _finalize_all_operations
            _finalize_all_operations(conn, mo["id"], mo["started_at"], new_time)
            conn.execute(
                "UPDATE production_orders SET status = 'completed', "
                "completed_at = ?, qty_produced = ?, current_operation = NULL WHERE id = ?",
                (new_time, mo["output_qty"], mo["id"]),
            )
            stock_id = generate_id(conn, "STK", "stock")
            conn.execute(
                "INSERT INTO stock (id, item_id, warehouse, location, on_hand) "
                "VALUES (?, ?, ?, ?, ?)",
                (stock_id, mo["item_id"], config.LOC_FINISHED_GOODS, config.LOC_PRODUCTION_OUT, mo["output_qty"]),
            )
            completed_mos.append(mo["id"])
        if completed_mos:
            conn.commit()
            result["production_orders_completed"] = completed_mos

        # --- Side-effect 3: auto-deliver shipments ---
        delivered_ships = []
        in_transit = conn.execute(
            "SELECT id FROM shipments "
            "WHERE status = 'in_transit' AND planned_arrival IS NOT NULL AND planned_arrival <= ?",
            (new_date,)
        ).fetchall()
        for ship in in_transit:
            conn.execute(
                "UPDATE shipments SET status = 'delivered', delivered_at = ? WHERE id = ?",
                (new_time, ship["id"],)
            )
            delivered_ships.append(ship["id"])
        if delivered_ships:
            conn.commit()
            result["shipments_delivered"] = delivered_ships

        # --- Side-effect 4: expire quotes ---
        expired_count = conn.execute(
            "UPDATE quotes SET status = 'expired' "
            "WHERE status = 'sent' AND valid_until IS NOT NULL AND valid_until < ?",
            (new_date,)
        ).rowcount
        if expired_count > 0:
            result["quotes_expired"] = expired_count
        conn.commit()  # release write lock before update_readiness opens a new connection

        # --- Side-effect 5: promote waiting → ready production orders ---
        from services.production import production_service
        readiness = production_service.update_readiness()
        if readiness["promoted_to_ready"]:
            result["production_orders_promoted"] = readiness["promoted_to_ready"]

        return result


# Namespace for backward compatibility
simulation_service = SimpleNamespace(
    get_current_time=get_current_time,
    advance_time=advance_time,
)
SimulationService = simulation_service
