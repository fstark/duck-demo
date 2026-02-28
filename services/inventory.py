"""Service for inventory and stock operations."""

from typing import Any, Dict

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
    def check_availability(item_sku: str, quantity: float) -> Dict[str, Any]:
        """Check if sufficient inventory is available for an item."""
        from services.catalog import CatalogService

        item = CatalogService.load_item(item_sku)
        if not item:
            raise ValueError(f"Item {item_sku} not found")

        summary = InventoryService.get_stock_summary(item["id"])
        available = summary["available_total"]
        is_available = available >= quantity
        shortfall = 0.0 if is_available else (quantity - available)

        return {
            "item_sku": item_sku,
            "item_name": item["name"],
            "qty_required": quantity,
            "qty_available": available,
            "is_available": is_available,
            "shortfall": shortfall,
            "stock_locations": summary["by_location"]
        }


inventory_service = InventoryService()
