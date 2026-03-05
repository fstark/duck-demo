"""MCP tools – activity log query for agents."""

from typing import Any, Dict, Optional

from mcp_tools._common import log_tool
from services import activity_service


def register(mcp):
    """Register activity tools."""

    @mcp.tool(name="activity_get_log", meta={"tags": ["shared"]})
    @log_tool("activity_get_log")
    def activity_get_log(
        limit: int = 20,
        category: Optional[str] = None,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query the factory activity log.

        Use this to find out what happened in the factory — orders created,
        production completed, shipments dispatched, invoices issued, etc.

        Args:
            limit: Max entries to return (default 20, max 100).
            category: Filter by category: sales, production, logistics, purchasing, billing.
            action: Filter by action, e.g. 'sales_order.created', 'production_order.completed'.
            entity_type: Filter by entity type, e.g. 'sales_order', 'shipment'.
            entity_ids: Filter by specific entity IDs, e.g. ['SO-1042', 'SO-1043'].
            since: ISO datetime lower bound (inclusive).
            until: ISO datetime upper bound (inclusive).

        Returns:
            Dict with 'entries' list and 'total' count.
        """
        capped_limit = min(max(1, limit), 100)
        return activity_service.get_log(
            limit=capped_limit,
            offset=0,
            category=category,
            action=action,
            entity_type=entity_type,
            entity_ids=entity_ids,
            since=since,
            until=until,
        )
