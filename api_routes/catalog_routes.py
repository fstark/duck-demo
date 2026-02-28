"""API routes – catalog items, images, and 3D models."""

import base64
import os

from starlette.responses import FileResponse, Response

from api_routes._common import _json, _cors_preflight, DEMO_CORS_HEADERS
from services import db_conn, catalog_service, inventory_service
from utils import ui_href
import config


def register(mcp):
    """Register catalog/item routes."""

    @mcp.custom_route("/api/items", methods=["GET", "OPTIONS"])
    async def api_items(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        limit = int(qp.get("limit", 50))
        from api_routes._common import _parse_bool
        in_stock_only = _parse_bool(qp.get("in_stock_only"))
        result = catalog_service.list_items(in_stock_only=in_stock_only, limit=limit)
        return _json(result)

    @mcp.custom_route("/api/items/{sku}", methods=["GET", "OPTIONS"])
    async def api_item_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        sku = request.path_params.get("sku")
        from db import dict_rows
        with db_conn() as conn:
            item = catalog_service.load_item(sku)
            if not item:
                return _json({"error": "Item not found"}, status_code=404)
            result = dict(item)
            result["ui_url"] = ui_href("items", sku)
            if result.get("image"):
                result["image_url"] = f"{config.API_BASE}/api/items/{sku}/image.png"
            result.pop("image", None)
            stock = inventory_service.get_stock_summary(item["id"])
            result["stock"] = stock
            recipes = dict_rows(conn.execute(
                "SELECT r.*, (SELECT COUNT(*) FROM recipe_ingredients WHERE recipe_id = r.id) as ingredient_count, (SELECT COUNT(*) FROM recipe_operations WHERE recipe_id = r.id) as operation_count FROM recipes r WHERE r.output_item_id = ? ORDER BY r.id",
                (item["id"],)
            ))
            result["recipes"] = recipes
            used_in_recipes = dict_rows(conn.execute(
                "SELECT DISTINCT r.id as recipe_id, r.output_item_id, i.sku as output_sku, i.name as output_name, ri.input_qty as qty_per_batch FROM recipe_ingredients ri JOIN recipes r ON ri.recipe_id = r.id JOIN items i ON r.output_item_id = i.id WHERE ri.input_item_id = ? ORDER BY r.id",
                (item["id"],)
            ))
            result["used_in_recipes"] = used_in_recipes
            production_orders = dict_rows(conn.execute(
                "SELECT po.id, po.recipe_id, po.status, po.started_at, po.completed_at, po.eta_finish, po.eta_ship, r.output_qty FROM production_orders po JOIN recipes r ON po.recipe_id = r.id WHERE po.item_id = ? ORDER BY po.id DESC",
                (item["id"],)
            ))
            result["production_orders"] = production_orders
            purchase_orders = dict_rows(conn.execute(
                "SELECT po.id, po.qty, po.status, po.ordered_at, po.expected_delivery, po.received_at, s.id as supplier_id, s.name as supplier_name FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.id WHERE po.item_id = ? ORDER BY po.id DESC",
                (item["id"],)
            ))
            result["purchase_orders"] = purchase_orders
            return _json(result)

    @mcp.custom_route("/api/items/{sku}/image.png", methods=["GET", "OPTIONS"])
    async def api_item_image(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        sku = request.path_params.get("sku")
        with db_conn() as conn:
            row = conn.execute("SELECT image FROM items WHERE sku = ?", (sku,)).fetchone()
            if not row or not row["image"]:
                return _json({"error": "Image not found"}, status_code=404)
            return Response(content=row["image"], media_type="image/png", headers=DEMO_CORS_HEADERS)

    @mcp.custom_route("/api/models/duck.obj", methods=["GET", "OPTIONS"])
    async def api_duck_model(request):
        """Serve the duck 3D model for MCP App item inspector."""
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "public", "models", "duck.obj")
        if not os.path.exists(model_path):
            return _json({"error": "Model not found"}, status_code=404)
        return FileResponse(model_path, media_type="text/plain", headers=DEMO_CORS_HEADERS)

    @mcp.custom_route("/api/items/{sku}/image/base64", methods=["GET", "OPTIONS"])
    async def api_item_image_base64(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        sku = request.path_params.get("sku")
        with db_conn() as conn:
            row = conn.execute("SELECT image FROM items WHERE sku = ?", (sku,)).fetchone()
            if not row or not row["image"]:
                return _json({"error": "Image not found"}, status_code=404)
            b64_data = base64.b64encode(row["image"]).decode("utf-8")
            return Response(content=b64_data, media_type="text/plain", headers=DEMO_CORS_HEADERS)

    @mcp.custom_route("/api/items/{sku}/stock", methods=["GET", "OPTIONS"])
    async def api_item_stock(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        sku = request.path_params.get("sku")
        try:
            item = catalog_service.load_item(sku)
            if not item:
                return _json({"error": "Item not found"}, status_code=404)
            result = inventory_service.get_stock_summary(item["id"])
            result["ui_url"] = ui_href("items", sku)
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=404)
