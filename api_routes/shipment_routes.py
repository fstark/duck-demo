"""API routes – shipments."""

from api_routes._common import _json, cors_handler
from db import dict_rows
from services import db_conn, logistics_service
from utils import ui_href


def register(mcp):
    """Register shipment routes."""

    @mcp.custom_route("/api/shipments/{shipment_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_shipment(request):
        shipment_id = request.path_params.get("shipment_id")
        try:
            result = logistics_service.get_shipment_status(shipment_id)
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=404)

    @mcp.custom_route("/api/shipments", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_shipments(request):
        with db_conn() as conn:
            rows = dict_rows(conn.execute("SELECT * FROM shipments ORDER BY planned_departure DESC").fetchall())
            for row in rows:
                row["ui_url"] = ui_href("shipments", row["id"])
        return _json({"shipments": rows})
