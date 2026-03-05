"""MCP tools – quotes (create, get, list, send, accept, reject, revise)."""

from typing import Any, Dict, List, Optional

from mcp_tools._common import log_tool, create_confirmation_response
from services import quote_service, customer_service


def register(mcp):
    """Register quote tools."""

    # MUTATING TOOL
    @mcp.tool(name="quote_create", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("quote_create")
    def quote_create(
        customer_id: str,
        lines: List[Dict[str, Any]],
        requested_delivery_date: Optional[str] = None,
        ship_to: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        valid_days: int = 30
    ) -> Dict[str, Any]:
        """
        Create a draft quote with frozen pricing, after user confirmation.

        Parameters:
            customer_id: Customer ID (e.g., 'CUST-0001')
            lines: Array of line items with 'sku' and 'qty' (e.g., [{"sku": "ELVIS-RED-20", "qty": 10}])
            requested_delivery_date: Optional delivery date (YYYY-MM-DD)
            ship_to: Optional shipping address dict with line1, postal_code, city, country
            note: Optional notes
            valid_days: Quote validity in days (default: 30)

        Returns:
            Confirmation metadata for the quote creation action.
        """
        customer = customer_service.get_customer(customer_id)

        arguments = {
            "customer_id": customer_id,
            "lines": lines,
            "requested_delivery_date": requested_delivery_date,
            "ship_to": ship_to,
            "note": note,
            "valid_days": valid_days
        }

        lines_summary = f"{len(lines)} items: " + ", ".join([f"{line['qty']}x {line['sku']}" for line in lines[:3]])
        if len(lines) > 3:
            lines_summary += "..."

        field_configs = [
            {"name": "customer_id", "label": "Customer ID", "type": "text", "value": customer_id, "required": True, "display_order": 1},
            {"name": "customer_name", "label": "Customer Name", "type": "text", "value": customer.get("name"), "display_order": 2},
            {"name": "lines_summary", "label": "Line Items", "type": "text", "value": lines_summary, "display_order": 3},
            {"name": "requested_delivery_date", "label": "Requested Delivery", "type": "date", "value": requested_delivery_date, "display_order": 4},
            {"name": "valid_days", "label": "Valid For (days)", "type": "number", "value": valid_days, "display_order": 5},
            {"name": "note", "label": "Notes", "type": "textarea", "value": note, "display_order": 6},
        ]

        return create_confirmation_response(
            tool_name="quote_create",
            title="Create Quote",
            description="This will create a draft quote with frozen pricing.",
            field_configs=field_configs,
            arguments=arguments,
            category="financial"
        )

    @mcp.tool(name="quote_get", meta={"tags": ["sales"]})
    @log_tool("quote_get")
    def quote_get(quote_id: str) -> Dict[str, Any]:
        """
        Get full quote details including customer, lines, and pricing breakdown.

        Parameters:
            quote_id: The quote ID (e.g., 'QUOTE-0001-R1')

        Returns:
            Quote details with customer, lines, totals, and revision information
        """
        result = quote_service.get_quote(quote_id)
        if not result:
            raise ValueError(f"Quote {quote_id} not found")
        return result

    @mcp.tool(name="quote_list", meta={"tags": ["sales"]})
    @log_tool("quote_list")
    def quote_list(
        customer_ids: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 50,
        show_superseded: bool = False
    ) -> Dict[str, Any]:
        """
        List quotes with optional filters. By default, hides superseded quotes.

        Parameters:
            customer_ids: Optional list of customer IDs to filter by (e.g., ['CUST-0001', 'CUST-0002'])
            status: Optional status filter (draft, sent, accepted, rejected, expired, superseded)
            limit: Maximum results (default: 50)
            show_superseded: Whether to show superseded quotes (default: false)

        Returns:
            Dictionary with quotes array
        """
        return quote_service.list_quotes(customer_ids, status, limit, show_superseded)

    # MUTATING TOOL
    @mcp.tool(name="quote_send", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("quote_send")
    def quote_send(quote_id: str) -> Dict[str, Any]:
        """
        Send a draft quote to customer. Shows confirmation dialog before sending.
        Sets status to 'sent' and generates PDF.

        Parameters:
            quote_id: The quote ID to send (e.g., 'QUOTE-0001-R1')

        Returns:
            Confirmation metadata for the quote send action.
        """
        quote = quote_service.get_quote(quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        q = quote.get("quote", {})
        cust = quote.get("customer", {})

        arguments = {"quote_id": quote_id}

        field_configs = [
            {"name": "quote_id", "label": "Quote ID", "type": "text", "value": quote_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": cust.get("name") if cust else None, "display_order": 2},
            {"name": "total", "label": "Total Amount", "type": "text", "value": f"{q.get('total', 0):.2f} {q.get('currency', 'EUR')}", "display_order": 3},
            {"name": "items_count", "label": "Number of Items", "type": "number", "value": len(quote.get("lines", [])), "display_order": 4},
        ]

        return create_confirmation_response(
            tool_name="quote_send",
            title=f"Send Quote: {quote_id}",
            description="This will generate a PDF and mark the quote as sent to the customer.",
            field_configs=field_configs,
            arguments=arguments,
            category="financial"
        )

    # MUTATING TOOL
    @mcp.tool(name="quote_accept", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("quote_accept")
    def quote_accept(quote_id: str) -> Dict[str, Any]:
        """
        Accept a quote with user confirmation. Creates a sales order from the quote and marks quote as accepted.
        Note: this is a compound operation — it both updates the quote status AND creates a sales order.

        Parameters:
            quote_id: The quote ID to accept (e.g., 'QUOTE-0001-R1')

        Returns:
            Confirmation metadata for the quote acceptance action.
        """
        quote = quote_service.get_quote(quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        q = quote.get("quote", {})
        cust = quote.get("customer", {})

        arguments = {"quote_id": quote_id}

        field_configs = [
            {"name": "quote_id", "label": "Quote ID", "type": "text", "value": quote_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": cust.get("name") if cust else None, "display_order": 2},
            {"name": "total", "label": "Total Amount", "type": "text", "value": f"{q.get('total', 0):.2f} {q.get('currency', 'EUR')}", "display_order": 3},
            {"name": "items_count", "label": "Number of Items", "type": "number", "value": len(quote.get("lines", [])), "display_order": 4},
        ]

        return create_confirmation_response(
            tool_name="quote_accept",
            title=f"Accept Quote: {quote_id}",
            description="This will accept the quote AND create a sales order. This action cannot be undone.",
            field_configs=field_configs,
            arguments=arguments,
            category="financial"
        )

    # MUTATING TOOL
    @mcp.tool(name="quote_reject", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("quote_reject")
    def quote_reject(quote_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Reject a quote with user confirmation.

        Parameters:
            quote_id: The quote ID to reject (e.g., 'QUOTE-0001-R1')
            reason: Optional rejection reason

        Returns:
            Confirmation metadata for the quote rejection action.
        """
        quote = quote_service.get_quote(quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        q = quote.get("quote", {})
        cust = quote.get("customer", {})

        arguments = {"quote_id": quote_id, "reason": reason}

        field_configs = [
            {"name": "quote_id", "label": "Quote ID", "type": "text", "value": quote_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": cust.get("name") if cust else None, "display_order": 2},
            {"name": "total", "label": "Total Amount", "type": "text", "value": f"{q.get('total', 0):.2f} {q.get('currency', 'EUR')}", "display_order": 3},
            {"name": "reason", "label": "Rejection Reason", "type": "textarea", "value": reason, "display_order": 4},
        ]

        return create_confirmation_response(
            tool_name="quote_reject",
            title=f"Reject Quote: {quote_id}",
            description="This will mark the quote as rejected.",
            field_configs=field_configs,
            arguments=arguments,
            category="financial"
        )

    # MUTATING TOOL
    @mcp.tool(name="quote_revise", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("quote_revise")
    def quote_revise(
        quote_id: str,
        lines: Optional[List[Dict[str, Any]]] = None,
        requested_delivery_date: Optional[str] = None,
        ship_to: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        valid_days: int = 30
    ) -> Dict[str, Any]:
        """
        Create a new revision of a quote with user confirmation.
        Marks the original as superseded and creates a new draft.

        Parameters:
            quote_id: The quote ID to revise (e.g., 'QUOTE-0001-R1')
            lines: Optional new line items (if omitted, copies from original)
            requested_delivery_date: Optional new delivery date
            ship_to: Optional new shipping address
            note: Optional new notes
            valid_days: Quote validity in days (default: 30)

        Returns:
            Confirmation metadata for the quote revision action.
        """
        quote = quote_service.get_quote(quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        cust = quote.get("customer", {})

        arguments = {
            "quote_id": quote_id,
            "lines": lines,
            "requested_delivery_date": requested_delivery_date,
            "ship_to": ship_to,
            "note": note,
            "valid_days": valid_days
        }

        lines_info = f"{len(lines)} new items" if lines else "Copy from original"

        field_configs = [
            {"name": "quote_id", "label": "Original Quote ID", "type": "text", "value": quote_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": cust.get("name") if cust else None, "display_order": 2},
            {"name": "lines_info", "label": "Line Items", "type": "text", "value": lines_info, "display_order": 3},
            {"name": "requested_delivery_date", "label": "Delivery Date", "type": "date", "value": requested_delivery_date, "display_order": 4},
            {"name": "valid_days", "label": "Valid For (days)", "type": "number", "value": valid_days, "display_order": 5},
            {"name": "note", "label": "Notes", "type": "textarea", "value": note, "display_order": 6},
        ]

        return create_confirmation_response(
            tool_name="quote_revise",
            title=f"Revise Quote: {quote_id}",
            description="This will create a new quote revision and mark the original as superseded.",
            field_configs=field_configs,
            arguments=arguments,
            category="financial"
        )
