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
        sales_order_id = qp.get("sales_order_id")
        with db_conn() as conn:
            if sales_order_id:
                query = "SELECT po.*, i.name as item_name, i.sku as item_sku, i.type as item_type FROM production_orders po LEFT JOIN items i ON po.item_id = i.id WHERE po.sales_order_id = ? ORDER BY po.eta_finish DESC LIMIT ?"
                rows = dict_rows(conn.execute(query, (sales_order_id, limit)).fetchall())
            else:
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

    @mcp.custom_route("/api/work-centers", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_work_centers(request):
        """List all work centers with current usage statistics."""
        with db_conn() as conn:
            # Get work centers
            wc_query = "SELECT id, name, max_concurrent, description FROM work_centers ORDER BY name"
            work_centers = dict_rows(conn.execute(wc_query).fetchall())
            
            # Get current usage per work center
            usage_query = """
                SELECT work_center, status, COUNT(*) as count
                FROM production_operations
                WHERE work_center IS NOT NULL
                GROUP BY work_center, status
            """
            usage_rows = dict_rows(conn.execute(usage_query).fetchall())
            
            # Build usage map
            usage_map = {}
            for row in usage_rows:
                wc = row["work_center"]
                if wc not in usage_map:
                    usage_map[wc] = {"pending": 0, "in_progress": 0, "completed": 0}
                usage_map[wc][row["status"]] = row["count"]
            
            # Enrich work centers with usage
            for wc in work_centers:
                wc_name = wc["name"]
                usage = usage_map.get(wc_name, {"pending": 0, "in_progress": 0, "completed": 0})
                wc["in_progress"] = usage["in_progress"]
                wc["pending"] = usage["pending"]
                wc["completed"] = usage["completed"]
                wc["utilization"] = round(usage["in_progress"] / wc["max_concurrent"] * 100, 1) if wc["max_concurrent"] > 0 else 0
                wc["ui_url"] = ui_href("work-centers", wc["id"])
            
        return _json({"work_centers": work_centers})

    @mcp.custom_route("/api/work-centers/{work_center_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_work_center_detail(request):
        """Get detailed information about a specific work center."""
        work_center_id = request.path_params.get("work_center_id")
        with db_conn() as conn:
            # Get work center
            wc_query = "SELECT id, name, max_concurrent, description FROM work_centers WHERE id = ?"
            wc = conn.execute(wc_query, (work_center_id,)).fetchone()
            if not wc:
                return _json({"error": "Work center not found"}, status_code=404)
            
            wc_dict = dict(wc)
            wc_name = wc_dict["name"]
            
            # Get operations for this work center
            ops_query = """
                SELECT 
                    pop.id, pop.production_order_id, pop.operation_name, 
                    pop.duration_hours, pop.status, pop.started_at, pop.completed_at,
                    po.item_id, i.name as item_name, i.sku as item_sku
                FROM production_operations pop
                JOIN production_orders po ON pop.production_order_id = po.id
                LEFT JOIN items i ON po.item_id = i.id
                WHERE pop.work_center = ?
                ORDER BY 
                    CASE pop.status 
                        WHEN 'in_progress' THEN 1 
                        WHEN 'pending' THEN 2 
                        ELSE 3 
                    END,
                    pop.started_at DESC,
                    pop.production_order_id
                LIMIT 200
            """
            operations = dict_rows(conn.execute(ops_query, (wc_name,)).fetchall())
            
            # Add UI URLs to operations
            for op in operations:
                op["production_order_ui_url"] = ui_href("production", op["production_order_id"])
            
            # Calculate statistics
            in_progress = sum(1 for op in operations if op["status"] == "in_progress")
            pending = sum(1 for op in operations if op["status"] == "pending")
            completed = sum(1 for op in operations if op["status"] == "completed")
            
            wc_dict["operations"] = operations
            wc_dict["in_progress"] = in_progress
            wc_dict["pending"] = pending
            wc_dict["completed"] = completed
            wc_dict["utilization"] = round(in_progress / wc_dict["max_concurrent"] * 100, 1) if wc_dict["max_concurrent"] > 0 else 0
            wc_dict["ui_url"] = ui_href("work-centers", work_center_id)
            
        return _json(wc_dict)
