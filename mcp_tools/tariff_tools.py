"""MCP tool – tariff code suggestions."""

from typing import Any, Dict

from mcp_tools._common import log_tool
from services.tariff import suggest_tariff_codes


def register(mcp):
    """Register tariff tools."""

    @mcp.tool(
        name="tariff_suggest",
        description=(
            "Suggest HS tariff codes for products being shipped between two countries. "
            "Provide country_of_origin and country_of_destination as ISO 3166-1 alpha-2 "
            "codes (e.g. 'FR', 'US', 'DE') and a list of free-form product descriptions. "
            "Returns 1-3 suggested tariff codes per product with confidence levels."
        ),
        meta={"tags": ["shared"]},
    )
    @log_tool("tariff_suggest")
    def tariff_suggest(
        country_of_origin: str,
        country_of_destination: str,
        products: list[str],
    ) -> Dict[str, Any]:
        return suggest_tariff_codes(
            country_of_origin=country_of_origin,
            country_of_destination=country_of_destination,
            products=products,
        )
