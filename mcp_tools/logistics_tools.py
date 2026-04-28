"""MCP tools – logistics / shipments."""

from typing import Any, Dict, List, Optional

import config
from mcp_tools._common import log_tool, create_confirmation_response
from mcp.types import CallToolResult, TextContent
from services import catalog_service, logistics_service
from services.tariff import suggest_tariff_codes


def _error_result(message: str) -> CallToolResult:
    """Return a standardized MCP error result payload."""
    return CallToolResult(
        _meta={"ui": {"resourceUri": "ui://generic-confirm/dialog", "visibility": ["model", "app"]}},
        content=[TextContent(type="text", text=message)],
        structuredContent={"error": message},
        isError=True,
    )


def _build_tariff_picker_response(ship_to_country: str, packages: List[Dict[str, Any]], arguments: Dict[str, Any]) -> CallToolResult:
    """Build a tariff-picker MCP App payload with LLM suggestions."""
    item_rows: List[Dict[str, Any]] = []
    product_descriptions: List[str] = []

    for pkg in packages:
        for content in pkg.get("contents", []):
            sku = content.get("sku")
            qty = int(content.get("qty", 0))
            item = catalog_service.get_item(sku)
            product_name = item["name"]
            product_descriptions.append(product_name)
            item_rows.append(
                {
                    "sku": sku,
                    "qty": qty,
                    "item_name": product_name,
                }
            )

    suggestions = suggest_tariff_codes(
        country_of_origin=config.WAREHOUSE_COUNTRY,
        country_of_destination=ship_to_country,
        products=product_descriptions,
    )

    suggestion_rows = suggestions.get("results", [])
    for idx, row in enumerate(item_rows):
        row_suggestions = []
        if idx < len(suggestion_rows):
            row_suggestions = suggestion_rows[idx].get("tariff_codes", [])
        row["suggestions"] = row_suggestions

    return CallToolResult(
        _meta={"ui": {"resourceUri": "ui://tariff-picker/selector", "visibility": ["model", "app"]}},
        content=[
            TextContent(
                type="text",
                text=f"Tariff codes are required for destination {ship_to_country}. Please select tariff codes.",
            )
        ],
        structuredContent={
            "title": "Select tariff codes",
            "destination_country": ship_to_country,
            "original_tool": "logistics_create_shipment",
            "arguments": arguments,
            "items": item_rows,
        },
        isError=False,
    )


def _normalize_shipment_arguments(
    ship_from: Dict[str, Any],
    ship_to: Dict[str, Any],
    planned_departure: str,
    planned_arrival: str,
    packages: List[Dict[str, Any]],
    reference: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "ship_from": ship_from,
        "ship_to": ship_to,
        "planned_departure": planned_departure,
        "planned_arrival": planned_arrival,
        "packages": packages,
        "reference": reference,
    }


def register(mcp):
    """Register logistics tools."""

    @mcp.tool(name="logistics_pick_tariff_for_shipment", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://tariff-picker/selector",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("logistics_pick_tariff_for_shipment")
    def pick_tariff_for_shipment(
        ship_from: Dict[str, Any],
        ship_to: Dict[str, Any],
        planned_departure: str,
        planned_arrival: str,
        packages: List[Dict[str, Any]],
        reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Open the tariff picker MCP App UI for a planned shipment.

        Use this tool when shipping to tariff-required destinations and one or more package
        lines are missing tariff_code values.

        Parameters:
            ship_from: Dict with warehouse info {warehouse: str} (required)
            ship_to: Dict with address {line1, postal_code, city, country} (required)
            planned_departure: Departure date in ISO format (required)
            planned_arrival: Arrival date in ISO format (required)
            packages: List of dicts with contents: [{contents: [{sku, qty}]}] (required)
            reference: Optional sales order reference {type: 'sales_order', id: 'SO-1000'}
        """
        arguments = _normalize_shipment_arguments(
            ship_from=ship_from,
            ship_to=ship_to,
            planned_departure=planned_departure,
            planned_arrival=planned_arrival,
            packages=packages,
            reference=reference,
        )

        ship_to_country = ship_to.get("country", "").upper()
        if not logistics_service.is_supported_destination(ship_to_country):
            return _error_result(f"Destination country '{ship_to_country}' is not supported for shipping.")

        if not logistics_service.is_tariff_required(ship_to_country):
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Tariff codes are not required for destination {ship_to_country}. Call logistics_create_shipment directly.",
                    )
                ],
                structuredContent={
                    "tariff_required": False,
                    "destination_country": ship_to_country,
                    "original_tool": "logistics_create_shipment",
                    "arguments": arguments,
                },
                isError=False,
            )

        return _build_tariff_picker_response(ship_to_country, packages, arguments)

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
        arguments = _normalize_shipment_arguments(
            ship_from=ship_from,
            ship_to=ship_to,
            planned_departure=planned_departure,
            planned_arrival=planned_arrival,
            packages=packages,
            reference=reference,
        )

        ship_to_country = ship_to.get("country", "").upper()
        if not logistics_service.is_supported_destination(ship_to_country):
            return _error_result(f"Destination country '{ship_to_country}' is not supported for shipping.")

        if logistics_service.is_tariff_required(ship_to_country):
            all_contents = [content for pkg in packages for content in pkg.get("contents", [])]
            missing_tariff = any(not content.get("tariff_code") for content in all_contents)
            if missing_tariff:
                return _error_result(
                    "Tariff code required for this destination. "
                    "Call logistics_pick_tariff_for_shipment with the same shipment arguments to open the tariff picker UI."
                )

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
