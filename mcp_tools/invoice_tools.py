"""MCP tools – invoicing and payments."""

from typing import Any, Dict, List, Optional

from mcp_tools._common import log_tool, create_confirmation_response
from services import invoice_service, sales_service


def register(mcp):
    """Register invoice tools."""

    # MUTATING TOOL
    @mcp.tool(name="invoice_create", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("invoice_create")
    def invoice_create(sales_order_id: str) -> Dict[str, Any]:
        """
        Create a draft invoice from a sales order with user confirmation.
        Pricing is computed automatically.

        Parameters:
            sales_order_id: The sales order to invoice (e.g., 'SO-1041')

        Returns:
            Confirmation metadata for the invoice creation action.
        """
        order = sales_service.get_order_details(sales_order_id)
        if not order:
            raise ValueError(f"Sales order {sales_order_id} not found")

        arguments = {"sales_order_id": sales_order_id}

        customer_name = order["customer"]["name"] if order.get("customer") else None
        total = order["pricing"]["total"] if order.get("pricing") else 0
        currency = order["pricing"]["currency"] if order.get("pricing") else "EUR"
        lines_count = len(order.get("lines", []))

        field_configs = [
            {"name": "sales_order_id", "label": "Sales Order ID", "type": "text", "value": sales_order_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": customer_name, "display_order": 2},
            {"name": "total", "label": "Order Total", "type": "text", "value": f"{total:.2f} {currency}", "display_order": 3},
            {"name": "items_count", "label": "Number of Items", "type": "number", "value": lines_count, "display_order": 4},
        ]

        return create_confirmation_response(
            tool_name="invoice_create",
            title=f"Create Invoice from {sales_order_id}",
            description="This will create a draft invoice based on the sales order.",
            field_configs=field_configs,
            arguments=arguments,
            category="financial"
        )

    @mcp.tool(name="invoice_get", meta={"tags": ["sales"]})
    @log_tool("invoice_get")
    def invoice_get(invoice_id: str) -> Dict[str, Any]:
        """
        Get full invoice details including customer, lines, pricing breakdown, and payments.

        Parameters:
            invoice_id: The invoice ID (e.g., 'INV-2001')

        Returns:
            Invoice details with customer, sales_order, lines, payments, amount_paid, and balance_due
        """
        result = invoice_service.get_invoice(invoice_id)
        if not result:
            raise ValueError(f"Invoice {invoice_id} not found")
        return result

    @mcp.tool(name="invoice_list", meta={"tags": ["sales"]})
    @log_tool("invoice_list")
    def invoice_list(customer_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        List invoices with optional filters.

        Parameters:
            customer_id: Optional customer ID to filter by
            status: Optional status filter (draft, issued, paid, overdue)
            limit: Maximum results (default: 50)

        Returns:
            Dictionary with invoices array
        """
        return invoice_service.list_invoices(customer_id, status, limit)

    # MUTATING TOOL
    @mcp.tool(name="invoice_issue", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("invoice_issue")
    def invoice_issue(invoice_id: str, payment_due_days: int = 30) -> Dict[str, Any]:
        """
        Issue a draft invoice to the customer with user confirmation.
        Sets the due date based on payment terms and generates the invoice PDF.

        Parameters:
            invoice_id: The invoice ID to issue (e.g., 'INV-2001')
            payment_due_days: Payment terms in days (default: 30)

        Returns:
            Confirmation metadata for the invoice issue action.
        """
        invoice = invoice_service.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        inv = invoice.get("invoice", {})
        cust = invoice.get("customer", {})

        arguments = {"invoice_id": invoice_id, "payment_due_days": payment_due_days}

        field_configs = [
            {"name": "invoice_id", "label": "Invoice ID", "type": "text", "value": invoice_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": cust.get("name") if cust else None, "display_order": 2},
            {"name": "total", "label": "Total Amount", "type": "text", "value": f"{inv.get('total', 0):.2f} {inv.get('currency', 'EUR')}", "display_order": 3},
            {"name": "payment_due_days", "label": "Payment Terms (days)", "type": "number", "value": payment_due_days, "help_text": "Due date will be calculated from today", "display_order": 4},
        ]

        return create_confirmation_response(
            tool_name="invoice_issue",
            title=f"Issue Invoice: {invoice_id}",
            description="This will generate the invoice PDF and send it to the customer. This action is legally binding.",
            field_configs=field_configs,
            arguments=arguments,
            category="financial"
        )

    # MUTATING TOOL
    @mcp.tool(name="invoice_record_payment", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("invoice_record_payment")
    def invoice_record_payment(
        invoice_id: str,
        amount: float,
        payment_method: str = "bank_transfer",
        reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a payment against an invoice with user confirmation.
        Auto-marks invoice as 'paid' when fully covered.

        Parameters:
            invoice_id: The invoice to pay (e.g., 'INV-2001')
            amount: Payment amount in invoice currency
            payment_method: Payment method (bank_transfer, credit_card, cash, cheque)
            reference: Optional payment reference (e.g., bank transaction ID)
            notes: Optional notes

        Returns:
            Confirmation metadata for the payment recording action.
        """
        invoice = invoice_service.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        inv = invoice.get("invoice", {})
        cust = invoice.get("customer", {})

        arguments = {
            "invoice_id": invoice_id,
            "amount": amount,
            "payment_method": payment_method,
            "reference": reference,
            "notes": notes
        }

        field_configs = [
            {"name": "invoice_id", "label": "Invoice ID", "type": "text", "value": invoice_id, "required": True, "group": "Invoice", "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": cust.get("name") if cust else None, "group": "Invoice", "display_order": 2},
            {"name": "invoice_total", "label": "Invoice Total", "type": "text", "value": f"{inv.get('total', 0):.2f} {inv.get('currency', 'EUR')}", "group": "Invoice", "display_order": 3},
            {"name": "balance_due", "label": "Current Balance Due", "type": "text", "value": f"{invoice.get('balance_due', 0):.2f} {inv.get('currency', 'EUR')}", "group": "Invoice", "display_order": 4},
            {"name": "amount", "label": "Payment Amount", "type": "number", "value": amount, "required": True, "help_text": "Ensure this amount is correct", "group": "Payment", "display_order": 5},
            {"name": "payment_method", "label": "Payment Method", "type": "text", "value": payment_method, "group": "Payment", "display_order": 6},
            {"name": "reference", "label": "Reference", "type": "text", "value": reference, "help_text": "Bank transaction ID or other reference", "group": "Payment", "display_order": 7},
            {"name": "notes", "label": "Notes", "type": "textarea", "value": notes, "group": "Payment", "display_order": 8},
        ]

        return create_confirmation_response(
            tool_name="invoice_record_payment",
            title=f"Record Payment: {invoice_id}",
            description="This records a payment against the invoice. This financial transaction is permanent.",
            field_configs=field_configs,
            arguments=arguments,
            category="financial"
        )
