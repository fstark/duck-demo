"""Service for production order operations."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from db import dict_rows, generate_id
from utils import ui_href
from services._base import db_conn


def get_statistics() -> Dict[str, Any]:
    """Get production statistics."""
    with db_conn() as conn:
        total_production = conn.execute("SELECT COUNT(*) as count FROM production_orders").fetchone()["count"]
        status_rows = dict_rows(conn.execute("SELECT status, COUNT(*) as count FROM production_orders GROUP BY status ORDER BY count DESC"))
        total_qty = conn.execute("SELECT SUM(r.output_qty) as total FROM production_orders po JOIN recipes r ON po.recipe_id = r.id").fetchone()["total"] or 0
        top_items = dict_rows(conn.execute("SELECT i.sku, i.name, SUM(r.output_qty) as total_qty, COUNT(*) as order_count FROM production_orders po JOIN recipes r ON po.recipe_id = r.id JOIN items i ON po.item_id = i.id GROUP BY i.id, i.sku, i.name ORDER BY total_qty DESC LIMIT 10"))
        upcoming = dict_rows(conn.execute("SELECT i.sku, i.name, r.output_qty as qty, po.eta_finish, po.status FROM production_orders po JOIN recipes r ON po.recipe_id = r.id JOIN items i ON po.item_id = i.id WHERE po.eta_finish >= date('now') AND po.eta_finish <= date('now', '+60 days') ORDER BY po.eta_finish LIMIT 20"))
        return {"total_production_orders": total_production, "production_orders_by_status": status_rows, "total_quantity_in_production": total_qty, "top_items_in_production": top_items, "upcoming_production": upcoming}


def get_order_status(production_order_id: str) -> Dict[str, Any]:
    """Return status of a production order."""
    with db_conn() as conn:
        query = "SELECT po.*, i.name as item_name, i.sku as item_sku, i.type as item_type FROM production_orders po LEFT JOIN items i ON po.item_id = i.id WHERE po.id = ?"
        row = conn.execute(query, (production_order_id,)).fetchone()
        if not row:
            return {"error": "Production order not found", "production_order_id": production_order_id}
        result = dict(row)
        result["ui_url"] = ui_href("production-orders", production_order_id)
        operations = dict_rows(conn.execute("SELECT * FROM production_operations WHERE production_order_id = ? ORDER BY sequence_order", (production_order_id,)))
        result["operations"] = operations
        if result.get("recipe_id"):
            recipe = conn.execute("SELECT r.*, i.sku as output_sku, i.name as output_name FROM recipes r JOIN items i ON r.output_item_id = i.id WHERE r.id = ?", (result["recipe_id"],)).fetchone()
            if recipe:
                result["recipe"] = dict(recipe)
                ingredients = dict_rows(conn.execute("SELECT ri.*, i.sku as ingredient_sku, i.name as ingredient_name, i.uom as ingredient_uom FROM recipe_ingredients ri JOIN items i ON ri.input_item_id = i.id WHERE ri.recipe_id = ?", (result["recipe_id"],)))
                result["recipe"]["ingredients"] = ingredients
                recipe_operations = dict_rows(conn.execute("SELECT * FROM recipe_operations WHERE recipe_id = ? ORDER BY sequence_order", (result["recipe_id"],)))
                result["recipe"]["operations"] = recipe_operations
        return result


def find_orders_by_date_range(start_date: str, end_date: str, limit: int) -> List[Dict[str, Any]]:
    """Retrieve production orders by date range."""
    with db_conn() as conn:
        query = "SELECT po.*, i.name as item_name, i.sku as item_sku, i.type as item_type FROM production_orders po LEFT JOIN items i ON po.item_id = i.id WHERE po.eta_finish >= ? AND po.eta_finish <= ? ORDER BY po.eta_finish LIMIT ?"
        rows = conn.execute(query, (start_date, end_date, limit)).fetchall()
        return [dict(row) for row in rows]


def create_order(recipe_id: str, sales_order_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """Create a new production order for a sales order."""
    from services.recipe import recipe_service
    from services.inventory import inventory_service
    from services.simulation import simulation_service

    with db_conn() as conn:
        recipe_data = recipe_service.get_recipe(recipe_id)
        shortfalls = []
        for ing in recipe_data["ingredients"]:
            qty_needed = ing["input_qty"]
            check = inventory_service.check_availability(ing["ingredient_sku"], qty_needed)
            if not check["is_available"]:
                shortfalls.append({"ingredient_sku": ing["ingredient_sku"], "ingredient_name": ing["ingredient_name"], "qty_needed": qty_needed, "qty_available": check["qty_available"], "shortfall": check["shortfall"]})
        status = "waiting" if shortfalls else "ready"
        sim_time = simulation_service.get_current_time()
        sim_date = datetime.fromisoformat(sim_time).date()
        prod_time_days = recipe_data["production_time_hours"] / 24.0
        eta_finish = (sim_date + timedelta(days=1 + int(prod_time_days))).isoformat()
        eta_ship = (sim_date + timedelta(days=2 + int(prod_time_days))).isoformat()
        order_id = generate_id(conn, "MO", "production_orders")
        conn.execute("INSERT INTO production_orders (id, sales_order_id, recipe_id, item_id, status, eta_finish, eta_ship) VALUES (?, ?, ?, ?, ?, ?, ?)", (order_id, sales_order_id, recipe_id, recipe_data["output_item_id"], status, eta_finish, eta_ship))
        for op in recipe_data["operations"]:
            pop_id = generate_id(conn, "POP", "production_operations")
            conn.execute("INSERT INTO production_operations (id, production_order_id, recipe_operation_id, sequence_order, operation_name, duration_hours, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (pop_id, order_id, op["id"], op["sequence_order"], op["operation_name"], op["duration_hours"], "pending"))
        conn.commit()
        return {"production_order_id": order_id, "recipe_id": recipe_id, "output_item": recipe_data["output_sku"], "output_qty": recipe_data["output_qty"], "status": status, "eta_finish": eta_finish, "eta_ship": eta_ship, "ingredient_shortfalls": shortfalls, "ui_url": ui_href("production-orders", order_id)}


def start_order(production_order_id: str) -> Dict[str, Any]:
    """Start a production order.

    Transitions status from 'ready' to 'in_progress', sets started_at,
    and **deducts recipe ingredients** from stock.

    Returns a dict with ``status`` of ``'in_progress'`` on success, or
    ``'waiting_for_stock'`` with ``shortfalls`` when materials are
    insufficient (no exception raised for stock shortages).
    """
    from services.inventory import inventory_service
    from services.simulation import simulation_service

    with db_conn() as conn:
        order = conn.execute("SELECT * FROM production_orders WHERE id = ?", (production_order_id,)).fetchone()
        if not order:
            raise ValueError(f"Production order {production_order_id} not found")
        if order["status"] != "ready":
            raise ValueError(f"Production order {production_order_id} is not ready (current status: {order['status']})")

        # Pre-check ingredient availability before deducting
        ingredients = conn.execute(
            "SELECT ri.input_item_id, ri.input_qty, i.sku "
            "FROM recipe_ingredients ri "
            "JOIN items i ON ri.input_item_id = i.id "
            "WHERE ri.recipe_id = ?",
            (order["recipe_id"],)
        ).fetchall()

        shortfalls = []
        for ing in ingredients:
            total = conn.execute(
                "SELECT COALESCE(SUM(on_hand), 0) as total FROM stock WHERE item_id = ?",
                (ing["input_item_id"],)
            ).fetchone()["total"]
            if total < ing["input_qty"]:
                shortfalls.append({
                    "item_id": ing["input_item_id"],
                    "sku": ing["sku"],
                    "needed": ing["input_qty"],
                    "available": total,
                })

        if shortfalls:
            return {
                "production_order_id": production_order_id,
                "status": "waiting_for_stock",
                "shortfalls": shortfalls,
                "message": f"MO {production_order_id} waiting for stock",
            }

        # All ingredients available — deduct and start
        for ing in ingredients:
            inventory_service.deduct_stock(ing["input_item_id"], ing["input_qty"], conn=conn)

        first_op = conn.execute("SELECT operation_name FROM recipe_operations WHERE recipe_id = ? ORDER BY sequence_order LIMIT 1", (order["recipe_id"],)).fetchone()
        current_operation = first_op["operation_name"] if first_op else None
        sim_time = simulation_service.get_current_time()
        conn.execute("UPDATE production_orders SET status = 'in_progress', started_at = ?, current_operation = ? WHERE id = ?", (sim_time, current_operation, production_order_id))
        # Mark the first production operation as in_progress
        conn.execute(
            "UPDATE production_operations SET status = 'in_progress', started_at = ? "
            "WHERE production_order_id = ? AND sequence_order = ("
            "  SELECT MIN(sequence_order) FROM production_operations WHERE production_order_id = ?"
            ")",
            (sim_time, production_order_id, production_order_id),
        )
        conn.commit()
        return {"production_order_id": production_order_id, "status": "in_progress", "current_operation": current_operation, "message": f"Production order {production_order_id} started"}


def complete_order(production_order_id: str, qty_produced: int, warehouse: str, location: str) -> Dict[str, Any]:
    """Complete a production order and add finished goods to stock."""
    from services.simulation import simulation_service

    with db_conn() as conn:
        order = conn.execute("SELECT * FROM production_orders WHERE id = ?", (production_order_id,)).fetchone()
        if not order:
            raise ValueError(f"Production order {production_order_id} not found")
        if order["status"] == "completed":
            raise ValueError(f"Production order {production_order_id} already completed")
        sim_time = simulation_service.get_current_time()
        # Finalize all operations that are not yet completed
        _finalize_all_operations(conn, production_order_id, order["started_at"], sim_time)
        conn.execute("UPDATE production_orders SET status = 'completed', completed_at = ?, qty_produced = ?, current_operation = NULL WHERE id = ?", (sim_time, qty_produced, production_order_id))
        stock_id = generate_id(conn, "STK", "stock")
        conn.execute("INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)", (stock_id, order["item_id"], warehouse, location, qty_produced))
        conn.commit()
        return {"production_order_id": production_order_id, "status": "completed", "qty_produced": qty_produced, "stock_id": stock_id, "warehouse": warehouse, "location": location, "message": f"Production order {production_order_id} completed, {qty_produced} units added to stock"}


def update_readiness() -> Dict[str, Any]:
    """Check 'waiting' production orders and promote to 'ready' if materials are now available."""
    from services.inventory import inventory_service

    with db_conn() as conn:
        waiting = conn.execute(
            "SELECT po.id, po.recipe_id FROM production_orders po WHERE po.status = 'waiting'"
        ).fetchall()

        promoted = []
        for wo in waiting:
            ingredients = conn.execute(
                "SELECT ri.input_item_id, ri.input_qty, i.sku as ingredient_sku "
                "FROM recipe_ingredients ri "
                "JOIN items i ON ri.input_item_id = i.id "
                "WHERE ri.recipe_id = ?",
                (wo["recipe_id"],)
            ).fetchall()

            all_available = True
            for ing in ingredients:
                check = inventory_service.check_availability(ing["ingredient_sku"], ing["input_qty"])
                if not check["is_available"]:
                    all_available = False
                    break

            if all_available:
                conn.execute("UPDATE production_orders SET status = 'ready' WHERE id = ?", (wo["id"],))
                promoted.append(wo["id"])

        if promoted:
            conn.commit()
        return {"checked": len(waiting), "promoted_to_ready": promoted}


def _finalize_all_operations(conn, production_order_id: str, mo_started_at: Optional[str], completed_at: str) -> None:
    """Mark all non-completed operations as completed with proportional timestamps.

    Timestamps are spread across the MO's duration based on each operation's
    ``duration_hours``.  Operations already completed are left untouched.
    """
    ops = dict_rows(conn.execute(
        "SELECT id, sequence_order, duration_hours, status, started_at "
        "FROM production_operations WHERE production_order_id = ? ORDER BY sequence_order",
        (production_order_id,),
    ))
    if not ops:
        return

    start_dt = datetime.fromisoformat(mo_started_at) if mo_started_at else datetime.fromisoformat(completed_at)
    end_dt = datetime.fromisoformat(completed_at)
    total_hours = sum(op["duration_hours"] for op in ops) or 1.0
    elapsed = end_dt - start_dt
    if elapsed.total_seconds() <= 0:
        elapsed = timedelta(hours=total_hours)
        start_dt = end_dt - elapsed

    cursor = start_dt
    for op in ops:
        if op["status"] == "completed":
            # already done — advance cursor past its duration
            frac = op["duration_hours"] / total_hours
            cursor += elapsed * frac
            continue
        op_start = op.get("started_at")
        op_start_ts = op_start if op_start else cursor.isoformat()
        frac = op["duration_hours"] / total_hours
        cursor += elapsed * frac
        op_end_ts = cursor.isoformat()
        conn.execute(
            "UPDATE production_operations SET status = 'completed', "
            "started_at = ?, completed_at = ? WHERE id = ?",
            (op_start_ts, op_end_ts, op["id"]),
        )


def advance_operations(production_order_id: str, sim_time: str, conn=None) -> Dict[str, Any]:
    """Tick through operations for an in-progress MO based on elapsed time.

    Walks the operation list in sequence order.  Each operation's start is
    computed from the MO ``started_at`` plus the cumulative duration of all
    preceding operations.  Operations whose cumulative end-time has passed
    are marked *completed*; the first operation whose window spans the
    current ``sim_time`` is marked *in_progress*; the rest stay *pending*.

    Returns a dict with ``all_done`` (bool) and the ``current_operation``
    name (or ``None`` when all operations are finished).
    """
    def _inner(c):
        mo = c.execute(
            "SELECT started_at FROM production_orders WHERE id = ?",
            (production_order_id,),
        ).fetchone()
        if not mo or not mo["started_at"]:
            return {"all_done": False, "current_operation": None}

        mo_start = datetime.fromisoformat(mo["started_at"])
        now = datetime.fromisoformat(sim_time)

        ops = dict_rows(c.execute(
            "SELECT id, sequence_order, operation_name, duration_hours, status "
            "FROM production_operations WHERE production_order_id = ? ORDER BY sequence_order",
            (production_order_id,),
        ))
        if not ops:
            return {"all_done": True, "current_operation": None}

        cursor = mo_start
        current_operation = None
        all_done = True

        for op in ops:
            op_start = cursor
            op_end = cursor + timedelta(hours=op["duration_hours"])

            if now >= op_end:
                # This operation should be completed
                if op["status"] != "completed":
                    c.execute(
                        "UPDATE production_operations SET status = 'completed', "
                        "started_at = ?, completed_at = ? WHERE id = ?",
                        (op_start.isoformat(), op_end.isoformat(), op["id"]),
                    )
            elif now >= op_start:
                # This operation is currently in progress
                if op["status"] != "in_progress":
                    c.execute(
                        "UPDATE production_operations SET status = 'in_progress', "
                        "started_at = ? WHERE id = ?",
                        (op_start.isoformat(), op["id"]),
                    )
                current_operation = op["operation_name"]
                all_done = False
            else:
                # Future operation — stays pending
                all_done = False
                if current_operation is None:
                    current_operation = op["operation_name"]

            cursor = op_end

        # Update current_operation on the MO header
        c.execute(
            "UPDATE production_orders SET current_operation = ? WHERE id = ?",
            (current_operation, production_order_id),
        )
        return {"all_done": all_done, "current_operation": current_operation}

    if conn is not None:
        return _inner(conn)
    with db_conn() as c:
        result = _inner(c)
        c.commit()
        return result


def complete_operation(production_order_id: str) -> Dict[str, Any]:
    """Manually complete the current in-progress operation and advance to the next.

    If the completed operation is the last one, the MO itself is **not**
    automatically completed — call ``complete_order`` separately so the
    caller can specify ``qty_produced`` and stock location.

    Returns a dict describing what happened.
    """
    from services.simulation import simulation_service

    with db_conn() as conn:
        order = conn.execute(
            "SELECT * FROM production_orders WHERE id = ?",
            (production_order_id,),
        ).fetchone()
        if not order:
            raise ValueError(f"Production order {production_order_id} not found")
        if order["status"] != "in_progress":
            raise ValueError(
                f"Production order {production_order_id} is not in_progress "
                f"(current status: {order['status']})"
            )

        sim_time = simulation_service.get_current_time()

        # Find the current in-progress operation
        current_op = conn.execute(
            "SELECT * FROM production_operations "
            "WHERE production_order_id = ? AND status = 'in_progress' "
            "ORDER BY sequence_order LIMIT 1",
            (production_order_id,),
        ).fetchone()
        if not current_op:
            return {
                "production_order_id": production_order_id,
                "status": "no_in_progress_operation",
                "message": "No in-progress operation found to complete",
            }

        # Complete the current operation
        conn.execute(
            "UPDATE production_operations SET status = 'completed', completed_at = ? WHERE id = ?",
            (sim_time, current_op["id"]),
        )

        # Advance to the next pending operation
        next_op = conn.execute(
            "SELECT * FROM production_operations "
            "WHERE production_order_id = ? AND status = 'pending' "
            "ORDER BY sequence_order LIMIT 1",
            (production_order_id,),
        ).fetchone()

        if next_op:
            conn.execute(
                "UPDATE production_operations SET status = 'in_progress', started_at = ? WHERE id = ?",
                (sim_time, next_op["id"]),
            )
            conn.execute(
                "UPDATE production_orders SET current_operation = ? WHERE id = ?",
                (next_op["operation_name"], production_order_id),
            )
            conn.commit()
            return {
                "production_order_id": production_order_id,
                "status": "advanced",
                "completed_operation": current_op["operation_name"],
                "next_operation": next_op["operation_name"],
                "message": (
                    f"Operation '{current_op['operation_name']}' completed. "
                    f"Now on '{next_op['operation_name']}'."
                ),
            }
        else:
            # Last operation completed — MO can be completed
            conn.execute(
                "UPDATE production_orders SET current_operation = NULL WHERE id = ?",
                (production_order_id,),
            )
            conn.commit()
            return {
                "production_order_id": production_order_id,
                "status": "all_operations_done",
                "completed_operation": current_op["operation_name"],
                "message": (
                    f"Operation '{current_op['operation_name']}' completed. "
                    f"All operations finished — MO is ready to be completed."
                ),
            }


# Namespace for backward compatibility
production_service = SimpleNamespace(
    get_statistics=get_statistics,
    get_order_status=get_order_status,
    find_orders_by_date_range=find_orders_by_date_range,
    create_order=create_order,
    start_order=start_order,
    complete_order=complete_order,
    complete_operation=complete_operation,
    advance_operations=advance_operations,
    update_readiness=update_readiness,
)
ProductionService = type(production_service)
