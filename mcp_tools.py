"""MCP tool definitions - thin wrappers around business logic services."""

import functools
import json
import logging
from typing import Any, Dict, List, Optional

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
        """Get flexible statistics for any entity with optional grouping and filtering."""
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
        """Create a new customer."""
        return customer_service.create_customer(name, company, email, city)
    
    @mcp.tool(name="crm_get_customer_details")
    @log_tool("crm_get_customer_details")
    def get_customer_details(customer_id: str, include_orders: bool = True) -> Dict[str, Any]:
        """Get customer data plus recent orders."""
        return customer_service.get_customer_details(customer_id, include_orders)
    
    @mcp.tool(name="catalog_get_item")
    @log_tool("catalog_get_item")
    def get_item(sku: str) -> Dict[str, Any]:
        """Fetch an item by SKU."""
        return catalog_service.get_item(sku)
    
    @mcp.tool(name="catalog_search_items")
    @log_tool("catalog_search_items")
    def search_items(words: List[str], limit: int = 10, min_score: int = 1) -> Dict[str, Any]:
        """Fuzzy item search via containment on SKU/name tokens."""
        return catalog_service.search_items(words, limit, min_score)
    
    @mcp.tool(name="inventory_list_items")
    @log_tool("inventory_list_items")
    def inventory_list_items(in_stock_only: bool = False, limit: int = 50) -> Dict[str, Any]:
        """List items, optionally only those with available stock."""
        return catalog_service.list_items(in_stock_only, limit)
    
    @mcp.tool(name="inventory_get_stock_summary")
    @log_tool("inventory_get_stock_summary")
    def get_stock_summary(item_id: Optional[str] = None, sku: Optional[str] = None) -> Dict[str, Any]:
        """Return on-hand and available by location for an item."""
        if not item_id and not sku:
            raise ValueError("Provide item_id or sku")
        if sku and not item_id:
            item = catalog_service.load_item(sku)
            if not item:
                raise ValueError("Item not found")
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
    def inventory_check_availability(item_sku: str, qty_required: float) -> Dict[str, Any]:
        """Check if sufficient inventory is available for an item."""
        return inventory_service.check_availability(item_sku, qty_required)
    
    @mcp.tool(name="sales_quote_options")
    @log_tool("sales_quote_options")
    def sales_quote_options(
        sku: str,
        qty: int,
        need_by: Optional[str] = None,
        allowed_substitutions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate quote / fulfillment options for a request."""
        return pricing_service.calculate_quote_options(sku, qty, need_by, allowed_substitutions or [])
    
    @mcp.tool(name="sales_create_sales_order")
    @log_tool("sales_create_sales_order")
    def create_sales_order(
        customer_id: str,
        requested_delivery_date: Optional[str] = None,
        ship_to: Optional[Dict[str, Any]] = None,
        lines: Optional[List[Dict[str, Any]]] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a draft sales order with lines."""
        return sales_service.create_order(customer_id, requested_delivery_date, ship_to, lines, note)
    
    @mcp.tool(name="sales_price_sales_order")
    @log_tool("sales_price_sales_order")
    def price_sales_order(sales_order_id: str, pricelist: Optional[str] = None) -> Dict[str, Any]:
        """Apply pricing logic."""
        return pricing_service.compute_pricing(sales_order_id)
    
    @mcp.tool(name="sales_search_sales_orders")
    @log_tool("sales_search_sales_orders")
    def search_sales_orders(customer_id: Optional[str] = None, limit: int = 5, sort: str = "most_recent") -> Dict[str, Any]:
        """Return recent sales orders for a customer."""
        return sales_service.search_orders(customer_id, limit, sort)
    
    @mcp.tool(name="sales_get_sales_order")
    @log_tool("sales_get_sales_order")
    def get_sales_order(sales_order_id: str) -> Dict[str, Any]:
        """Return a sales order with lines, pricing, and linked shipments."""
        detail = sales_service.get_order_details(sales_order_id)
        if not detail:
            raise ValueError("Sales order not found")
        return detail
    
    @mcp.tool(name="sales_link_shipment_to_sales_order")
    @log_tool("sales_link_shipment_to_sales_order")
    def link_shipment_to_sales_order(sales_order_id: str, shipment_id: str) -> Dict[str, Any]:
        """Link an existing shipment to a sales order."""
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
        """Create a planned shipment with basic package contents."""
        return logistics_service.create_shipment(ship_from, ship_to, planned_departure, planned_arrival, packages, reference)
    
    @mcp.tool(name="logistics_get_shipment_status")
    @log_tool("logistics_get_shipment_status")
    def get_shipment_status(shipment_id: str) -> Dict[str, Any]:
        """Return the status of a shipment."""
        return logistics_service.get_shipment_status(shipment_id)
    
    @mcp.tool(name="production_get_statistics")
    @log_tool("production_get_statistics")
    def get_production_statistics() -> Dict[str, Any]:
        """Get production statistics including total production orders and breakdown by status."""
        return production_service.get_statistics()
    
    @mcp.tool(name="production_get_production_order_status")
    @log_tool("production_get_production_order_status")
    def get_production_order_status(production_order_id: str) -> Dict[str, Any]:
        """Return status of a production order."""
        return production_service.get_order_status(production_order_id)
    
    @mcp.tool(name="production_find_orders_by_date_range")
    @log_tool("production_find_orders_by_date_range")
    def find_production_orders_by_date_range(start_date: str, end_date: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve all production orders scheduled to finish within a specific date range."""
        return production_service.find_orders_by_date_range(start_date, end_date, limit)
    
    @mcp.tool(name="production_create_order")
    @log_tool("production_create_order")
    def production_create_order(recipe_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Create a new production order to execute one batch of a recipe."""
        return production_service.create_order(recipe_id, notes)
    
    @mcp.tool(name="production_start_order")
    @log_tool("production_start_order")
    def production_start_order(production_order_id: str) -> Dict[str, Any]:
        """Start a production order (change status from 'ready' to 'in_progress')."""
        return production_service.start_order(production_order_id)
    
    @mcp.tool(name="production_complete_order")
    @log_tool("production_complete_order")
    def production_complete_order(
        production_order_id: str,
        qty_produced: int,
        warehouse: str = "MAIN",
        location: str = "FG-A"
    ) -> Dict[str, Any]:
        """Complete a production order and add produced goods to stock."""
        return production_service.complete_order(production_order_id, qty_produced, warehouse, location)
    
    @mcp.tool(name="recipe_list")
    @log_tool("recipe_list")
    def recipe_list(output_item_sku: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """List recipes, optionally filtering by output item SKU."""
        return recipe_service.list_recipes(output_item_sku, limit)
    
    @mcp.tool(name="recipe_get")
    @log_tool("recipe_get")
    def recipe_get(recipe_id: str) -> Dict[str, Any]:
        """Get detailed recipe information including ingredients and operations."""
        return recipe_service.get_recipe(recipe_id)
    
    @mcp.tool(name="purchase_create_order")
    @log_tool("purchase_create_order")
    def purchase_create_order(item_sku: str, qty: float, supplier_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a purchase order for raw materials or components."""
        return purchase_service.create_order(item_sku, qty, supplier_name)
    
    @mcp.tool(name="purchase_restock_materials")
    @log_tool("purchase_restock_materials")
    def purchase_restock_materials() -> Dict[str, Any]:
        """Check all raw materials and create purchase orders for items below reorder quantity."""
        return purchase_service.restock_materials()
    
    @mcp.tool(name="purchase_receive")
    @log_tool("purchase_receive")
    def purchase_receive(purchase_order_id: str, warehouse: str = "MAIN", location: str = "RM-A") -> Dict[str, Any]:
        """Receive a purchase order and add materials to stock."""
        return purchase_service.receive(purchase_order_id, warehouse, location)
    
    @mcp.tool(name="simulation_get_time")
    @log_tool("simulation_get_time")
    def simulation_get_time() -> Dict[str, Any]:
        """Get the current simulated time."""
        return {"current_time": simulation_service.get_current_time()}
    
    @mcp.tool(name="simulation_advance_time")
    @log_tool("simulation_advance_time")
    def simulation_advance_time(
        hours: Optional[float] = None,
        days: Optional[int] = None,
        to_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """Advance the simulated time forward."""
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
        """Create a new email draft for a customer."""
        return messaging_service.create_email(customer_id, subject, body, sales_order_id, recipient_email, recipient_name)
    
    @mcp.tool(name="messaging_list_emails")
    @log_tool("messaging_list_emails")
    def messaging_list_emails(
        customer_id: Optional[str] = None,
        sales_order_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """List emails with optional filters."""
        return messaging_service.list_emails(customer_id, sales_order_id, status, limit)
    
    @mcp.tool(name="messaging_get_email")
    @log_tool("messaging_get_email")
    def messaging_get_email(email_id: str) -> Dict[str, Any]:
        """Get detailed email information including related customer and sales order."""
        return messaging_service.get_email(email_id)
    
    @mcp.tool(name="messaging_update_email")
    @log_tool("messaging_update_email")
    def messaging_update_email(email_id: str, subject: Optional[str] = None, body: Optional[str] = None) -> Dict[str, Any]:
        """Update email subject and/or body."""
        return messaging_service.update_email(email_id, subject, body)
    
    @mcp.tool(name="messaging_send_email")
    @log_tool("messaging_send_email")
    def messaging_send_email(email_id: str) -> Dict[str, Any]:
        """Mark email as sent (simulation only)."""
        return messaging_service.send_email(email_id)
    
    @mcp.tool(name="messaging_delete_email")
    @log_tool("messaging_delete_email")
    def messaging_delete_email(email_id: str) -> Dict[str, Any]:
        """Delete an email."""
        return messaging_service.delete_email(email_id)
    
    @mcp.tool(name="admin_reset_database")
    @log_tool("admin_reset_database")
    def admin_reset_database(confirm: str) -> Dict[str, Any]:
        """Reset database to initial demo state."""
        return admin_service.reset_database(confirm)
