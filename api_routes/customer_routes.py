"""API routes – customer list and detail."""

from api_routes._common import _json, _cors_preflight
from db import dict_rows
from services import db_conn, customer_service
from utils import ui_href


def register(mcp):
    """Register customer routes."""

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
