"""MCP tools – email messaging."""

from typing import Any, Dict, List, Optional

from mcp_tools._common import log_tool, create_confirmation_response
from services import messaging_service


def register(mcp):
    """Register messaging tools."""

    @mcp.tool(name="messaging_create_email", meta={"tags": ["sales"]})
    @log_tool("messaging_create_email")
    def messaging_create_email(
        customer_id: str,
        subject: str,
        body: str,
        sales_order_id: Optional[str] = None,
        recipient_email: Optional[str] = None,
        recipient_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new email draft for a customer.
        Recipient details auto-populate from customer if not provided.
        If sales_order_id is provided, validates it belongs to the customer.

        Returns:
            Dictionary with email_id, email details, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return messaging_service.create_email(customer_id, subject, body, sales_order_id, recipient_email, recipient_name)

    @mcp.tool(name="messaging_list_emails", meta={"tags": ["sales"]})
    @log_tool("messaging_list_emails")
    def messaging_list_emails(
        customer_ids: Optional[List[str]] = None,
        sales_order_ids: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        List emails with optional filters.
        Results sorted by modified_at DESC (most recently modified first).

        Parameters:
            customer_ids: Optional list of customer IDs to filter by (e.g., ['CUST-0001', 'CUST-0002'])
            sales_order_ids: Optional list of sales order IDs to filter by (e.g., ['SO-1000', 'SO-1001'])
            status: Optional status filter (draft, sent)
            limit: Maximum results (default: 20)

        Note: To view a specific email by its ID (e.g., EMAIL-0006), use messaging_get_email instead.
        This tool is for listing/searching multiple emails with filters.
        """
        return messaging_service.list_emails(customer_ids, sales_order_ids, status, limit)

    @mcp.tool(name="messaging_get_email", meta={"tags": ["sales"]})
    @log_tool("messaging_get_email")
    def messaging_get_email(email_id: str) -> Dict[str, Any]:
        """
        Get detailed email information including related customer and sales order.
        Use this to retrieve a specific email by its ID (e.g., EMAIL-0006).

        Parameters:
            email_id: The email ID (e.g., 'EMAIL-1000', 'EMAIL-0006')

        Returns:
            Dictionary with email details, customer info, and optional sales_order details
        """
        return messaging_service.get_email(email_id)

    @mcp.tool(name="messaging_update_email", meta={"tags": ["sales"]})
    @log_tool("messaging_update_email")
    def messaging_update_email(email_id: str, subject: Optional[str] = None, body: Optional[str] = None) -> Dict[str, Any]:
        """
        Update email subject and/or body.
        Only draft emails can be updated.

        Returns:
            Dictionary with email_id, updated fields, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return messaging_service.update_email(email_id, subject, body)

    @mcp.tool(name="messaging_send_email", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("messaging_send_email")
    def messaging_send_email(email_id: str) -> Dict[str, Any]:
        """
        Mark email as sent with user confirmation (simulation only - no actual email sent).
        Only draft emails can be sent.

        Parameters:
            email_id: The email ID to send

        Returns:
            Confirmation metadata for the email send action.
        """
        email_data = messaging_service.get_email(email_id)
        email = email_data["email"]

        arguments = {"email_id": email_id}

        field_configs = [
            {"name": "email_id", "label": "Email ID", "type": "text", "value": email_id, "required": True, "display_order": 1},
            {"name": "to", "label": "To", "type": "email", "value": email.get("recipient_email"), "display_order": 2},
            {"name": "subject", "label": "Subject", "type": "text", "value": email.get("subject"), "display_order": 3},
            {"name": "body", "label": "Body", "type": "textarea", "value": email.get("body"), "display_order": 4},
        ]

        return create_confirmation_response(
            tool_name="messaging_send_email",
            title=f"Send Email: {email.get('subject', email_id)}",
            description="This will mark the email as sent. This action is irreversible.",
            field_configs=field_configs,
            arguments=arguments,
            category="messaging"
        )

    @mcp.tool(name="messaging_delete_email", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("messaging_delete_email")
    def messaging_delete_email(email_id: str) -> Dict[str, Any]:
        """
        Delete an email with user confirmation.
        Only draft emails can be deleted.

        Parameters:
            email_id: The email ID to delete

        Returns:
            Confirmation metadata for the email deletion action.
        """
        email_data = messaging_service.get_email(email_id)
        email = email_data["email"]

        arguments = {"email_id": email_id}

        field_configs = [
            {"name": "email_id", "label": "Email ID", "type": "text", "value": email_id, "required": True, "display_order": 1},
            {"name": "to", "label": "To", "type": "email", "value": email.get("recipient_email"), "display_order": 2},
            {"name": "subject", "label": "Subject", "type": "text", "value": email.get("subject"), "display_order": 3},
        ]

        return create_confirmation_response(
            tool_name="messaging_delete_email",
            title=f"Delete Email: {email.get('subject', email_id)}",
            description="This will permanently delete the email draft.",
            field_configs=field_configs,
            arguments=arguments,
            category="messaging"
        )
