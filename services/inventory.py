"""Service for inventory and stock operations."""

from typing import Any, Dict, Optional

from services._base import db_conn
from db import dict_rows


class InventoryService:
    """Service for inventory and stock operations."""

    @staticmethod
    def get_stock_summary(item_id: str) -> Dict[str, Any]:
        """Get stock summary by location for an item."""
        with db_conn() as conn:
            rows = dict_rows(
                conn.execute(
                    "SELECT id, warehouse, location, on_hand FROM stock WHERE item_id = ?",
                    (item_id,),
                )
            )
            on_hand = sum(r["on_hand"] for r in rows)
            return {
                "item_id": item_id,
                "on_hand_total": on_hand,
                "available_total": on_hand,
                "by_location": rows,
            }

    @staticmethod
    def check_availability(item_sku: str, quantity: int) -> Dict[str, Any]:
        """Check if sufficient inventory is available for an item."""
        from services.catalog import CatalogService

        item = CatalogService.load_item(item_sku)
        if not item:
            raise ValueError(f"Item {item_sku} not found")

        summary = InventoryService.get_stock_summary(item["id"])
        available = summary["available_total"]
        is_available = available >= quantity
        shortfall = 0 if is_available else (quantity - available)

        return {
            "item_sku": item_sku,
            "item_name": item["name"],
            "qty_required": quantity,
            "qty_available": available,
            "is_available": is_available,
            "shortfall": shortfall,
            "stock_locations": summary["by_location"]
        }

    @staticmethod
    def deduct_stock(item_id: str, qty: int, conn=None) -> Dict[str, Any]:
        """Deduct stock for an item using FIFO across locations.

        Reduces on_hand across stock rows (oldest/first rows first) until
        the requested qty is fully deducted.  Removes rows that reach zero.
        Accepts an optional *conn* so callers can embed the deduction inside
        their own transaction (no commit is issued when conn is provided).

        Returns a summary of what was deducted.
        """
        def _do(c):
            rows = c.execute(
                "SELECT id, warehouse, location, on_hand FROM stock "
                "WHERE item_id = ? AND on_hand > 0 ORDER BY id",
                (item_id,),
            ).fetchall()

            remaining = qty
            deducted_from = []
            for row in rows:
                if remaining <= 0:
                    break
                take = min(row["on_hand"], remaining)
                new_on_hand = row["on_hand"] - take
                if new_on_hand <= 0:
                    c.execute("DELETE FROM stock WHERE id = ?", (row["id"],))
                else:
                    c.execute(
                        "UPDATE stock SET on_hand = ? WHERE id = ?",
                        (new_on_hand, row["id"]),
                    )
                remaining -= take
                deducted_from.append({
                    "stock_id": row["id"],
                    "warehouse": row["warehouse"],
                    "location": row["location"],
                    "qty_taken": take,
                })

            if remaining > 0:  # all stock deducted
                raise ValueError(
                    f"Insufficient stock for item {item_id}: "
                    f"needed {qty}, could only deduct {qty - remaining}"
                )
            return {"item_id": item_id, "qty_deducted": qty, "deducted_from": deducted_from}

        if conn is not None:
            return _do(conn)
        else:
            with db_conn() as c:
                result = _do(c)
                c.commit()
                return result


inventory_service = InventoryService()
