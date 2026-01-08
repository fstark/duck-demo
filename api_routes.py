"""REST API route definitions - thin wrappers around business logic services."""

import base64
from typing import Any, Dict, Optional

from starlette.responses import JSONResponse, Response

from db import dict_rows
from services import (
    db_conn,
    simulation_service,
    customer_service,
    catalog_service,
    inventory_service,
    pricing_service,
    sales_service,
    logistics_service,
    production_service,
    recipe_service,
    messaging_service,
)
from utils import ui_href


DEMO_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "*",
}


def _json(data: Any, status_code: int = 200) -> JSONResponse:
    """Return JSON response with CORS headers."""
    return JSONResponse(data, status_code=status_code, headers=DEMO_CORS_HEADERS)


def _cors_preflight(methods: list) -> Response:
    """Handle CORS preflight requests."""
    headers = dict(DEMO_CORS_HEADERS)
    headers["Access-Control-Allow-Methods"] = ", ".join(methods)
    return Response(status_code=204, headers=headers)


def _parse_bool(val: Optional[str]) -> bool:
    """Parse boolean from query string."""
    if val is None:
        return False
    return val.lower() in {"1", "true", "yes", "y", "on"}


def register_routes(mcp):
    """Register all REST API routes with the FastMCP instance."""
    
    @mcp.custom_route("/api/health", methods=["GET", "OPTIONS"])
    async def api_health(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        return _json({"status": "ok"})
    
    @mcp.custom_route("/api/simulation/time", methods=["GET", "OPTIONS"])
    async def api_simulation_time(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        try:
            result = {"current_time": simulation_service.get_current_time()}
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=500)
    
    @mcp.custom_route("/api/customers", methods=["GET", "OPTIONS"])
    async def api_customers(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        limit = int(qp.get("limit", 20))
        result = customer_service.find_customers(
            name=qp.get("name"),
            email=qp.get("email"),
            company=qp.get("company"),
            city=qp.get("city"),
            limit=limit,
        )
        return _json(result)
    
    @mcp.custom_route("/api/customers/{customer_id}", methods=["GET", "OPTIONS"])
    async def api_customer_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        customer_id = request.path_params.get("customer_id")
        with db_conn() as conn:
            customer_row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if not customer_row:
                return _json({"error": "Customer not found"}, status_code=404)
            customer = dict(customer_row)
            customer["ui_url"] = ui_href("customers", customer_id)
            orders_query = "SELECT id as sales_order_id, status, created_at, requested_delivery_date FROM sales_orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT 50"
            orders = dict_rows(conn.execute(orders_query, (customer_id,)).fetchall())
            customer["sales_orders"] = orders
            shipments_query = "SELECT DISTINCT s.id, s.status, s.planned_departure, s.planned_arrival, sos.sales_order_id FROM shipments s JOIN sales_order_shipments sos ON s.id = sos.shipment_id JOIN sales_orders so ON sos.sales_order_id = so.id WHERE so.customer_id = ? ORDER BY s.planned_departure DESC LIMIT 50"
            shipments = dict_rows(conn.execute(shipments_query, (customer_id,)).fetchall())
            customer["shipments"] = shipments
            return _json(customer)
    
    @mcp.custom_route("/api/items", methods=["GET", "OPTIONS"])
    async def api_items(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        limit = int(qp.get("limit", 50))
        in_stock_only = _parse_bool(qp.get("in_stock_only"))
        result = catalog_service.list_items(in_stock_only=in_stock_only, limit=limit)
        return _json(result)
    
    @mcp.custom_route("/api/items/{sku}", methods=["GET", "OPTIONS"])
    async def api_item_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        sku = request.path_params.get("sku")
        with db_conn() as conn:
            item = catalog_service.load_item(sku)
            if not item:
                return _json({"error": "Item not found"}, status_code=404)
            result = dict(item)
            result["ui_url"] = ui_href("items", sku)
            if result.get("image"):
                result["image_url"] = f"/api/items/{sku}/image"
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
    
    @mcp.custom_route("/api/items/{sku}/image", methods=["GET", "OPTIONS"])
    async def api_item_image(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        sku = request.path_params.get("sku")
        with db_conn() as conn:
            row = conn.execute("SELECT image FROM items WHERE sku = ?", (sku,)).fetchone()
            if not row or not row["image"]:
                return _json({"error": "Image not found"}, status_code=404)
            return Response(content=row["image"], media_type="image/png", headers=DEMO_CORS_HEADERS)
    
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
    
    @mcp.custom_route("/api/sales-orders", methods=["GET", "OPTIONS"])
    async def api_sales_orders(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        limit = int(qp.get("limit", 20))
        result = sales_service.search_orders(
            customer_id=qp.get("customer_id"),
            limit=limit,
            sort=qp.get("sort", "most_recent"),
        )
        return _json(result)
    
    @mcp.custom_route("/api/sales-orders/{order_id}", methods=["GET", "OPTIONS"])
    async def api_sales_order_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        order_id = request.path_params.get("order_id")
        detail = sales_service.get_order_details(order_id)
        if not detail:
            return _json({"error": "Not found"}, status_code=404)
        return _json(detail)
    
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
    
    @mcp.custom_route("/api/production-orders", methods=["GET", "OPTIONS"])
    async def api_production_orders(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        limit = int(qp.get("limit", 100))
        with db_conn() as conn:
            query = "SELECT po.*, i.name as item_name, i.sku as item_sku, i.type as item_type FROM production_orders po LEFT JOIN items i ON po.item_id = i.id ORDER BY po.eta_finish DESC LIMIT ?"
            rows = dict_rows(conn.execute(query, (limit,)).fetchall())
            for row in rows:
                row["ui_url"] = ui_href("production", row["id"])
        return _json({"production_orders": rows})
    
    @mcp.custom_route("/api/production-orders/{production_id}", methods=["GET", "OPTIONS"])
    async def api_production(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        production_id = request.path_params.get("production_id")
        try:
            result = production_service.get_order_status(production_id)
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=404)
    
    @mcp.custom_route("/api/quotes", methods=["GET", "OPTIONS"])
    async def api_quotes(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
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
            need_by=qp.get("need_by"),
            allowed_subs=allowed_subs,
        )
        return _json(result)
    
    @mcp.custom_route("/api/recipes", methods=["GET", "OPTIONS"])
    async def api_recipes(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        output_item_sku = qp.get("output_item_sku")
        limit = int(qp.get("limit", 50))
        result = recipe_service.list_recipes(output_item_sku=output_item_sku, limit=limit)
        return _json(result)
    
    @mcp.custom_route("/api/recipes/{recipe_id}", methods=["GET", "OPTIONS"])
    async def api_recipe_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        recipe_id = request.path_params.get("recipe_id")
        try:
            result = recipe_service.get_recipe(recipe_id)
            return _json(result)
        except ValueError as exc:
            return _json({"error": str(exc)}, status_code=404)
    
    @mcp.custom_route("/api/suppliers", methods=["GET", "OPTIONS"])
    async def api_suppliers(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        limit = int(qp.get("limit", 50))
        with db_conn() as conn:
            rows = dict_rows(conn.execute("SELECT * FROM suppliers ORDER BY name LIMIT ?", (limit,)))
            return _json({"suppliers": rows})
    
    @mcp.custom_route("/api/suppliers/{supplier_id}", methods=["GET", "OPTIONS"])
    async def api_supplier_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
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
    
    @mcp.custom_route("/api/purchase-orders", methods=["GET", "OPTIONS"])
    async def api_purchase_orders(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
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
    async def api_purchase_order_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        po_id = request.path_params.get("po_id")
        with db_conn() as conn:
            po = conn.execute(
                "SELECT po.*, s.name as supplier_name, s.contact_email, i.sku as item_sku, i.name as item_name, i.type as item_type, i.uom FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.id JOIN items i ON po.item_id = i.id WHERE po.id = ?",
                (po_id,)
            ).fetchone()
            if not po:
                return _json({"error": "Purchase order not found"}, status_code=404)
            return _json(dict(po))
    
    @mcp.custom_route("/api/emails", methods=["GET", "OPTIONS"])
    async def api_emails(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        limit = int(qp.get("limit", 20))
        result = messaging_service.list_emails(
            customer_id=qp.get("customer_id"),
            sales_order_id=qp.get("sales_order_id"),
            status=qp.get("status"),
            limit=limit
        )
        return _json(result)
    
    @mcp.custom_route("/api/emails/{email_id}", methods=["GET", "OPTIONS"])
    async def api_email_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        email_id = request.path_params.get("email_id")
        try:
            result = messaging_service.get_email(email_id)
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=404)
