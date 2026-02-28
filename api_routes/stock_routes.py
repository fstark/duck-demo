"""API routes – stock list and detail."""

from api_routes._common import _json, _cors_preflight
from db import dict_rows
from services import db_conn
from utils import ui_href


def register(mcp):
    """Register stock routes."""

    @mcp.custom_route("/api/stock", methods=["GET", "OPTIONS"])
    async def api_stock(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        limit = int(qp.get("limit", 200))
        with db_conn() as conn:
            query = "SELECT s.id, s.item_id, i.sku as item_sku, i.name as item_name, i.type as item_type, s.warehouse, s.location, s.on_hand FROM stock s JOIN items i ON s.item_id = i.id ORDER BY s.warehouse, s.location LIMIT ?"
            rows = dict_rows(conn.execute(query, (limit,)).fetchall())
            for row in rows:
                row["ui_url"] = ui_href("stock", row["id"])
            return _json({"stock": rows})

    @mcp.custom_route("/api/stock/{stock_id}", methods=["GET", "OPTIONS"])
    async def api_stock_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        stock_id = request.path_params.get("stock_id")
        with db_conn() as conn:
            query = "SELECT s.id, s.item_id, i.sku as item_sku, i.name as item_name, i.type as item_type, s.warehouse, s.location, s.on_hand FROM stock s JOIN items i ON s.item_id = i.id WHERE s.id = ?"
            row = conn.execute(query, (stock_id,)).fetchone()
            if not row:
                return _json({"error": "Stock record not found"}, status_code=404)
            return _json(dict(row))
