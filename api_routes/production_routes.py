"""API routes – production orders."""

from api_routes._common import _json, cors_handler
from db import dict_rows
from services import db_conn, production_service
from utils import ui_href


def register(mcp):
    """Register production routes."""

    @mcp.custom_route("/api/production-orders", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_production_orders(request):
        qp = request.query_params
        limit = int(qp.get("limit", 100))
        with db_conn() as conn:
            query = "SELECT po.*, i.name as item_name, i.sku as item_sku, i.type as item_type FROM production_orders po LEFT JOIN items i ON po.item_id = i.id ORDER BY po.eta_finish DESC LIMIT ?"
            rows = dict_rows(conn.execute(query, (limit,)).fetchall())
            for row in rows:
                row["ui_url"] = ui_href("production", row["id"])
        return _json({"production_orders": rows})

    @mcp.custom_route("/api/production-orders/{production_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_production(request):
        production_id = request.path_params.get("production_id")
        try:
            result = production_service.get_order_status(production_id)
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=404)
