"""API routes package – register all REST routes with FastMCP."""

from api_routes import (
    system_routes,
    customer_routes,
    catalog_routes,
    stock_routes,
    sales_routes,
    shipment_routes,
    production_routes,
    recipe_routes,
    supplier_routes,
    purchase_routes,
    email_routes,
    quote_routes,
    invoice_routes,
)

_MODULES = [
    system_routes,
    customer_routes,
    catalog_routes,
    stock_routes,
    sales_routes,
    shipment_routes,
    production_routes,
    recipe_routes,
    supplier_routes,
    purchase_routes,
    email_routes,
    quote_routes,
    invoice_routes,
]


def register_all_routes(mcp):
    """Register every domain's routes with the FastMCP instance."""
    for mod in _MODULES:
        mod.register(mcp)
