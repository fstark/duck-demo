"""MCP tools – flexible statistics with optional charting."""

from typing import Any, Dict, List, Optional, Union

from mcp_tools._common import log_tool
from services import stats_service


def register(mcp):
    """Register statistics tools."""

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
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
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
            date_from: Filter records from this date (inclusive, YYYY-MM-DD). Uses the entity's primary date field (e.g., created_at for sales_orders/sales_order_lines, completed_at for production_orders)
            date_to: Filter records up to this date (inclusive, YYYY-MM-DD). Uses the same date field as date_from
            limit: Maximum results for grouped queries (default: 100)
            return_chart: Optional chart type to generate directly (pie, bar, line, stacked_bar, etc.)
            chart_title: Optional title for generated chart

        Entity Types and Valid Fields:
            - customers: fields=[id], groups=[city, company], dates=[created_at]
            - sales_orders: fields=[id], groups=[status, customer_id], dates=[created_at, requested_delivery_date]
            - sales_order_lines: fields=[qty], groups=[sales_order_id, item_id], dates=[created_at] 📦 Use for order quantities (dates from parent sales_orders)
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

            Most popular duck in October 2025:
                entity="sales_order_lines", metric="sum", field="qty", group_by="item_id", date_from="2025-10-01", date_to="2025-10-31", limit=1
        """
        return stats_service.get_statistics(entity, metric, group_by, field, status, item_type, warehouse, city, limit, return_chart, chart_title, date_from, date_to)
