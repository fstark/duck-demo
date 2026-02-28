"""API routes – shipments."""

from api_routes._common import _json, _cors_preflight
from db import dict_rows
from services import db_conn, logistics_service
from utils import ui_href


def register(mcp):
    """Register shipment routes."""

    @mcp.custom_route("/api/shipments/{shipment_id}", methods=["GET", "OPTIONS"])
    async def api_shipment(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        shipment_id = request.path_params.get("shipment_id")
        try:
            result = logistics_service.get_shipment_status(shipment_id)
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=404)

    @mcp.custom_route("/api/shipments", methods=["GET", "OPTIONS"])
    async def api_shipments(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        with db_conn() as conn:
            rows = dict_rows(conn.execute("SELECT * FROM shipments ORDER BY planned_departure DESC").fetchall())
            for row in rows:
                row["ui_url"] = ui_href("shipments", row["id"])
        return _json({"shipments": rows})
