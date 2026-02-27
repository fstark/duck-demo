"""MCP tool definitions - thin wrappers around business logic services."""

import functools
import json
import logging
import os
from typing import Any, Dict, List, Optional, TypedDict, Union

from mcp.types import CallToolResult, TextContent

import config
from services import (
    simulation_service,
    customer_service,
    catalog_service,
    inventory_service,
    pricing_service,
    sales_service,
    logistics_service,
    production_service,
    recipe_service,
    purchase_service,
    messaging_service,
    quote_service,
    invoice_service,
    stats_service,
    admin_service,
    chart_service,
)


logger = logging.getLogger("duck-demo")


def log_tool(name: str):
    """Decorator to log tool calls with parameters and results."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                params_str = json.dumps({"args": args, "kwargs": kwargs}, default=str)
            except Exception:
                params_str = f"args={args}, kwargs={kwargs}"
            logger.info("[CallToolRequest] tool=%s params=%s", name, params_str)
            try:
                result = func(*args, **kwargs)
                try:
                    result_str = json.dumps(result, default=str)
                except Exception:
                    result_str = str(result)
                logger.info("[CallToolResponse] tool=%s result=%s", name, result_str)
                return result
            except Exception as exc:
                logger.exception("[CallToolError] tool=%s error=%s", name, exc)
                raise
        return wrapper
    return decorator


# ==================== Confirmation System Types ====================

class FieldMetadata(TypedDict, total=False):
    """Metadata for a single field in a confirmation dialog."""
    name: str              # Field identifier (matches argument name)
    label: str             # Display label for the field
    type: str              # Field type: 'text', 'email', 'number', 'date', 'boolean', 'textarea', 'select', 'object'
    value: Any             # Current value of the field
    required: bool         # Whether the field is required
    help_text: str         # Optional help text shown below the field
    group: str             # Optional group name for organizing fields
    display_order: int     # Optional order for display (lower = first)
    options: List[str]     # For 'select' type: list of options


class ConfirmationMetadata(TypedDict):
    """Complete metadata for a confirmation dialog."""
    original_tool: str     # Name of the tool being confirmed (for routing)
    title: str             # Dialog title (e.g., "Confirm Customer Creation")
    description: str       # Action description (e.g., "This will create a new customer record")
    category: str          # Category for styling/icons (e.g., "customer", "order", "financial")
    fields: List[FieldMetadata]  # Field definitions
    arguments: Dict[str, Any]    # Original tool arguments (preserved for dispatch)


def create_confirmation_response(
    tool_name: str,
    title: str,
    description: str,
    field_configs: List[Dict[str, Any]],
    arguments: Dict[str, Any],
    category: str = "general"
) -> CallToolResult:
    """
    Helper to create standardized confirmation response.
    
    Args:
        tool_name: Name of the original tool (for routing back through dispatcher)
        title: Dialog title
        description: Action description shown to user
        field_configs: List of field configurations (each dict becomes a FieldMetadata)
        arguments: Original tool arguments (will be passed to dispatcher)
        category: Category for styling (customer, order, financial, etc.)
    
    Returns:
        CallToolResult with confirmation metadata for MCP App consumption
    """
    fields: List[FieldMetadata] = []
    for config in field_configs:
        field: FieldMetadata = {
            "name": config["name"],
            "label": config.get("label", config["name"].replace("_", " ").title()),
            "type": config.get("type", "text"),
            "value": config["value"],
            "required": config.get("required", False),
        }
        if "help_text" in config:
            field["help_text"] = config["help_text"]
        if "group" in config:
            field["group"] = config["group"]
        if "display_order" in config:
            field["display_order"] = config["display_order"]
        if "options" in config:
            field["options"] = config["options"]
        fields.append(field)
    
    metadata: ConfirmationMetadata = {
        "original_tool": tool_name,
        "title": title,
        "description": description,
        "category": category,
        "fields": fields,
        "arguments": arguments
    }
    
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=f"Please confirm action: **{title}**"
            )
        ],
        structuredContent=metadata,
        isError=False
    )


def register_tools(mcp):
    """Register all MCP tools with the FastMCP instance.
    
    Tools are tagged for client-side filtering:
    - 'shared': Available to both sales and production agents
    - 'sales': Sales agent only (CRM, orders, shipping, emails)
    - 'production': Production agent only (manufacturing, recipes, materials)
    """
    
    @mcp.tool(name="user_get_current", meta={"tags": ["shared"]})
    @log_tool("user_get_current")
    def get_current_user() -> Dict[str, Any]:
        """Get current user information including first name, last name, role, and email."""
        return {
            "first_name": "Fred",
            "last_name": "Stark",
            "role": "Duck Inc Sales",
            "email": "fred.stark@rubberducks.ia"
        }
    
    # ==================== Generic Confirmation Dispatcher ====================
    
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
    
    @mcp.tool(name="stats_get_summary", meta={"tags": ["shared"]})
    @log_tool("stats_get_summary")
    def get_statistics(
        entity: str,
        metric: str = "count",
        group_by: Optional[Union[str, List[str]]] = None,
        field: Optional[str] = None,
        status: Optional[str] = None,
        item_type: Optional[str] = None,
        warehouse: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 100,
        return_chart: Optional[str] = None,
        chart_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get flexible statistics for any entity with optional grouping, filtering, and chart generation.
        ⚠️ USE THIS TOOL for any aggregation of >10 records. Never manually count from large datasets.
        
        Args:
            entity: The entity to query (see Entity Types below)
            metric: The metric to calculate (count, sum, avg, min, max)
            group_by: Field(s) to group by - string for single dimension, list for multi-dimensional (e.g., ["item_id", "status"])
            field: Field name for sum/avg/min/max operations (see Valid Fields below)
            status: Filter by status (for sales_orders, production_orders, shipments, purchase_orders)
            item_type: Filter by item type (for items)
            warehouse: Filter by warehouse (for stock)
            city: Filter by city (for customers)
            limit: Maximum results for grouped queries (default: 100)
            return_chart: Optional chart type to generate directly (pie, bar, line, stacked_bar, etc.)
            chart_title: Optional title for generated chart
        
        Entity Types and Valid Fields:
            - customers: fields=[id], groups=[city, company], dates=[created_at]
            - sales_orders: fields=[id], groups=[status, customer_id], dates=[created_at, requested_delivery_date]
            - sales_order_lines: fields=[qty], groups=[sales_order_id, item_id] 📦 Use for order quantities
            - items: fields=[unit_price], groups=[type]
            - stock: fields=[on_hand], groups=[warehouse, location, item_id]
            - production_orders: fields=[id, qty], groups=[status, item_id], dates=[started_at, completed_at, eta_finish, eta_ship] 🏭 qty via join with recipes
            - shipments: fields=[id], groups=[status], dates=[planned_departure, planned_arrival]
            - shipment_lines: fields=[qty], groups=[shipment_id, item_id], dates=[planned_departure, planned_arrival] 📦 Use for shipment quantities with dates via join
            - purchase_orders: fields=[qty], groups=[status, item_id, supplier_id], dates=[ordered_at, expected_delivery, received_at]
        
        💡 Key Schema Pattern:
            - Header tables (sales_orders, shipments): Have status/dates but NO quantities
            - Line tables (sales_order_lines, shipment_lines): Have quantities but NO status/dates
            - For quantity analysis by date: Count header records OR sum line quantities (separate queries)
        
        Group By Options:
            Single dimension: "status", "type", "city", "warehouse", "item_id", etc.
            Date grouping: "date:field_name", "month:field_name", "year:field_name"
            Multi-dimensional: ["item_id", "status"] - for stacked charts, pivot tables
        
        Chart Generation:
            - When return_chart is specified, generates chart directly from query results
            - Single dimension: All chart types supported (pie, bar, line, etc.)
            - Multi-dimensional: Automatically pivots for stacked charts (first field = labels, second field = series)
            - Returns both chart URL and raw data
        
        Examples:
            Single dimension with chart:
                entity="production_orders", metric="count", group_by="date:completed_at", return_chart="line"
            
            Multi-dimensional for stacked chart:
                entity="production_orders", metric="count", group_by=["status", "item_id"], return_chart="stacked_bar"
            
            Without chart (raw data only):
                entity="shipment_lines", metric="sum", field="qty", group_by="item_id"
        """
        return stats_service.get_statistics(entity, metric, group_by, field, status, item_type, warehouse, city, limit, return_chart, chart_title)
    
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
        # Prepare arguments for dispatcher
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
        
        # Define field configurations for display
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
    
    # MUTATING TOOL - Confirms and creates customer after user approval
    # NOTE: No tags - this tool is only callable by MCP App UI, not by agents
    
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
    
    @mcp.tool(name="catalog_get_item", meta={"tags": ["shared"]})
    @log_tool("catalog_get_item")
    def get_item(sku: str) -> Dict[str, Any]:
        """
        Fetch complete item details by SKU or item_id.
        Use this after search to get full details including image_url, uom, and reorder_qty.
        Accepts either SKU (e.g., 'ELVIS-RED-20') or item_id (e.g., 'ITEM-ELVIS-20').
        
        Parameters:
            sku: The item SKU or item_id
        
        Returns:
            Complete item details: id, sku, name, type, unit_price, uom, reorder_qty, image_url
        """
        return catalog_service.get_item(sku)
    
    @mcp.tool(name="catalog_inspect_item", meta={
        "tags": ["shared"],
        "ui": {
            "resourceUri": "ui://item-inspect/viewer",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("catalog_inspect_item")
    def inspect_item(sku: str) -> Dict[str, Any]:
        """
        Launch interactive 3D viewer to inspect an item in detail.
        This tool returns an MCP App UI with a rotating 3D wireframe model and item details overlay.
        
        Parameters:
            sku: The item SKU or item_id to inspect
        
        Returns:
            UI metadata for interactive 3D viewer. The viewer displays the item as a rotating
            wireframe model with mouse-controlled rotation and overlaid product details.
        """
        try:
            item = catalog_service.get_item(sku)
            
            # Load the 3D model data to send to the MCP app based on SKU
            model_path = os.path.join(os.path.dirname(__file__), "models", f"{item['sku']}.obj")
            model_data = None
            try:
                with open(model_path, 'r') as f:
                    model_data = f.read()
            except Exception as model_error:
                logger.warning(f"Failed to load 3D model for {item['sku']}: {model_error}")
            
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Launching 3D inspector for: **{item['name']}**"
                    )
                ],
                structuredContent={
                    **item,
                    "model_obj": model_data
                },
                isError=False
            )
        except Exception as e:
            logger.error(f"Error in catalog_inspect_item for sku={sku}: {e}", exc_info=True)
            # Return minimal valid response so UI still loads
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Launching 3D inspector (item not found: {sku})"
                    )
                ],
                structuredContent={
                    "sku": sku,
                    "name": "Item Not Found",
                    "type": "unknown",
                    "unit_price": 0.0
                },
                isError=False
            )
    
    @mcp.tool(name="catalog_search_items", meta={"tags": ["shared"]})
    @log_tool("catalog_search_items")
    def search_items(words: List[str], limit: int = 10, min_score: int = 1) -> Dict[str, Any]:
        """
        Fuzzy search for items by keywords in SKU or name, ranked by relevance.
        Returns MINIMAL fields only for efficient browsing.
        Use catalog_get_item(sku) to get complete details including image_url.

        Parameters:
            words: List of search terms to match
            limit: Maximum results to return (default: 10)
            min_score: Minimum match score (default: 1)
        
        Returns:
            Nested structure: {"items": [{"item": {...}, "score": N, "matched_words": [...]}]}
            Item object includes ONLY: id, sku, name, type, unit_price, ui_url
        """
        return catalog_service.search_items(words, limit, min_score)
    
    @mcp.tool(name="inventory_list_items", meta={"tags": ["shared"]})
    @log_tool("inventory_list_items")
    def inventory_list_items(in_stock_only: bool = False, item_type: Optional[str] = "finished_good", limit: int = 50) -> Dict[str, Any]:
        """
        List all catalog items with their current stock levels.
        Returns MINIMAL fields only for efficient browsing.
        Use catalog_get_item(sku) to get complete details including image_url, uom, reorder_qty.
        
        Parameters:
            in_stock_only: If True, only return items with available stock (default: False)
            item_type: Filter by item type - 'finished_good' (default, duck products), 'raw_material', 'component', or None for all types
            limit: Maximum number of items to return (default: 50)
        
        Returns:
            Dictionary with items array including ONLY:
            id, sku, name, type, unit_price, on_hand_total, available_total, ui_url
        """
        result = catalog_service.list_items(in_stock_only, item_type, limit)
        # Strip extra fields to keep response minimal for LLMs
        for item in result.get("items", []):
            item.pop("image_url", None)
            item.pop("uom", None)
            item.pop("reorder_qty", None)
        return result
    
    @mcp.tool(name="inventory_get_stock", meta={"tags": ["shared"]})
    @log_tool("inventory_get_stock")
    def get_stock_summary(item_id: Optional[str] = None, sku: Optional[str] = None) -> Dict[str, Any]:
        """Return on-hand and available by location for an item."""
        if not item_id and not sku:
            raise ValueError("Provide item_id or sku")
        if sku and not item_id:
            item = catalog_service.load_item(sku)
            if not item:
                raise ValueError(f"Item with SKU '{sku}' not found")
            item_id = item["id"]
        elif item_id and not sku:
            # Get SKU for UI link
            from services import db_conn
            with db_conn() as conn:
                sku_row = conn.execute("SELECT sku FROM items WHERE id = ?", (item_id,)).fetchone()
                sku = sku_row["sku"] if sku_row else str(item_id)
        summary = inventory_service.get_stock_summary(item_id)  # type: ignore[arg-type]
        from utils import ui_href
        summary["ui_url"] = ui_href("items", sku or item_id)
        return summary
    
    @mcp.tool(name="inventory_check_availability", meta={"tags": ["shared"]})
    @log_tool("inventory_check_availability")
    def inventory_check_availability(item_sku: str, quantity: float) -> Dict[str, Any]:
        """
        Check if sufficient inventory is available for an item.
        Returns availability status, on_hand total, and shortfall if any.
        
        Parameters:
            item_sku: The SKU of the item to check
            quantity: The quantity needed
        """
        return inventory_service.check_availability(item_sku, quantity)
    
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
    def search_sales_orders(customer_id: Optional[str] = None, limit: int = 5, sort: str = "most_recent") -> Dict[str, Any]:
        """
        Search sales orders, optionally filtered by customer. Returns full order details including pricing and fulfillment state.
        
        Parameters:
            customer_id: Optional customer ID to filter by (if omitted, searches all orders)
            limit: Maximum results (default: 5)
            sort: Sort order - 'most_recent' or by ID
        
        Returns:
            Dictionary with sales_orders array including customer info, lines, total, currency, and fulfillment_state
        """
        return sales_service.search_orders(customer_id, limit, sort)
    
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
        
        # Calculate total items
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
    def production_create_order(recipe_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new production order to execute one batch of a recipe.
        Shows confirmation dialog before creating the order.
        
        Parameters:
            recipe_id: The recipe to execute (e.g., 'RCP-ELVIS-20')
            notes: Optional notes for the production order
        
        Returns:
            Confirmation metadata for the production order creation action.
        """
        # Get recipe details for preview
        recipe = recipe_service.get_recipe(recipe_id)
        
        arguments = {"recipe_id": recipe_id, "notes": notes}
        
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
        # Get production order details for preview
        order = production_service.get_order(production_order_id)
        
        arguments = {"production_order_id": production_order_id}
        
        field_configs = [
            {"name": "production_order_id", "label": "Production Order ID", "type": "text", "value": production_order_id, "required": True, "display_order": 1},
            {"name": "recipe", "label": "Recipe", "type": "text", "value": order.get("recipe_id"), "display_order": 2},
            {"name": "qty_to_produce", "label": "Quantity to Produce", "type": "number", "value": order.get("qty_to_produce"), "display_order": 3},
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
        # Get production order details for preview
        order = production_service.get_order(production_order_id)
        
        arguments = {
            "production_order_id": production_order_id,
            "qty_produced": qty_produced,
            "warehouse": warehouse,
            "location": location
        }
        
        field_configs = [
            {"name": "production_order_id", "label": "Production Order ID", "type": "text", "value": production_order_id, "required": True, "display_order": 1},
            {"name": "recipe", "label": "Recipe", "type": "text", "value": order.get("recipe_id"), "display_order": 2},
            {"name": "qty_to_produce", "label": "Planned Quantity", "type": "number", "value": order.get("qty_to_produce"), "display_order": 3},
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
    
    @mcp.tool(name="catalog_list_recipes", meta={"tags": ["shared"]})
    @log_tool("catalog_list_recipes")
    def recipe_list(output_item_sku: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        List recipes, optionally filtering by output item SKU.
        
        Parameters:
            output_item_sku: Optional SKU to filter recipes that produce this item
            limit: Maximum number of recipes to return
        """
        return recipe_service.list_recipes(output_item_sku, limit)
    
    @mcp.tool(name="catalog_get_recipe", meta={"tags": ["shared"]})
    @log_tool("catalog_get_recipe")
    def recipe_get(recipe_id: str) -> Dict[str, Any]:
        """
        Get detailed recipe information including ingredients and operations.
        
        Parameters:
            recipe_id: The recipe ID (e.g., 'RCP-ELVIS-20')
        """
        return recipe_service.get_recipe(recipe_id)
    
    # MUTATING TOOL
    @mcp.tool(name="purchase_create_order", meta={
        "tags": ["production"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("purchase_create_order")
    def purchase_create_order(item_sku: str, qty: float, supplier_name: Optional[str] = None) -> Dict[str, Any]:
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
        # Get item details for preview
        item = catalog_service.get_item(item_sku)
        stock_info = inventory_service.get_stock(item_sku)
        
        arguments = {"item_sku": item_sku, "qty": qty, "supplier_name": supplier_name}
        
        # Estimate cost
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
        # Get list of materials that need restocking
        materials_needing_restock = []
        # Query for materials below reorder point
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
            # Use a simpler message if nothing needs restocking
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
        # Get purchase order details for preview
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
    
    @mcp.tool(name="simulation_get_time", meta={"tags": ["shared"]})
    @log_tool("simulation_get_time")
    def simulation_get_time() -> Dict[str, Any]:
        """
        Get the current simulated time.
        
        Returns:
            Dictionary with current_time (ISO format string)
        """
        return {"current_time": simulation_service.get_current_time()}
    
    @mcp.tool(name="simulation_advance_time", meta={"tags": ["shared"]})
    @log_tool("simulation_advance_time")
    def simulation_advance_time(
        hours: Optional[float] = None,
        days: Optional[int] = None,
        to_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Advance the simulated time forward.
        
        Parameters:
            hours: Number of hours to advance (e.g., 2.5)
            days: Number of days to advance (e.g., 7)
            to_time: ISO datetime to set time to (e.g., '2025-01-15 14:00:00')
        
        Returns:
            Dictionary with old_time and new_time
        """
        return simulation_service.advance_time(hours, days, to_time)
    
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
        customer_id: Optional[str] = None,
        sales_order_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        List emails with optional filters.
        Results sorted by modified_at DESC (most recently modified first).
        
        Note: To view a specific email by its ID (e.g., EMAIL-0006), use messaging_get_email instead.
        This tool is for listing/searching multiple emails with filters.
        """
        return messaging_service.list_emails(customer_id, sales_order_id, status, limit)
    
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
        # Get email details for preview
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
        # Get email details for preview
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
    
    # ── Quote tools ──────────────────────────────────────────────────────
    
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
        # Get customer details for preview
        customer = customer_service.get_customer(customer_id)
        
        arguments = {
            "customer_id": customer_id,
            "lines": lines,
            "requested_delivery_date": requested_delivery_date,
            "ship_to": ship_to,
            "note": note,
            "valid_days": valid_days
        }
        
        # Format lines for display
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
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        show_superseded: bool = False
    ) -> Dict[str, Any]:
        """
        List quotes with optional filters. By default, hides superseded quotes.
        
        Parameters:
            customer_id: Optional customer ID filter
            status: Optional status filter (draft, sent, accepted, rejected, expired, superseded)
            limit: Maximum results (default: 50)
            show_superseded: Whether to show superseded quotes (default: false)
        
        Returns:
            Dictionary with quotes array
        """
        return quote_service.list_quotes(customer_id, status, limit, show_superseded)
    
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
        # Get quote details for preview
        quote = quote_service.get_quote(quote_id)
        
        arguments = {"quote_id": quote_id}
        
        field_configs = [
            {"name": "quote_id", "label": "Quote ID", "type": "text", "value": quote_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": quote.get("customer_name"), "display_order": 2},
            {"name": "total", "label": "Total Amount", "type": "text", "value": f"{quote.get('total_amount', 0):.2f} {quote.get('currency', 'EUR')}", "display_order": 3},
            {"name": "items_count", "label": "Number of Items", "type": "number", "value": len(quote.get("items", [])), "display_order": 4},
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
        # Get quote details for preview
        quote = quote_service.get_quote(quote_id)
        
        arguments = {"quote_id": quote_id}
        
        field_configs = [
            {"name": "quote_id", "label": "Quote ID", "type": "text", "value": quote_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": quote.get("customer_name"), "display_order": 2},
            {"name": "total", "label": "Total Amount", "type": "text", "value": f"{quote.get('total_amount', 0):.2f} {quote.get('currency', 'EUR')}", "display_order": 3},
            {"name": "items_count", "label": "Number of Items", "type": "number", "value": len(quote.get("items", [])), "display_order": 4},
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
        # Get quote details for preview
        quote = quote_service.get_quote(quote_id)
        
        arguments = {"quote_id": quote_id, "reason": reason}
        
        field_configs = [
            {"name": "quote_id", "label": "Quote ID", "type": "text", "value": quote_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": quote.get("customer_name"), "display_order": 2},
            {"name": "total", "label": "Total Amount", "type": "text", "value": f"{quote.get('total_amount', 0):.2f} {quote.get('currency', 'EUR')}", "display_order": 3},
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
        # Get original quote details for preview
        quote = quote_service.get_quote(quote_id)
        
        changes = {}
        if lines is not None:
            changes["lines"] = lines
        if requested_delivery_date is not None:
            changes["requested_delivery_date"] = requested_delivery_date
        if ship_to is not None:
            changes["ship_to"] = ship_to
        if note is not None:
            changes["note"] = note
        changes["valid_days"] = valid_days
        
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
            {"name": "customer", "label": "Customer", "type": "text", "value": quote.get("customer_name"), "display_order": 2},
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
    
    # ── Invoice & Payment tools ──────────────────────────────────────────
    
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
        # Get sales order details for preview
        order = sales_service.get_order(sales_order_id)
        
        arguments = {"sales_order_id": sales_order_id}
        
        field_configs = [
            {"name": "sales_order_id", "label": "Sales Order ID", "type": "text", "value": sales_order_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": order.get("customer_name"), "display_order": 2},
            {"name": "total", "label": "Order Total", "type": "text", "value": f"{order.get('total_amount', 0):.2f} {order.get('currency', 'EUR')}", "display_order": 3},
            {"name": "items_count", "label": "Number of Items", "type": "number", "value": len(order.get("lines", [])), "display_order": 4},
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
        # Get invoice details for preview
        invoice = invoice_service.get_invoice(invoice_id)
        
        arguments = {"invoice_id": invoice_id, "payment_due_days": payment_due_days}
        
        field_configs = [
            {"name": "invoice_id", "label": "Invoice ID", "type": "text", "value": invoice_id, "required": True, "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": invoice.get("customer_name"), "display_order": 2},
            {"name": "total", "label": "Total Amount", "type": "text", "value": f"{invoice.get('total_amount', 0):.2f} {invoice.get('currency', 'EUR')}", "display_order": 3},
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
        # Get invoice details for preview
        invoice = invoice_service.get_invoice(invoice_id)
        
        arguments = {
            "invoice_id": invoice_id,
            "amount": amount,
            "payment_method": payment_method,
            "reference": reference,
            "notes": notes
        }
        
        field_configs = [
            {"name": "invoice_id", "label": "Invoice ID", "type": "text", "value": invoice_id, "required": True, "group": "Invoice", "display_order": 1},
            {"name": "customer", "label": "Customer", "type": "text", "value": invoice.get("customer_name"), "group": "Invoice", "display_order": 2},
            {"name": "invoice_total", "label": "Invoice Total", "type": "text", "value": f"{invoice.get('total_amount', 0):.2f} {invoice.get('currency', 'EUR')}", "group": "Invoice", "display_order": 3},
            {"name": "balance_due", "label": "Current Balance Due", "type": "text", "value": f"{invoice.get('balance_due', 0):.2f} {invoice.get('currency', 'EUR')}", "group": "Invoice", "display_order": 4},
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
    
    @mcp.tool(name="chart_generate", meta={"tags": ["shared"]})
    @log_tool("chart_generate")
    def chart_generate(
        chart_type: str,
        labels: List[str],
        values: Optional[List[float]] = None,
        series: Optional[List[Dict[str, Any]]] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a chart image and return a URL to access it.
        
        Parameters:
            chart_type: Type of chart - pie, bar, bar_horizontal, line, scatter, area, stacked_area, stacked_bar, waterfall, treemap
            labels: List of labels for x-axis or pie slices
            values: List of numeric values (single series, for backward compatibility)
            series: List of series dicts for multi-series charts: [{"name": "Q1", "values": [10, 20, 30]}, {"name": "Q2", "values": [15, 25, 35]}]
            title: Optional title for the chart
        
        Chart Types:
            - pie: Single series only, shows distribution with values and percentages
            - bar: Vertical bar chart, supports multiple series side-by-side
            - bar_horizontal: Horizontal bar chart, supports multiple series
            - line: Line chart with markers, great for trends over time
            - scatter: Scatter plot for correlations
            - area: Filled area under line, shows volume over time
            - stacked_area: Multiple series stacked, shows composition changes
            - stacked_bar: Multiple series stacked vertically
            - waterfall: Sequential changes (single series), shows cumulative effect
        
        Examples:
            Single series (backward compatible):
                chart_generate("pie", labels=["A", "B", "C"], values=[30, 50, 20])
            
            Multi-series comparison:
                chart_generate("bar", labels=["Jan", "Feb", "Mar"], 
                    series=[{"name": "2025", "values": [100, 120, 140]},
                            {"name": "2026", "values": [110, 130, 150]}])
            
            Waterfall (sequential changes):
                chart_generate("waterfall", labels=["Start", "Sales", "Costs", "End"], 
                    values=[1000, 500, -300, 1200])
        
        Returns:
            Dictionary with 'url' field containing the full URL to the generated chart image.
            Chart files are stored with timestamp-first filenames for easy date-based sorting and cleanup.
        """
        result = chart_service.generate_chart(chart_type, labels, values, series, title)
        return {"url": result["url"], "filename": result["filename"]}
    
    @mcp.tool(name="admin_reset_database", meta={"tags": ["shared"]})
    @log_tool("admin_reset_database")
    def admin_reset_database(secret: str) -> Dict[str, Any]:
        """
        Reset database to initial demo state (drops all tables and reloads).
        
        Parameters:
            secret: Safety parameter - must be asked to the user
        
        Returns:
            Dictionary with status message and initial_time
        """
        return admin_service.reset_database(secret)
