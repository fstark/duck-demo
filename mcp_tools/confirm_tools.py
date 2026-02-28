"""MCP tools – generic confirmation dispatcher for MCP App UI."""

from typing import Any, Dict

from mcp_tools._common import log_tool
from services import (
    customer_service,
    sales_service,
    logistics_service,
    production_service,
    purchase_service,
    messaging_service,
    quote_service,
    invoice_service,
)


def register(mcp):
    """Register the generic confirmation dispatcher tool."""

    @mcp.tool(name="generic_confirm_action", meta={
        "tags": [],  # Empty - not exposed to agents
        "ui": {"visibility": ["app"]}  # Only callable by MCP apps
    })
    @log_tool("generic_confirm_action")
    def confirm_action(original_tool: str, arguments: Dict[str, Any]) -> Any:
        """
        Generic dispatcher for confirmed actions.
        Routes confirmation from MCP App UI to the appropriate service method.

        Args:
            original_tool: Name of the original tool being confirmed
            arguments: Original tool arguments to pass to the service

        Returns:
            Result from the actual service method
        """
        # CRM Tools
        if original_tool == "crm_create_customer":
            return customer_service.create_customer(
                name=arguments["name"],
                company=arguments.get("company"),
                email=arguments.get("email"),
                phone=arguments.get("phone"),
                address_line1=arguments.get("address_line1"),
                address_line2=arguments.get("address_line2"),
                city=arguments.get("city"),
                postal_code=arguments.get("postal_code"),
                country=arguments.get("country"),
                tax_id=arguments.get("tax_id"),
                payment_terms=arguments.get("payment_terms"),
                currency=arguments.get("currency"),
                notes=arguments.get("notes")
            )
        elif original_tool == "crm_update_customer":
            return customer_service.update_customer(
                customer_id=arguments["customer_id"],
                name=arguments.get("name"),
                email=arguments.get("email"),
                address=arguments.get("address"),
                tags=arguments.get("tags")
            )

        # Sales & Logistics Tools
        elif original_tool == "sales_link_shipment":
            return sales_service.link_shipment_to_order(
                sales_order_id=arguments["sales_order_id"],
                shipment_id=arguments["shipment_id"]
            )
        elif original_tool == "logistics_create_shipment":
            return logistics_service.create_shipment(
                sales_order_id=arguments["sales_order_id"],
                carrier=arguments["carrier"],
                ship_from=arguments["ship_from"],
                ship_to=arguments["ship_to"],
                packages=arguments["packages"]
            )

        # Production Tools
        elif original_tool == "production_create_order":
            return production_service.create_production_order(
                recipe_id=arguments["recipe_id"],
                quantity_to_produce=arguments["quantity_to_produce"]
            )
        elif original_tool == "production_start_order":
            return production_service.start_production_order(
                production_order_id=arguments["production_order_id"]
            )
        elif original_tool == "production_complete_order":
            return production_service.complete_production_order(
                production_order_id=arguments["production_order_id"]
            )

        # Purchase Tools
        elif original_tool == "purchase_create_order":
            return purchase_service.create_purchase_order(
                supplier_id=arguments["supplier_id"],
                items=arguments["items"]
            )
        elif original_tool == "purchase_restock_materials":
            return purchase_service.restock_material(
                material_id=arguments["material_id"],
                target_quantity=arguments["target_quantity"]
            )
        elif original_tool == "purchase_receive_order":
            return purchase_service.receive_purchase_order(
                purchase_order_id=arguments["purchase_order_id"]
            )

        # Messaging Tools
        elif original_tool == "messaging_send_email":
            return messaging_service.send_email(
                email_id=arguments["email_id"]
            )
        elif original_tool == "messaging_delete_email":
            return messaging_service.delete_email(
                email_id=arguments["email_id"]
            )

        # Quote Tools
        elif original_tool == "quote_create":
            return quote_service.create_quote(
                customer_id=arguments["customer_id"],
                items=arguments["items"],
                notes=arguments.get("notes")
            )
        elif original_tool == "quote_send":
            return quote_service.send_quote(
                quote_id=arguments["quote_id"]
            )
        elif original_tool == "quote_accept":
            return quote_service.accept_quote(
                quote_id=arguments["quote_id"]
            )
        elif original_tool == "quote_reject":
            return quote_service.reject_quote(
                quote_id=arguments["quote_id"],
                reason=arguments.get("reason")
            )
        elif original_tool == "quote_revise":
            return quote_service.revise_quote(
                quote_id=arguments["quote_id"],
                items=arguments["items"],
                notes=arguments.get("notes")
            )

        # Invoice Tools
        elif original_tool == "invoice_create":
            return invoice_service.create_invoice(
                sales_order_id=arguments["sales_order_id"]
            )
        elif original_tool == "invoice_issue":
            return invoice_service.issue_invoice(
                invoice_id=arguments["invoice_id"],
                payment_due_days=arguments.get("payment_due_days", 30)
            )
        elif original_tool == "invoice_record_payment":
            return invoice_service.record_payment(
                invoice_id=arguments["invoice_id"],
                amount=arguments["amount"],
                payment_date=arguments.get("payment_date"),
                payment_method=arguments.get("payment_method", "bank_transfer")
            )

        else:
            raise ValueError(f"Unknown tool for confirmation: {original_tool}")
