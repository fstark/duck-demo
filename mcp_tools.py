"""MCP tool definitions - thin wrappers around business logic services."""

import functools
import json
import logging
from typing import Any, Dict, List, Optional

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


def register_tools(mcp):
    """Register all MCP tools with the FastMCP instance."""
    
    @mcp.tool(name="get_current_user")
    @log_tool("get_current_user")
    def get_current_user() -> Dict[str, Any]:
        """Get current user information including first name, last name, role, and email."""
        return {
            "first_name": "Fred",
            "last_name": "Stark",
            "role": "Duck Inc Sales",
            "email": "fred.stark@rubberducks.ia"
        }
    
    @mcp.tool(name="get_statistics")
    @log_tool("get_statistics")
    def get_statistics(
        entity: str,
        metric: str = "count",
        group_by: Optional[str] = None,
        field: Optional[str] = None,
        status: Optional[str] = None,
        item_type: Optional[str] = None,
        warehouse: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get flexible statistics for any entity with optional grouping and filtering.
        
        Args:
            entity: The entity to query (customers, sales_orders, items, stock, production_orders, shipments)
            metric: The metric to calculate (count, sum, avg, min, max)
            group_by: Optional field to group by (status, type, city, warehouse, etc.)
            field: Field name for sum/avg/min/max operations (qty, on_hand, unit_price, etc.)
            status: Filter by status (for sales_orders, production_orders, shipments)
            item_type: Filter by item type (for items)
            warehouse: Filter by warehouse (for stock)
            city: Filter by city (for customers)
            limit: Maximum results for grouped queries
        
        Examples:
            - Total customers: entity="customers", metric="count"
            - Sales orders by status: entity="sales_orders", metric="count", group_by="status"
            - Total stock by warehouse: entity="stock", metric="sum", field="on_hand", group_by="warehouse"
            - Items by type: entity="items", metric="count", group_by="type"
        """
        return stats_service.get_statistics(entity, metric, group_by, field, status, item_type, warehouse, city, limit)
    
    @mcp.tool(name="crm_find_customers")
    @log_tool("crm_find_customers")
    def find_customers(
        name: Optional[str] = None,
        email: Optional[str] = None,
        company: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Find matching customers. Any provided field is used as a case-insensitive contains filter."""
        return customer_service.find_customers(name, email, company, city, limit)
    
    @mcp.tool(name="crm_create_customer")
    @log_tool("crm_create_customer")
    def create_customer(name: str, company: Optional[str] = None, email: Optional[str] = None, city: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new customer.
        
        Parameters:
            name: Customer name (required)
            company: Company name
            email: Email address
            city: City location
        
        Returns:
            Dictionary with customer_id, customer details, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return customer_service.create_customer(name, company, email, city)
    
    @mcp.tool(name="crm_get_customer_details")
    @log_tool("crm_get_customer_details")
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
    
    @mcp.tool(name="catalog_get_item")
    @log_tool("catalog_get_item")
    def get_item(sku: str) -> Dict[str, Any]:
        """
        Fetch complete item details by SKU.
        Use this after search to get full details including image_url, uom, and reorder_qty.
        
        Parameters:
            sku: The item SKU (e.g., 'ELVIS-RED-20')
        
        Returns:
            Complete item details: id, sku, name, type, unit_price, uom, reorder_qty, image_url
        """
        return catalog_service.get_item(sku)
    
    @mcp.tool(name="catalog_search_items_basic")
    @log_tool("catalog_search_items_basic")
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
    
    @mcp.tool(name="inventory_list_items")
    @log_tool("inventory_list_items")
    def inventory_list_items(in_stock_only: bool = False, limit: int = 50) -> Dict[str, Any]:
        """
        List all catalog items with their current stock levels.
        Returns MINIMAL fields only for efficient browsing.
        Use catalog_get_item(sku) to get complete details including image_url, uom, reorder_qty.
        
        Parameters:
            in_stock_only: If True, only return items with available stock (default: False)
            limit: Maximum number of items to return (default: 50)
        
        Returns:
            Dictionary with items array including ONLY:
            id, sku, name, type, unit_price, on_hand_total, available_total, ui_url
        """
        result = catalog_service.list_items(in_stock_only, limit)
        # Strip extra fields to keep response minimal for LLMs
        for item in result.get("items", []):
            item.pop("image_url", None)
            item.pop("uom", None)
            item.pop("reorder_qty", None)
        return result
    
    @mcp.tool(name="inventory_get_stock_summary")
    @log_tool("inventory_get_stock_summary")
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
    
    @mcp.tool(name="inventory_check_availability")
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
    
    @mcp.tool(name="sales_quote_options")
    @log_tool("sales_quote_options")
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
    
    @mcp.tool(name="sales_create_sales_order")
    @log_tool("sales_create_sales_order")
    def create_sales_order(
        customer_id: str,
        requested_delivery_date: Optional[str] = None,
        ship_to: Optional[Dict[str, Any]] = None,
        lines: Optional[List[Dict[str, Any]]] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a draft sales order with lines.
        
        Returns:
            Dictionary with sales_order_id, status, lines, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return sales_service.create_order(customer_id, requested_delivery_date, ship_to, lines, note)
    
    @mcp.tool(name="sales_price_sales_order")
    @log_tool("sales_price_sales_order")
    def price_sales_order(sales_order_id: str, pricelist: Optional[str] = None) -> Dict[str, Any]:
        """Apply simple pricing logic (12 EUR each, 5% discount for 24+, free shipping over €300)."""
        return pricing_service.compute_pricing(sales_order_id)
    
    @mcp.tool(name="sales_search_sales_orders")
    @log_tool("sales_search_sales_orders")
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
    
    @mcp.tool(name="sales_get_sales_order")
    @log_tool("sales_get_sales_order")
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
    
    @mcp.tool(name="sales_link_shipment_to_sales_order")
    @log_tool("sales_link_shipment_to_sales_order")
    def link_shipment_to_sales_order(sales_order_id: str, shipment_id: str) -> Dict[str, Any]:
        """
        Link an existing shipment to a sales order.
        
        Returns:
            Dictionary with sales_order_id, shipment_id, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return sales_service.link_shipment(sales_order_id, shipment_id)
    
    @mcp.tool(name="logistics_create_shipment")
    @log_tool("logistics_create_shipment")
    def create_shipment(
        ship_from: Optional[Dict[str, Any]] = None,
        ship_to: Optional[Dict[str, Any]] = None,
        planned_departure: Optional[str] = None,
        planned_arrival: Optional[str] = None,
        packages: Optional[List[Dict[str, Any]]] = None,
        reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a planned shipment with package contents and delivery schedule.
        
        Parameters:
            ship_from: Dict with warehouse info {warehouse: str}
            ship_to: Dict with address {line1, postal_code, city, country}
            planned_departure: Departure date in ISO format
            planned_arrival: Arrival date in ISO format
            packages: List of dicts with contents: [{contents: [{sku, qty}]}]
            reference: Optional sales order reference {type: 'sales_order', id: 'SO-1000'}
        
        Returns:
            Dictionary with shipment_id, status, planned dates, ui_url, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return logistics_service.create_shipment(ship_from, ship_to, planned_departure, planned_arrival, packages, reference)
    
    @mcp.tool(name="logistics_get_shipment_status")
    @log_tool("logistics_get_shipment_status")
    def get_shipment_status(shipment_id: str) -> Dict[str, Any]:
        """
        Get shipment status including associated sales orders and customer details.
        
        Parameters:
            shipment_id: The shipment ID (e.g., 'SHIP-1000')
        
        Returns:
            Shipment details with status, dates, and sales_orders array with customer info
        """
        return logistics_service.get_shipment_status(shipment_id)
    
    @mcp.tool(name="production_get_statistics")
    @log_tool("production_get_statistics")
    def get_production_statistics() -> Dict[str, Any]:
        """Get production statistics including total production orders and breakdown by status."""
        return production_service.get_statistics()
    
    @mcp.tool(name="production_get_production_order_status")
    @log_tool("production_get_production_order_status")
    def get_production_order_status(production_order_id: str) -> Dict[str, Any]:
        """
        Get detailed production order status including operations, recipe, and ingredients.
        
        Parameters:
            production_order_id: The production order ID (e.g., 'MO-1000')
        
        Returns:
            Production order details with item info, status, operations array, and recipe details with ingredients
        """
        return production_service.get_order_status(production_order_id)
    
    @mcp.tool(name="production_find_orders_by_date_range")
    @log_tool("production_find_orders_by_date_range")
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
    
    @mcp.tool(name="production_create_order")
    @log_tool("production_create_order")
    def production_create_order(recipe_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new production order to execute one batch of a recipe.
        Checks ingredient availability and creates order with 'planned' status.
        Creates production operations for each step in the recipe.
        
        Parameters:
            recipe_id: The recipe to execute (e.g., 'RCP-ELVIS-20')
            notes: Optional notes for the production order
        
        Returns:
            Dictionary with production_order_id, status, eta dates, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return production_service.create_order(recipe_id, notes)
    
    @mcp.tool(name="production_start_order")
    @log_tool("production_start_order")
    def production_start_order(production_order_id: str) -> Dict[str, Any]:
        """
        Start a production order (change status from 'ready' to 'in_progress').
        Sets current_operation to the first operation in the recipe.
        
        Parameters:
            production_order_id: The production order ID (e.g., 'MO-1000')
        
        Returns:
            Dictionary with production_order_id, status, current_operation, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return production_service.start_order(production_order_id)
    
    @mcp.tool(name="production_complete_order")
    @log_tool("production_complete_order")
    def production_complete_order(
        production_order_id: str,
        qty_produced: int,
        warehouse: str = "MAIN",
        location: str = "FG-A"
    ) -> Dict[str, Any]:
        """
        Complete a production order and add produced goods to stock.
        
        Parameters:
            production_order_id: The production order ID (e.g., 'MO-1000')
            qty_produced: Actual quantity produced
            warehouse: Warehouse to add stock to (default: MAIN)
            location: Location within warehouse (default: FG-A)
        
        Returns:
            Dictionary with production_order_id, qty_produced, stock_id, warehouse, location, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return production_service.complete_order(production_order_id, qty_produced, warehouse, location)
    
    @mcp.tool(name="recipe_list")
    @log_tool("recipe_list")
    def recipe_list(output_item_sku: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        List recipes, optionally filtering by output item SKU.
        
        Parameters:
            output_item_sku: Optional SKU to filter recipes that produce this item
            limit: Maximum number of recipes to return
        """
        return recipe_service.list_recipes(output_item_sku, limit)
    
    @mcp.tool(name="recipe_get")
    @log_tool("recipe_get")
    def recipe_get(recipe_id: str) -> Dict[str, Any]:
        """
        Get detailed recipe information including ingredients and operations.
        
        Parameters:
            recipe_id: The recipe ID (e.g., 'RCP-ELVIS-20')
        """
        return recipe_service.get_recipe(recipe_id)
    
    @mcp.tool(name="purchase_create_order")
    @log_tool("purchase_create_order")
    def purchase_create_order(item_sku: str, qty: float, supplier_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a purchase order for raw materials or components.
        If supplier_name not provided, auto-selects based on item type.
        
        Parameters:
            item_sku: SKU of item to purchase (e.g., 'ITEM-PVC')
            qty: Quantity to order
            supplier_name: Optional supplier name (auto-selected if not provided)
        
        Returns:
            Dictionary with purchase_order_id, item, supplier info, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return purchase_service.create_order(item_sku, qty, supplier_name)
    
    @mcp.tool(name="purchase_restock_materials")
    @log_tool("purchase_restock_materials")
    def purchase_restock_materials() -> Dict[str, Any]:
        """
        Check all raw materials and create purchase orders for items below reorder quantity.
        
        Returns:
            Dictionary with items_checked count, purchase_orders_created count, and purchase_orders array.
            **Summarize the results for the user** (e.g., 'Created 3 purchase orders to restock 5 items').
        """
        return purchase_service.restock_materials()
    
    @mcp.tool(name="purchase_receive_order")
    @log_tool("purchase_receive_order")
    def purchase_receive_order(purchase_order_id: str, warehouse: str = "MAIN", location: str = "RM-A") -> Dict[str, Any]:
        """
        Receive a purchase order delivery and add materials to stock.
        
        Parameters:
            purchase_order_id: The purchase order ID (e.g., 'PO-1000')
            warehouse: Warehouse to add stock to (default: MAIN)
            location: Location within warehouse (default: RM-A for raw materials)
        
        Returns:
            Dictionary with stock_id, quantities received, warehouse location, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return purchase_service.receive(purchase_order_id, warehouse, location)
    
    @mcp.tool(name="simulation_get_time")
    @log_tool("simulation_get_time")
    def simulation_get_time() -> Dict[str, Any]:
        """
        Get the current simulated time.
        
        Returns:
            Dictionary with current_time (ISO format string)
        """
        return {"current_time": simulation_service.get_current_time()}
    
    @mcp.tool(name="simulation_advance_time")
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
    
    @mcp.tool(name="messaging_create_email")
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
    
    @mcp.tool(name="messaging_list_emails")
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
        """
        return messaging_service.list_emails(customer_id, sales_order_id, status, limit)
    
    @mcp.tool(name="messaging_get_email")
    @log_tool("messaging_get_email")
    def messaging_get_email(email_id: str) -> Dict[str, Any]:
        """
        Get detailed email information including related customer and sales order.
        
        Parameters:
            email_id: The email ID (e.g., 'EMAIL-1000')
        
        Returns:
            Dictionary with email details, customer info, and optional sales_order details
        """
        return messaging_service.get_email(email_id)
    
    @mcp.tool(name="messaging_update_email")
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
    
    @mcp.tool(name="messaging_send_email")
    @log_tool("messaging_send_email")
    def messaging_send_email(email_id: str) -> Dict[str, Any]:
        """
        Mark email as sent (simulation only - no actual email sent).
        Only draft emails can be sent.
        
        Returns:
            Dictionary with email_id, status, and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return messaging_service.send_email(email_id)
    
    @mcp.tool(name="messaging_delete_email")
    @log_tool("messaging_delete_email")
    def messaging_delete_email(email_id: str) -> Dict[str, Any]:
        """
        Delete an email.
        Only draft emails can be deleted.
        
        Returns:
            Dictionary with email_id and `message` field.
            **Always relay the message verbatim to the user to confirm the action.**
        """
        return messaging_service.delete_email(email_id)
    
    @mcp.tool(name="chart_generate")
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
            chart_type: Type of chart - pie, bar, bar_horizontal, line, scatter, area, stacked_area, stacked_bar, waterfall
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
        filename = result["filename"]
        url = f"{config.API_BASE}/api/charts/{filename}"
        return {"url": url, "filename": filename}
    
    @mcp.tool(name="admin_reset_database")
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
