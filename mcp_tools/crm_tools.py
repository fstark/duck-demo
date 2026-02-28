"""MCP tools – CRM / customer management."""

from typing import Any, Dict, Optional

from mcp_tools._common import log_tool, create_confirmation_response
from services import customer_service


def register(mcp):
    """Register CRM tools."""

    @mcp.tool(name="crm_search_customers", meta={"tags": ["sales"]})
    @log_tool("crm_search_customers")
    def find_customers(
        name: Optional[str] = None,
        email: Optional[str] = None,
        company: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
        phone: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Find matching customers. Any provided field is used as a case-insensitive contains filter (except country which uses exact ISO match)."""
        return customer_service.find_customers(name, email, company, city, country, phone, limit)

    # MUTATING TOOL
    @mcp.tool(name="crm_create_customer", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("crm_create_customer")
    def create_customer(
        name: str,
        company: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address_line1: Optional[str] = None,
        address_line2: Optional[str] = None,
        city: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None,
        tax_id: Optional[str] = None,
        payment_terms: Optional[int] = None,
        currency: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiate customer creation with interactive confirmation dialog.
        This tool returns an MCP App UI for user confirmation before creating the customer.

        Parameters:
            name: Customer name (required)
            company: Company name
            email: Email address
            phone: Phone number
            address_line1: Street address line 1
            address_line2: Street address line 2 (apt, suite, etc.)
            city: City
            postal_code: Postal/ZIP code
            country: ISO 3166-1 alpha-2 country code (e.g., 'FR', 'DE', 'US')
            tax_id: Tax ID / VAT number for invoicing
            payment_terms: Payment terms in days (default: 30)
            currency: Preferred currency ISO code (default: 'EUR')
            notes: Internal notes about the customer

        Returns:
            UI metadata for interactive confirmation dialog. The actual customer creation
            happens after user confirms via the dialog.
        """
        arguments = {
            "name": name,
            "company": company,
            "email": email,
            "phone": phone,
            "address_line1": address_line1,
            "address_line2": address_line2,
            "city": city,
            "postal_code": postal_code,
            "country": country,
            "tax_id": tax_id,
            "payment_terms": payment_terms,
            "currency": currency,
            "notes": notes,
        }

        field_configs = [
            {"name": "name", "label": "Customer Name", "type": "text", "value": name, "required": True, "group": "Basic Info", "display_order": 1},
            {"name": "company", "label": "Company", "type": "text", "value": company, "group": "Basic Info", "display_order": 2},
            {"name": "email", "label": "Email", "type": "email", "value": email, "group": "Contact", "display_order": 3},
            {"name": "phone", "label": "Phone", "type": "text", "value": phone, "group": "Contact", "display_order": 4},
            {"name": "address_line1", "label": "Address Line 1", "type": "text", "value": address_line1, "group": "Address", "display_order": 5},
            {"name": "address_line2", "label": "Address Line 2", "type": "text", "value": address_line2, "group": "Address", "display_order": 6},
            {"name": "city", "label": "City", "type": "text", "value": city, "group": "Address", "display_order": 7},
            {"name": "postal_code", "label": "Postal Code", "type": "text", "value": postal_code, "group": "Address", "display_order": 8},
            {"name": "country", "label": "Country", "type": "text", "value": country, "help_text": "ISO 3166-1 alpha-2 code (e.g., FR, DE, US)", "group": "Address", "display_order": 9},
            {"name": "tax_id", "label": "Tax ID / VAT", "type": "text", "value": tax_id, "group": "Billing", "display_order": 10},
            {"name": "payment_terms", "label": "Payment Terms (days)", "type": "number", "value": payment_terms or 30, "group": "Billing", "display_order": 11},
            {"name": "currency", "label": "Currency", "type": "text", "value": currency or "EUR", "group": "Billing", "display_order": 12},
            {"name": "notes", "label": "Internal Notes", "type": "textarea", "value": notes, "group": "Other", "display_order": 13},
        ]

        return create_confirmation_response(
            tool_name="crm_create_customer",
            title=f"Create Customer: {name}",
            description="This will create a new customer record in the CRM system.",
            field_configs=field_configs,
            arguments=arguments,
            category="customer"
        )

    # MUTATING TOOL
    @mcp.tool(name="crm_update_customer", meta={
        "tags": ["sales"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("crm_update_customer")
    def update_customer(
        customer_id: str,
        name: Optional[str] = None,
        company: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address_line1: Optional[str] = None,
        address_line2: Optional[str] = None,
        city: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None,
        tax_id: Optional[str] = None,
        payment_terms: Optional[int] = None,
        currency: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing customer with user confirmation. Only provided fields will be updated.

        Parameters:
            customer_id: The customer ID to update (e.g., 'CUST-0044')
            name: New customer name
            company: New company name
            email: New email address
            phone: New phone number
            address_line1: New street address line 1
            address_line2: New street address line 2
            city: New city
            postal_code: New postal/ZIP code
            country: New ISO 3166-1 alpha-2 country code
            tax_id: New tax ID / VAT number
            payment_terms: New payment terms in days
            currency: New preferred currency ISO code
            notes: New internal notes

        Returns:
            Confirmation metadata for the customer update action.
        """
        arguments = {
            "customer_id": customer_id,
            "name": name,
            "company": company,
            "email": email,
            "phone": phone,
            "address_line1": address_line1,
            "address_line2": address_line2,
            "city": city,
            "postal_code": postal_code,
            "country": country,
            "tax_id": tax_id,
            "payment_terms": payment_terms,
            "currency": currency,
            "notes": notes
        }

        field_configs = [
            {"name": "customer_id", "label": "Customer ID", "type": "text", "value": customer_id, "required": True, "group": "Basic Info", "display_order": 1},
            {"name": "name", "label": "Name", "type": "text", "value": name, "group": "Basic Info", "display_order": 2},
            {"name": "company", "label": "Company", "type": "text", "value": company, "group": "Basic Info", "display_order": 3},
            {"name": "email", "label": "Email", "type": "email", "value": email, "group": "Contact", "display_order": 4},
            {"name": "phone", "label": "Phone", "type": "text", "value": phone, "group": "Contact", "display_order": 5},
            {"name": "address_line1", "label": "Address Line 1", "type": "text", "value": address_line1, "group": "Address", "display_order": 6},
            {"name": "address_line2", "label": "Address Line 2", "type": "text", "value": address_line2, "group": "Address", "display_order": 7},
            {"name": "city", "label": "City", "type": "text", "value": city, "group": "Address", "display_order": 8},
            {"name": "postal_code", "label": "Postal Code", "type": "text", "value": postal_code, "group": "Address", "display_order": 9},
            {"name": "country", "label": "Country", "type": "text", "value": country, "group": "Address", "display_order": 10},
            {"name": "tax_id", "label": "Tax ID / VAT", "type": "text", "value": tax_id, "group": "Billing", "display_order": 11},
            {"name": "payment_terms", "label": "Payment Terms (days)", "type": "number", "value": payment_terms, "group": "Billing", "display_order": 12},
            {"name": "currency", "label": "Currency", "type": "text", "value": currency, "group": "Billing", "display_order": 13},
            {"name": "notes", "label": "Notes", "type": "textarea", "value": notes, "group": "Other", "display_order": 14},
        ]

        return create_confirmation_response(
            tool_name="crm_update_customer",
            title=f"Update Customer: {customer_id}",
            description="This will update the customer record with the provided fields.",
            field_configs=field_configs,
            arguments=arguments,
            category="customer"
        )

    @mcp.tool(name="crm_get_customer", meta={"tags": ["sales"]})
    @log_tool("crm_get_customer")
    def get_customer_details(customer_id: str, include_orders: bool = True) -> Dict[str, Any]:
        """
        Get customer data plus up to 10 most recent sales orders.

        Parameters:
            customer_id: The customer ID (e.g., 'CUST-1000')
            include_orders: Whether to include recent orders (default: True)

        Returns:
            Dictionary with customer details and orders array with lines, shipments, and fulfillment status
        """
        return customer_service.get_customer_details(customer_id, include_orders)
