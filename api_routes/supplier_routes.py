"""API routes – suppliers."""

from api_routes._common import _json, cors_handler
from db import dict_rows
from services import db_conn


def register(mcp):
    """Register supplier routes."""

    @mcp.custom_route("/api/suppliers", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_suppliers(request):
        qp = request.query_params
        limit = int(qp.get("limit", 50))
        with db_conn() as conn:
            rows = dict_rows(conn.execute("SELECT * FROM suppliers ORDER BY name LIMIT ?", (limit,)))
            return _json({"suppliers": rows})

    @mcp.custom_route("/api/suppliers/{supplier_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_supplier_detail(request):
        supplier_id = request.path_params.get("supplier_id")
        with db_conn() as conn:
            supplier = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
            if not supplier:
                return _json({"error": "Supplier not found"}, status_code=404)
            result = dict(supplier)
            po_rows = dict_rows(conn.execute(
                "SELECT po.*, i.sku as item_sku, i.name as item_name FROM purchase_orders po JOIN items i ON po.item_id = i.id WHERE po.supplier_id = ? ORDER BY po.expected_delivery DESC LIMIT 100",
                (supplier_id,)
            ))
            result["purchase_orders"] = po_rows
            return _json(result)
