"""MCP tools package – register all tools with FastMCP.

Tools are tagged for client-side filtering:
- 'shared': Available to both sales and production agents
- 'sales': Sales agent only (CRM, orders, shipping, emails)
- 'production': Production agent only (manufacturing, recipes, materials)
"""

from mcp_tools import (
    user_tools,
    confirm_tools,
    stats_tools,
    crm_tools,
    catalog_tools,
    inventory_tools,
    sales_tools,
    logistics_tools,
    production_tools,
    work_center_tools,
    purchase_tools,
    simulation_tools,
    messaging_tools,
    quote_tools,
    invoice_tools,
    chart_tools,
    admin_tools,
    activity_tools,
)

_MODULES = [
    user_tools,
    confirm_tools,
    stats_tools,
    crm_tools,
    catalog_tools,
    inventory_tools,
    sales_tools,
    logistics_tools,
    production_tools,
    work_center_tools,
    purchase_tools,
    simulation_tools,
    messaging_tools,
    quote_tools,
    invoice_tools,
    chart_tools,
    admin_tools,
    activity_tools,
]


def register_all_tools(mcp):
    """Register every domain's tools with the FastMCP instance."""
    for mod in _MODULES:
        mod.register(mcp)
