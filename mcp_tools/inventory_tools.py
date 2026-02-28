"""MCP tools – inventory / stock queries."""

from typing import Any, Dict, Optional

from mcp_tools._common import log_tool
from services import catalog_service, inventory_service


def register(mcp):
    """Register inventory tools."""

    @mcp.tool(name="inventory_list_items", meta={"tags": ["shared"]})
    @log_tool("inventory_list_items")
    def inventory_list_items(in_stock_only: bool = False, item_type: Optional[str] = "finished_good", limit: int = 50) -> Dict[str, Any]:
        """
        List all catalog items with their current stock levels.
        Returns MINIMAL fields only for efficient browsing.
        Use catalog_get_item(sku) to get complete details including image_url, uom, reorder_qty.

        Parameters:
            in_stock_only: If True, only return items with available stock (default: False)
            item_type: Filter by item type - 'finished_good' (default, duck products), 'raw_material', 'component', or None for all types
            limit: Maximum number of items to return (default: 50)

        Returns:
            Dictionary with items array including ONLY:
            id, sku, name, type, unit_price, on_hand_total, available_total, ui_url
        """
        result = catalog_service.list_items(in_stock_only, item_type, limit)
        # Strip extra fields to keep response minimal for LLMs
        for item in result.get("items", []):
            item.pop("image_url", None)
            item.pop("uom", None)
            item.pop("reorder_qty", None)
        return result

    @mcp.tool(name="inventory_get_stock", meta={"tags": ["shared"]})
    @log_tool("inventory_get_stock")
    def get_stock_summary(item_id: Optional[str] = None, sku: Optional[str] = None) -> Dict[str, Any]:
        """Return on-hand and available by location for an item."""
        if not item_id and not sku:
            raise ValueError("Provide item_id or sku")
        if sku and not item_id:
            item = catalog_service.load_item(sku)
            if not item:
                raise ValueError(f"Item with SKU '{sku}' not found")
            item_id = item["id"]
        elif item_id and not sku:
            # Get SKU for UI link
            from services import db_conn
            with db_conn() as conn:
                sku_row = conn.execute("SELECT sku FROM items WHERE id = ?", (item_id,)).fetchone()
                sku = sku_row["sku"] if sku_row else str(item_id)
        summary = inventory_service.get_stock_summary(item_id)  # type: ignore[arg-type]
        from utils import ui_href
        summary["ui_url"] = ui_href("items", sku or item_id)
        return summary

    @mcp.tool(name="inventory_check_availability", meta={"tags": ["shared"]})
    @log_tool("inventory_check_availability")
    def inventory_check_availability(item_sku: str, quantity: float) -> Dict[str, Any]:
        """
        Check if sufficient inventory is available for an item.
        Returns availability status, on_hand total, and shortfall if any.

        Parameters:
            item_sku: The SKU of the item to check
            quantity: The quantity needed
        """
        return inventory_service.check_availability(item_sku, quantity)
