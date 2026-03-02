"""MCP tools – work center capacity and utilization."""

from typing import Any, Dict, List

from mcp_tools._common import log_tool
from services import db_conn
from db import dict_rows


def register(mcp):
    """Register work center tools."""

    @mcp.tool(name="work_center_list", meta={"tags": ["production"]})
    @log_tool("work_center_list")
    def list_work_centers() -> Dict[str, Any]:
        """
        List all work centers with current capacity utilization.
        Shows which work centers are bottlenecks and their queue depth.

        Returns:
            Dictionary with work_centers array showing capacity, utilization, and queue lengths
        """
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
                wc["utilization_percent"] = round(usage["in_progress"] / wc["max_concurrent"] * 100, 1) if wc["max_concurrent"] > 0 else 0
                wc["is_bottleneck"] = usage["in_progress"] >= wc["max_concurrent"]
                wc["available_capacity"] = max(0, wc["max_concurrent"] - usage["in_progress"])
            
        return {
            "work_centers": work_centers,
            "summary": {
                "total_work_centers": len(work_centers),
                "bottlenecked_count": sum(1 for wc in work_centers if wc["is_bottleneck"]),
                "total_pending": sum(wc["pending"] for wc in work_centers),
                "total_in_progress": sum(wc["in_progress"] for wc in work_centers),
            }
        }

    @mcp.tool(name="work_center_get_status", meta={"tags": ["production"]})
    @log_tool("work_center_get_status")
    def get_work_center_status(work_center_name: str) -> Dict[str, Any]:
        """
        Get detailed status of a specific work center including its operation queue.
        Use this to diagnose production bottlenecks and plan capacity.

        Parameters:
            work_center_name: The work center name (e.g., 'MOLDING', 'PAINTING', 'ASSEMBLY')

        Returns:
            Work center details with in-progress operations, pending queue, and recent completions
        """
        with db_conn() as conn:
            # Get work center
            wc_query = "SELECT id, name, max_concurrent, description FROM work_centers WHERE name = ?"
            wc = conn.execute(wc_query, (work_center_name,)).fetchone()
            if not wc:
                return {"error": f"Work center '{work_center_name}' not found"}
            
            wc_dict = dict(wc)
            
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
                LIMIT 100
            """
            operations = dict_rows(conn.execute(ops_query, (work_center_name,)).fetchall())
            
            # Separate by status
            in_progress = [op for op in operations if op["status"] == "in_progress"]
            pending = [op for op in operations if op["status"] == "pending"]
            completed = [op for op in operations if op["status"] == "completed"][:10]  # Only recent
            
            # Calculate statistics
            wc_dict["in_progress_count"] = len(in_progress)
            wc_dict["pending_count"] = len(pending)
            wc_dict["completed_count"] = len(completed)
            wc_dict["utilization_percent"] = round(len(in_progress) / wc_dict["max_concurrent"] * 100, 1) if wc_dict["max_concurrent"] > 0 else 0
            wc_dict["is_bottleneck"] = len(in_progress) >= wc_dict["max_concurrent"]
            wc_dict["available_capacity"] = max(0, wc_dict["max_concurrent"] - len(in_progress))
            
            wc_dict["in_progress_operations"] = in_progress
            wc_dict["pending_operations"] = pending[:20]  # Limit queue display
            wc_dict["recent_completions"] = completed
            
        return wc_dict

    @mcp.tool(name="work_center_get_bottlenecks", meta={"tags": ["production"]})
    @log_tool("work_center_get_bottlenecks")
    def identify_bottlenecks() -> Dict[str, Any]:
        """
        Identify production bottlenecks by analyzing work center utilization and queue depth.
        Returns work centers at or over capacity with their pending operation counts.

        Returns:
            List of bottlenecked work centers sorted by severity (queue length)
        """
        with db_conn() as conn:
            # Get work centers with their utilization
            query = """
                SELECT 
                    wc.name,
                    wc.max_concurrent,
                    wc.description,
                    COUNT(CASE WHEN pop.status = 'in_progress' THEN 1 END) as in_progress,
                    COUNT(CASE WHEN pop.status = 'pending' THEN 1 END) as pending
                FROM work_centers wc
                LEFT JOIN production_operations pop ON wc.name = pop.work_center
                GROUP BY wc.id, wc.name, wc.max_concurrent, wc.description
                HAVING in_progress >= wc.max_concurrent
                ORDER BY pending DESC, in_progress DESC
            """
            bottlenecks = dict_rows(conn.execute(query).fetchall())
            
            for bn in bottlenecks:
                bn["utilization_percent"] = round(bn["in_progress"] / bn["max_concurrent"] * 100, 1) if bn["max_concurrent"] > 0 else 0
                bn["severity"] = "critical" if bn["pending"] > 50 else "high" if bn["pending"] > 20 else "moderate"
            
        return {
            "bottlenecks": bottlenecks,
            "summary": {
                "bottleneck_count": len(bottlenecks),
                "total_queue_depth": sum(bn["pending"] for bn in bottlenecks),
                "critical_count": sum(1 for bn in bottlenecks if bn["severity"] == "critical"),
            }
        }
