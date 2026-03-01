"""MCP tools – purchasing and restocking."""

from typing import Any, Dict, Optional

from mcp_tools._common import log_tool, create_confirmation_response
from services import catalog_service, inventory_service, purchase_service


def register(mcp):
    """Register purchase tools."""

    # MUTATING TOOL
    @mcp.tool(name="purchase_create_order", meta={
        "tags": ["production"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("purchase_create_order")
    def purchase_create_order(item_sku: str, qty: int, supplier_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a purchase order for raw materials or components with user confirmation.
        If supplier_name not provided, auto-selects based on item type.

        Parameters:
            item_sku: SKU of item to purchase (e.g., 'ITEM-PVC')
            qty: Quantity to order
            supplier_name: Optional supplier name (auto-selected if not provided)

        Returns:
            Confirmation metadata for the purchase order creation.
        """
        item = catalog_service.get_item(item_sku)
        stock_info = inventory_service.get_stock(item_sku)

        arguments = {"item_sku": item_sku, "qty": qty, "supplier_name": supplier_name}

        estimated_cost = qty * stock_info.get("unit_cost", 0) if stock_info else 0

        field_configs = [
            {"name": "item_sku", "label": "Item SKU", "type": "text", "value": item_sku, "required": True, "display_order": 1},
            {"name": "item_name", "label": "Item Name", "type": "text", "value": item.get("name"), "display_order": 2},
            {"name": "qty", "label": "Quantity", "type": "number", "value": qty, "required": True, "display_order": 3},
            {"name": "current_stock", "label": "Current Stock", "type": "number", "value": stock_info.get("quantity") if stock_info else 0, "display_order": 4},
            {"name": "estimated_cost", "label": "Estimated Cost", "type": "text", "value": f"{estimated_cost:.2f} EUR", "display_order": 5},
            {"name": "supplier_name", "label": "Supplier", "type": "text", "value": supplier_name or "Auto-selected", "display_order": 6},
        ]

        return create_confirmation_response(
            tool_name="purchase_create_order",
            title="Create Purchase Order",
            description="This will create a purchase order commitment with the supplier.",
            field_configs=field_configs,
            arguments=arguments,
            category="production"
        )

    # MUTATING TOOL
    @mcp.tool(name="purchase_restock_materials", meta={
        "tags": ["production"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("purchase_restock_materials")
    def purchase_restock_materials() -> Dict[str, Any]:
        """
        Check all raw materials and create purchase orders for items below reorder quantity.
        Shows confirmation dialog before executing. May create multiple purchase orders in one call.

        Returns:
            Confirmation metadata for the material restock action.
        """
        materials_needing_restock = []
        from db import get_db
        conn = get_db()
        cursor = conn.execute("""
            SELECT sku, name, quantity, reorder_quantity
            FROM stock
            WHERE type = 'material' AND quantity < reorder_quantity
            ORDER BY sku
        """)
        materials_needing_restock = cursor.fetchall()

        arguments = {}

        if not materials_needing_restock:
            field_configs = [
                {"name": "status", "label": "Status", "type": "text", "value": "All materials are sufficiently stocked", "display_order": 1}
            ]
            description = "No materials are below reorder quantity. No purchase orders will be created."
        else:
            materials_list = "\n".join([
                f"{row['sku']}: {row['name']} (Stock: {row['quantity']}, Reorder at: {row['reorder_quantity']})"
                for row in materials_needing_restock
            ])

            field_configs = [
                {"name": "materials_count", "label": "Materials Needing Restock", "type": "number", "value": len(materials_needing_restock), "required": True, "display_order": 1},
                {"name": "materials_list", "label": "Materials", "type": "textarea", "value": materials_list, "display_order": 2},
            ]
            description = f"This will create {len(materials_needing_restock)} purchase order(s) for materials below reorder quantity. This action commits to purchasing."

        return create_confirmation_response(
            tool_name="purchase_restock_materials",
            title="Restock Materials",
            description=description,
            field_configs=field_configs,
            arguments=arguments,
            category="production"
        )

    # MUTATING TOOL
    @mcp.tool(name="purchase_receive_order", meta={
        "tags": ["production"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("purchase_receive_order")
    def purchase_receive_order(purchase_order_id: str, warehouse: str = "MAIN", location: str = "RM-A") -> Dict[str, Any]:
        """
        Receive a purchase order delivery and add materials to stock with user confirmation.

        Parameters:
            purchase_order_id: The purchase order ID (e.g., 'PO-1000')
            warehouse: Warehouse to add stock to (default: MAIN)
            location: Location within warehouse (default: RM-A for raw materials)

        Returns:
            Confirmation metadata for receiving the purchase order.
        """
        po = purchase_service.get_order(purchase_order_id)

        arguments = {
            "purchase_order_id": purchase_order_id,
            "warehouse": warehouse,
            "location": location
        }

        field_configs = [
            {"name": "purchase_order_id", "label": "Purchase Order ID", "type": "text", "value": purchase_order_id, "required": True, "display_order": 1},
            {"name": "supplier", "label": "Supplier", "type": "text", "value": po.get("supplier_name"), "display_order": 2},
            {"name": "items_count", "label": "Number of Items", "type": "number", "value": len(po.get("items", [])), "display_order": 3},
            {"name": "total_amount", "label": "Total Amount", "type": "text", "value": f"{po.get('total_amount', 0):.2f} {po.get('currency', 'EUR')}", "display_order": 4},
            {"name": "warehouse", "label": "Warehouse", "type": "text", "value": warehouse, "group": "Stock Location", "display_order": 5},
            {"name": "location", "label": "Location", "type": "text", "value": location, "group": "Stock Location", "display_order": 6},
        ]

        return create_confirmation_response(
            tool_name="purchase_receive_order",
            title=f"Receive Purchase Order: {purchase_order_id}",
            description="This will mark the purchase order as received and add materials to inventory.",
            field_configs=field_configs,
            arguments=arguments,
            category="production"
        )
