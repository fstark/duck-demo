"""API routes – purchase orders."""

from api_routes._common import _json, cors_handler
from db import dict_rows
from services import db_conn


def register(mcp):
    """Register purchase order routes."""

    @mcp.custom_route("/api/purchase-orders", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_purchase_orders(request):
        qp = request.query_params
        limit = int(qp.get("limit", 100))
        status = qp.get("status")
        with db_conn() as conn:
            if status:
                rows = dict_rows(conn.execute(
                    "SELECT po.*, s.name as supplier_name, i.sku as item_sku, i.name as item_name FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.id JOIN items i ON po.item_id = i.id WHERE po.status = ? ORDER BY po.expected_delivery DESC LIMIT ?",
                    (status, limit)
                ))
            else:
                rows = dict_rows(conn.execute(
                    "SELECT po.*, s.name as supplier_name, i.sku as item_sku, i.name as item_name FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.id JOIN items i ON po.item_id = i.id ORDER BY po.expected_delivery DESC LIMIT ?",
                    (limit,)
                ))
            return _json({"purchase_orders": rows})

    @mcp.custom_route("/api/purchase-orders/{po_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_purchase_order_detail(request):
        po_id = request.path_params.get("po_id")
        with db_conn() as conn:
            po = conn.execute(
                "SELECT po.*, s.name as supplier_name, s.contact_email, i.sku as item_sku, i.name as item_name, i.type as item_type, i.uom FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.id JOIN items i ON po.item_id = i.id WHERE po.id = ?",
                (po_id,)
            ).fetchone()
            if not po:
                return _json({"error": "Purchase order not found"}, status_code=404)
            return _json(dict(po))
