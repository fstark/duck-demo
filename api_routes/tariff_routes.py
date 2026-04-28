"""API routes – tariff code suggestions."""

from starlette.requests import Request

from api_routes._common import _json, cors_handler
from services.tariff import suggest_tariff_codes


def register(mcp):
    """Register tariff routes."""

    @mcp.custom_route("/api/tariff/suggest", methods=["POST", "OPTIONS"])
    @cors_handler(["POST"])
    async def tariff_suggest(request: Request):
        body = await request.json()
        country_of_origin = body.get("country_of_origin", "")
        country_of_destination = body.get("country_of_destination", "")
        products = body.get("products", [])

        if not country_of_origin or not country_of_destination or not products:
            return _json(
                {"error": "country_of_origin, country_of_destination, and products are required"},
                status_code=400,
            )

        result = suggest_tariff_codes(
            country_of_origin=country_of_origin,
            country_of_destination=country_of_destination,
            products=products,
        )
        return _json(result)
