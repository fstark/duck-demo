"""API routes – health, simulation time, chart images, stats spotlight."""

import os
from datetime import datetime, timedelta

from starlette.responses import FileResponse

from api_routes._common import _json, _cors_preflight, DEMO_CORS_HEADERS
from db import dict_rows
from services import db_conn, simulation_service


def register(mcp):
    """Register system/shared routes."""

    @mcp.custom_route("/api/health", methods=["GET", "OPTIONS"])
    async def api_health(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        return _json({"status": "ok"})

    @mcp.custom_route("/api/mcp-app-ui/customer-confirm", methods=["GET", "OPTIONS"])
    async def api_mcp_app_test(request):
        """Test endpoint to manually access the MCP App UI for debugging."""
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        ui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp_apps_ui", "customer-confirm.html")
        if os.path.exists(ui_path):
            with open(ui_path, "r", encoding="utf-8") as f:
                from starlette.responses import HTMLResponse
                return HTMLResponse(f.read(), headers=DEMO_CORS_HEADERS)
        else:
            return _json({"error": "MCP App UI not found"}, status_code=404)

    @mcp.custom_route("/api/simulation/time", methods=["GET", "OPTIONS"])
    async def api_simulation_time(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        try:
            result = {"current_time": simulation_service.get_current_time()}
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/charts/{filename}", methods=["GET", "OPTIONS"])
    async def api_chart_image(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        filename = request.path_params.get("filename")
        charts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp", "charts")
        file_path = os.path.join(charts_dir, filename)

        if not os.path.exists(file_path):
            return _json({"error": "Chart not found"}, status_code=404)

        return FileResponse(
            file_path,
            media_type="image/png",
            headers=DEMO_CORS_HEADERS
        )

    @mcp.custom_route("/api/stats/spotlight", methods=["GET", "OPTIONS"])
    async def api_stats_spotlight(request):
        """Return spotlight items for each overview card."""
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])

        with db_conn() as conn:
            now = simulation_service.get_current_time()
            now_dt = datetime.fromisoformat(now.replace('Z', '+00:00').replace(' ', 'T').split('+')[0])

            def relative_time(dt_str: str) -> str:
                """Convert datetime string to relative time like '2h ago', 'yesterday'."""
                if not dt_str:
                    return ""
                try:
                    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00').replace(' ', 'T').split('+')[0])
                    diff = now_dt - dt
                    if diff.days < 0:
                        return "future"
                    if diff.days == 0:
                        hours = diff.seconds // 3600
                        if hours < 1:
                            return "just now"
                        return f"{hours}h ago"
                    if diff.days == 1:
                        return "yesterday"
                    if diff.days < 7:
                        return f"{diff.days}d ago"
                    return f"{diff.days // 7}w ago"
                except:
                    return ""

            def days_until(dt_str: str) -> str:
                """Convert datetime string to 'in Xd' or 'today' or 'overdue'."""
                if not dt_str:
                    return ""
                try:
                    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00').replace(' ', 'T').split('+')[0])
                    diff = dt - now_dt
                    days = diff.days
                    if days < 0:
                        return "overdue"
                    if days == 0:
                        return "today"
                    if days == 1:
                        return "tomorrow"
                    return f"in {days}d"
                except:
                    return ""

            result = {}

            # CUSTOMERS
            customers_sql = """
                SELECT c.id, c.name, MAX(activity) as last_activity
                FROM customers c
                LEFT JOIN (
                    SELECT id as customer_id, created_at as activity FROM customers
                    UNION ALL
                    SELECT customer_id, MAX(created_at) as activity FROM sales_orders GROUP BY customer_id
                    UNION ALL
                    SELECT customer_id, MAX(created_at) as activity FROM quotes GROUP BY customer_id
                    UNION ALL
                    SELECT customer_id, MAX(modified_at) as activity FROM emails GROUP BY customer_id
                    UNION ALL
                    SELECT customer_id, MAX(created_at) as activity FROM invoices GROUP BY customer_id
                ) sub ON c.id = sub.customer_id
                GROUP BY c.id
                ORDER BY last_activity DESC NULLS LAST
                LIMIT 3
            """
            rows = conn.execute(customers_sql).fetchall()
            result["customers"] = [
                {"label": r["name"], "sublabel": relative_time(r["last_activity"]), "href": f"#/customers/{r['id']}"}
                for r in rows
            ]

            # QUOTES
            quotes = []
            newest_quote = conn.execute("""
                SELECT id, created_at FROM quotes
                WHERE status IN ('draft', 'sent')
                ORDER BY created_at DESC LIMIT 1
            """).fetchone()
            if newest_quote:
                quotes.append({"label": newest_quote["id"], "sublabel": "newest", "href": f"#/quotes/{newest_quote['id']}"})

            expiring_quote = conn.execute("""
                SELECT id, valid_until FROM quotes
                WHERE status = 'sent' AND valid_until >= ?
                ORDER BY valid_until ASC LIMIT 1
            """, (now[:10],)).fetchone()
            if expiring_quote and (not newest_quote or expiring_quote["id"] != newest_quote["id"]):
                quotes.append({"label": expiring_quote["id"], "sublabel": f"expires {days_until(expiring_quote['valid_until'])}", "href": f"#/quotes/{expiring_quote['id']}"})
            result["quotes"] = quotes

            # SALES ORDERS
            orders = []
            largest_order = conn.execute("""
                SELECT so.id, SUM(sol.qty * i.unit_price) as total
                FROM sales_orders so
                JOIN sales_order_lines sol ON so.id = sol.sales_order_id
                JOIN items i ON sol.item_id = i.id
                WHERE so.status NOT IN ('completed', 'cancelled')
                GROUP BY so.id
                ORDER BY total DESC LIMIT 1
            """).fetchone()
            if largest_order:
                total = largest_order["total"] or 0
                orders.append({"label": largest_order["id"], "sublabel": f"€{total:,.0f}", "href": f"#/orders/{largest_order['id']}"})

            urgent_order = conn.execute("""
                SELECT id, requested_delivery_date FROM sales_orders
                WHERE status NOT IN ('completed', 'cancelled') AND requested_delivery_date >= ?
                ORDER BY requested_delivery_date ASC LIMIT 1
            """, (now[:10],)).fetchone()
            if urgent_order and (not largest_order or urgent_order["id"] != largest_order["id"]):
                orders.append({"label": urgent_order["id"], "sublabel": f"due {days_until(urgent_order['requested_delivery_date'])}", "href": f"#/orders/{urgent_order['id']}"})
            result["sales_orders"] = orders

            # SHIPMENTS
            shipments = []
            pending_ship = conn.execute("""
                SELECT id FROM shipments WHERE status = 'pending' ORDER BY planned_departure ASC LIMIT 1
            """).fetchone()
            if pending_ship:
                shipments.append({"label": pending_ship["id"], "sublabel": "pending", "href": f"#/shipments/{pending_ship['id']}"})

            in_transit_ship = conn.execute("""
                SELECT id FROM shipments WHERE status = 'in_transit' ORDER BY planned_arrival ASC LIMIT 1
            """).fetchone()
            if in_transit_ship:
                shipments.append({"label": in_transit_ship["id"], "sublabel": "in transit", "href": f"#/shipments/{in_transit_ship['id']}"})
            result["shipments"] = shipments

            # INVOICES
            invoices = []
            overdue_inv = conn.execute("""
                SELECT id FROM invoices WHERE status = 'overdue' ORDER BY due_date ASC LIMIT 1
            """).fetchone()
            if overdue_inv:
                invoices.append({"label": overdue_inv["id"], "sublabel": "overdue", "href": f"#/invoices/{overdue_inv['id']}"})

            due_soon_inv = conn.execute("""
                SELECT id, due_date FROM invoices
                WHERE status = 'issued' AND due_date >= ?
                ORDER BY due_date ASC LIMIT 1
            """, (now[:10],)).fetchone()
            if due_soon_inv and (not overdue_inv or due_soon_inv["id"] != overdue_inv["id"]):
                invoices.append({"label": due_soon_inv["id"], "sublabel": f"due {days_until(due_soon_inv['due_date'])}", "href": f"#/invoices/{due_soon_inv['id']}"})
            result["invoices"] = invoices

            # EMAILS
            draft_emails = conn.execute("""
                SELECT id, subject, recipient_name FROM emails
                WHERE status = 'draft'
                ORDER BY modified_at DESC LIMIT 2
            """).fetchall()
            result["emails"] = [
                {"label": r["subject"][:25] + ("..." if len(r["subject"]) > 25 else ""), "sublabel": r["recipient_name"].split()[0] if r["recipient_name"] else "", "href": f"#/emails/{r['id']}"}
                for r in draft_emails
            ]

            # STOCK
            low_stock = conn.execute("""
                SELECT i.name, SUM(s.on_hand) as total_qty
                FROM stock s
                JOIN items i ON s.item_id = i.id
                WHERE i.type = 'finished_good'
                GROUP BY s.item_id
                ORDER BY total_qty ASC
                LIMIT 3
            """).fetchall()
            result["stock"] = [
                {"label": r["name"].replace(" Duck ", " ").replace("cm", ""), "sublabel": f"{int(r['total_qty'])} qty", "href": f"#/stock"}
                for r in low_stock
            ]

            # PRODUCTION ORDERS
            production = []
            in_progress_po = conn.execute("""
                SELECT id FROM production_orders WHERE status = 'in_progress' ORDER BY started_at DESC LIMIT 1
            """).fetchone()
            if in_progress_po:
                production.append({"label": in_progress_po["id"], "sublabel": "in progress", "href": f"#/production/{in_progress_po['id']}"})

            planned_po = conn.execute("""
                SELECT id FROM production_orders WHERE status = 'planned' ORDER BY eta_finish ASC LIMIT 1
            """).fetchone()
            if planned_po:
                production.append({"label": planned_po["id"], "sublabel": "planned", "href": f"#/production/{planned_po['id']}"})
            result["production_orders"] = production

            # PURCHASE ORDERS
            purchase_orders = []
            ordered_po = conn.execute("""
                SELECT id FROM purchase_orders WHERE status = 'ordered' ORDER BY expected_delivery ASC LIMIT 1
            """).fetchone()
            if ordered_po:
                purchase_orders.append({"label": ordered_po["id"], "sublabel": "ordered", "href": f"#/purchase-orders/{ordered_po['id']}"})

            received_po = conn.execute("""
                SELECT id FROM purchase_orders WHERE status = 'received' ORDER BY received_at DESC LIMIT 1
            """).fetchone()
            if received_po:
                purchase_orders.append({"label": received_po["id"], "sublabel": "received", "href": f"#/purchase-orders/{received_po['id']}"})
            result["purchase_orders"] = purchase_orders

            return _json(result)
