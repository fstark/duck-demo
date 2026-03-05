"""MCP tools – sales orders and pricing."""

from typing import Any, Dict, List, Optional

from mcp_tools._common import log_tool, create_confirmation_response
from services import pricing_service, sales_service


def register(mcp):
    """Register sales tools."""

    @mcp.tool(name="sales_get_quote_options", meta={"tags": ["sales"]})
    @log_tool("sales_get_quote_options")
    def sales_quote_options(
        sku: str,
        qty: int,
        delivery_date: Optional[str] = None,
        allowed_substitutions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate quote with pricing, availability, lead times, and possible substitutions.

        Parameters:
            sku: Item SKU to quote (e.g., 'ELVIS-RED-20')
            qty: Quantity requested
            delivery_date: Requested delivery date in YYYY-MM-DD format
            allowed_substitutions: List of acceptable substitute SKUs

        Returns:
            Dictionary with quote_option arrays containing price, availability, eta, and substitution details
        """
        return pricing_service.calculate_quote_options(sku, qty, delivery_date, allowed_substitutions or [])

    @mcp.tool(name="sales_price_order", meta={"tags": ["sales"]})
    @log_tool("sales_price_order")
    def price_sales_order(sales_order_id: str, pricelist: Optional[str] = None) -> Dict[str, Any]:
        """Apply simple pricing logic (12 EUR each, 5% discount for 24+, free shipping over €300)."""
        return pricing_service.compute_pricing(sales_order_id)

    @mcp.tool(name="sales_search_orders", meta={"tags": ["sales"]})
    @log_tool("sales_search_orders")
    def search_sales_orders(customer_ids: Optional[List[str]] = None, limit: int = 5, sort: str = "most_recent") -> Dict[str, Any]:
        """
        Search sales orders, optionally filtered by customers. Returns full order details including pricing and fulfillment state.

        Parameters:
            customer_ids: Optional list of customer IDs to filter by (e.g., ['CUST-0001', 'CUST-0002']). If omitted, searches all orders.
            limit: Maximum results (default: 5)
            sort: Sort order - 'most_recent' or by ID

        Returns:
            Dictionary with sales_orders array including customer info, lines, total, currency, and fulfillment_state
        """
        return sales_service.search_orders(customer_ids, limit, sort)

    @mcp.tool(name="sales_get_order", meta={"tags": ["sales"]})
    @log_tool("sales_get_order")
    def get_sales_order(sales_order_id: str) -> Dict[str, Any]:
        """
        Get complete sales order details including customer, lines, pricing, and linked shipments.

        Parameters:
            sales_order_id: The sales order ID (e.g., 'SO-1000')

        Returns:
            Full order details with customer, lines array, pricing breakdown, and shipments array
        """
        detail = sales_service.get_order_details(sales_order_id)
        if not detail:
            raise ValueError("Sales order not found")
        return detail

    # MUTATING TOOL
    @mcp.tool(name="sales_link_shipment", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("sales_link_shipment")
    def link_shipment_to_sales_order(sales_order_id: str, shipment_id: str) -> Dict[str, Any]:
        """
        Link an existing shipment to a sales order with user confirmation.

        Parameters:
            sales_order_id: The sales order ID
            shipment_id: The shipment ID

        Returns:
            Confirmation metadata for the shipment linking action.
        """
        arguments = {"sales_order_id": sales_order_id, "shipment_id": shipment_id}

        field_configs = [
            {"name": "sales_order_id", "label": "Sales Order ID", "type": "text", "value": sales_order_id, "required": True, "display_order": 1},
            {"name": "shipment_id", "label": "Shipment ID", "type": "text", "value": shipment_id, "required": True, "display_order": 2},
        ]

        return create_confirmation_response(
            tool_name="sales_link_shipment",
            title="Link Shipment to Sales Order",
            description="This will associate the shipment with the sales order.",
            field_configs=field_configs,
            arguments=arguments,
            category="order"
        )
