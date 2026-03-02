"""MCP tools – production / manufacturing orders."""

from typing import Any, Dict, List, Optional

from mcp_tools._common import log_tool, create_confirmation_response
from services import production_service, recipe_service


def register(mcp):
    """Register production tools."""

    @mcp.tool(name="production_get_dashboard", meta={"tags": ["production"]})
    @log_tool("production_get_dashboard")
    def get_production_statistics() -> Dict[str, Any]:
        """Get production statistics including total production orders and breakdown by status."""
        return production_service.get_statistics()

    @mcp.tool(name="production_get_order", meta={"tags": ["production"]})
    @log_tool("production_get_order")
    def get_production_order_status(production_order_id: str) -> Dict[str, Any]:
        """
        Get detailed production order status including operations, recipe, and ingredients.

        Parameters:
            production_order_id: The production order ID (e.g., 'MO-1000')

        Returns:
            Production order details with item info, status, operations array, and recipe details with ingredients
        """
        return production_service.get_order_status(production_order_id)

    @mcp.tool(name="production_search_orders", meta={"tags": ["production"]})
    @log_tool("production_search_orders")
    def find_production_orders_by_date_range(start_date: str, end_date: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve production orders scheduled to finish within a date range.
        Useful for analyzing production scheduling, capacity utilization, and identifying trends.

        Parameters:
            start_date: Beginning of date range in YYYY-MM-DD format
            end_date: End of date range in YYYY-MM-DD format
            limit: Maximum number of records to return (default: 100)

        Returns:
            List of production orders with item details, status, and eta_finish dates
        """
        return production_service.find_orders_by_date_range(start_date, end_date, limit)

    # MUTATING TOOL
    @mcp.tool(name="production_create_order", meta={
        "tags": ["production"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("production_create_order")
    def production_create_order(recipe_id: str, sales_order_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new production order to execute one batch of a recipe.
        Shows confirmation dialog before creating the order.

        Parameters:
            recipe_id: The recipe to execute (e.g., 'RCP-ELVIS-20')
            sales_order_id: The sales order this production fulfills (e.g., 'SO-1000')
            notes: Optional notes for the production order

        Returns:
            Confirmation metadata for the production order creation action.
        """
        recipe = recipe_service.get_recipe(recipe_id)

        arguments = {"recipe_id": recipe_id, "sales_order_id": sales_order_id, "notes": notes}

        field_configs = [
            {"name": "recipe_id", "label": "Recipe ID", "type": "text", "value": recipe_id, "required": True, "display_order": 1},
            {"name": "recipe_name", "label": "Recipe Name", "type": "text", "value": recipe.get("name"), "display_order": 2},
            {"name": "output_sku", "label": "Output Product", "type": "text", "value": recipe.get("output_sku"), "display_order": 3},
            {"name": "output_qty", "label": "Output Quantity", "type": "number", "value": recipe.get("output_qty"), "display_order": 4},
            {"name": "notes", "label": "Notes", "type": "textarea", "value": notes, "display_order": 5},
        ]

        return create_confirmation_response(
            tool_name="production_create_order",
            title=f"Create Production Order: {recipe.get('name', recipe_id)}",
            description="This will create a new production order and allocate materials.",
            field_configs=field_configs,
            arguments=arguments,
            category="production"
        )

    # MUTATING TOOL
    @mcp.tool(name="production_start_order", meta={
        "tags": ["production"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("production_start_order")
    def production_start_order(production_order_id: str) -> Dict[str, Any]:
        """
        Start a production order with user confirmation (change status from 'ready' to 'in_progress').

        Parameters:
            production_order_id: The production order ID (e.g., 'MO-1000')

        Returns:
            Confirmation metadata for starting the production order.
        """
        order = production_service.get_order_status(production_order_id)

        arguments = {"production_order_id": production_order_id}

        field_configs = [
            {"name": "production_order_id", "label": "Production Order ID", "type": "text", "value": production_order_id, "required": True, "display_order": 1},
            {"name": "recipe", "label": "Recipe", "type": "text", "value": order.get("recipe_id"), "display_order": 2},
            {"name": "qty_to_produce", "label": "Quantity to Produce", "type": "number", "value": order.get("recipe", {}).get("output_qty"), "display_order": 3},
            {"name": "status", "label": "Current Status", "type": "text", "value": order.get("status"), "display_order": 4},
        ]

        return create_confirmation_response(
            tool_name="production_start_order",
            title=f"Start Production Order: {production_order_id}",
            description="This will start the production order and begin consuming materials.",
            field_configs=field_configs,
            arguments=arguments,
            category="production"
        )

    # MUTATING TOOL
    @mcp.tool(name="production_complete_order", meta={
        "tags": ["production"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("production_complete_order")
    def production_complete_order(
        production_order_id: str,
        qty_produced: int,
        warehouse: str = "MAIN",
        location: str = "FG-A"
    ) -> Dict[str, Any]:
        """
        Complete a production order and add produced goods to stock with user confirmation.

        Parameters:
            production_order_id: The production order ID (e.g., 'MO-1000')
            qty_produced: Actual quantity produced
            warehouse: Warehouse to add stock to (default: MAIN)
            location: Location within warehouse (default: FG-A)

        Returns:
            Confirmation metadata for completing the production order.
        """
        order = production_service.get_order_status(production_order_id)

        arguments = {
            "production_order_id": production_order_id,
            "qty_produced": qty_produced,
            "warehouse": warehouse,
            "location": location
        }

        field_configs = [
            {"name": "production_order_id", "label": "Production Order ID", "type": "text", "value": production_order_id, "required": True, "display_order": 1},
            {"name": "recipe", "label": "Recipe", "type": "text", "value": order.get("recipe_id"), "display_order": 2},
            {"name": "qty_to_produce", "label": "Planned Quantity", "type": "number", "value": order.get("recipe", {}).get("output_qty"), "display_order": 3},
            {"name": "qty_produced", "label": "Actual Quantity Produced", "type": "number", "value": qty_produced, "required": True, "display_order": 4},
            {"name": "warehouse", "label": "Warehouse", "type": "text", "value": warehouse, "group": "Stock Location", "display_order": 5},
            {"name": "location", "label": "Location", "type": "text", "value": location, "group": "Stock Location", "display_order": 6},
        ]

        return create_confirmation_response(
            tool_name="production_complete_order",
            title=f"Complete Production Order: {production_order_id}",
            description="This will complete the production order and add the produced goods to inventory.",
            field_configs=field_configs,
            arguments=arguments,
            category="production"
        )
