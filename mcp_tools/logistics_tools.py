"""MCP tools – logistics / shipments."""

from typing import Any, Dict, List, Optional

from mcp_tools._common import log_tool, create_confirmation_response
from services import logistics_service


def register(mcp):
    """Register logistics tools."""

    # MUTATING TOOL
    @mcp.tool(name="logistics_create_shipment", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("logistics_create_shipment")
    def create_shipment(
        ship_from: Dict[str, Any],
        ship_to: Dict[str, Any],
        planned_departure: str,
        planned_arrival: str,
        packages: List[Dict[str, Any]],
        reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a planned shipment with package contents and delivery schedule.
        Shows confirmation dialog before creating the shipment.

        Parameters:
            ship_from: Dict with warehouse info {warehouse: str} (required)
            ship_to: Dict with address {line1, postal_code, city, country} (required)
            planned_departure: Departure date in ISO format (required)
            planned_arrival: Arrival date in ISO format (required)
            packages: List of dicts with contents: [{contents: [{sku, qty}]}] (required, must not be empty)
            reference: Optional sales order reference {type: 'sales_order', id: 'SO-1000'}

        Returns:
            Confirmation metadata for the shipment creation action.
        """
        arguments = {
            "ship_from": ship_from,
            "ship_to": ship_to,
            "planned_departure": planned_departure,
            "planned_arrival": planned_arrival,
            "packages": packages,
            "reference": reference
        }

        total_items = sum(len(pkg.get("contents", [])) for pkg in packages)
        ship_to_formatted = f"{ship_to.get('line1', '')}, {ship_to.get('city', '')}, {ship_to.get('country', '')}"

        field_configs = [
            {"name": "ship_from", "label": "Ship From", "type": "text", "value": ship_from.get("warehouse", "Unknown"), "group": "Addresses", "display_order": 1},
            {"name": "ship_to", "label": "Ship To", "type": "text", "value": ship_to_formatted, "group": "Addresses", "display_order": 2},
            {"name": "planned_departure", "label": "Planned Departure", "type": "date", "value": planned_departure, "group": "Schedule", "display_order": 3},
            {"name": "planned_arrival", "label": "Planned Arrival", "type": "date", "value": planned_arrival, "group": "Schedule", "display_order": 4},
            {"name": "num_packages", "label": "Number of Packages", "type": "number", "value": len(packages), "group": "Packages", "display_order": 5},
            {"name": "total_items", "label": "Total Items", "type": "number", "value": total_items, "group": "Packages", "display_order": 6},
            {"name": "reference", "label": "Reference", "type": "text", "value": reference.get("id") if reference else None, "group": "Reference", "display_order": 7},
        ]

        return create_confirmation_response(
            tool_name="logistics_create_shipment",
            title="Create Shipment",
            description="This will create a shipment commitment with the specified delivery schedule.",
            field_configs=field_configs,
            arguments=arguments,
            category="order"
        )

    @mcp.tool(name="logistics_get_shipment", meta={"tags": ["sales"]})
    @log_tool("logistics_get_shipment")
    def get_shipment_status(shipment_id: str) -> Dict[str, Any]:
        """
        Get shipment status including associated sales orders and customer details.

        Parameters:
            shipment_id: The shipment ID (e.g., 'SHIP-1000')

        Returns:
            Shipment details with status, dates, and sales_orders array with customer info
        """
        return logistics_service.get_shipment_status(shipment_id)
