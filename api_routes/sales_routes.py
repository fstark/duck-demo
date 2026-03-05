"""API routes – sales orders and quote options."""

from api_routes._common import _json, cors_handler
from services import sales_service, pricing_service


def register(mcp):
    """Register sales routes."""

    @mcp.custom_route("/api/sales-orders", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_sales_orders(request):
        qp = request.query_params
        limit = int(qp.get("limit", 20))
        result = sales_service.search_orders(
            customer_ids=[qp["customer_id"]] if "customer_id" in qp else None,
            limit=limit,
            sort=qp.get("sort", "most_recent"),
        )
        return _json(result)

    @mcp.custom_route("/api/sales-orders/{order_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_sales_order_detail(request):
        order_id = request.path_params.get("order_id")
        detail = sales_service.get_order_details(order_id)
        if not detail:
            return _json({"error": "Not found"}, status_code=404)
        return _json(detail)

    @mcp.custom_route("/api/sales-orders/{order_id}/timeline", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_sales_order_timeline(request):
        order_id = request.path_params.get("order_id")
        timeline = sales_service.get_order_timeline(order_id)
        if not timeline:
            return _json({"error": "Not found"}, status_code=404)
        return _json(timeline)

    @mcp.custom_route("/api/sales-orders/{order_id}/fulfillment", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_sales_order_fulfillment(request):
        order_id = request.path_params.get("order_id")
        result = sales_service.get_fulfillment_sources(order_id)
        if not result:
            return _json({"error": "Not found"}, status_code=404)
        return _json(result)

    @mcp.custom_route("/api/sales-orders/{order_id}/supply-chain", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_sales_order_supply_chain(request):
        order_id = request.path_params.get("order_id")
        result = sales_service.get_supply_chain_trace_for_order(order_id)
        if not result:
            return _json({"error": "Not found"}, status_code=404)
        return _json(result)

    @mcp.custom_route("/api/quote-options", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_quote_options(request):
        qp = request.query_params
        sku = qp.get("sku")
        qty = qp.get("qty")
        if not sku or not qty:
            return _json({"error": "sku and qty are required"}, status_code=400)
        try:
            qty_int = int(qty)
        except ValueError:
            return _json({"error": "qty must be an integer"}, status_code=400)
        allowed_subs = []
        subs_param = qp.get("subs")
        if subs_param:
            allowed_subs = [s.strip() for s in subs_param.split(",") if s.strip()]
        result = pricing_service.calculate_quote_options(
            sku=sku,
            qty=qty_int,
            delivery_date=qp.get("delivery_date"),
            allowed_subs=allowed_subs,
        )
        return _json(result)
