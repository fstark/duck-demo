"""API routes – aggregated dashboard payload."""

from api_routes._common import _json, cors_handler
from services._base import db_conn
from services import activity_service


def register(mcp):
    """Register dashboard routes."""

    @mcp.custom_route("/api/dashboard", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_dashboard(request):
        with db_conn() as conn:
            # ------ Status distributions ----------------------------------
            status_distributions = {}
            for table, key in [
                ("sales_orders", "sales_orders"),
                ("production_orders", "production_orders"),
                ("quotes", "quotes"),
                ("invoices", "invoices"),
                ("shipments", "shipments"),
            ]:
                rows = conn.execute(
                    f"SELECT status, COUNT(*) as count FROM {table} GROUP BY status ORDER BY count DESC"
                ).fetchall()
                status_distributions[key] = [dict(r) for r in rows]

            # ------ KPIs --------------------------------------------------
            open_orders = conn.execute(
                "SELECT COUNT(*) FROM sales_orders WHERE status IN ('confirmed', 'draft')"
            ).fetchone()[0]
            in_progress_mos = conn.execute(
                "SELECT COUNT(*) FROM production_orders WHERE status IN ('ready', 'in_progress')"
            ).fetchone()[0]
            pending_shipments = conn.execute(
                "SELECT COUNT(*) FROM shipments WHERE status IN ('planned', 'in_transit')"
            ).fetchone()[0]
            overdue_invoices = conn.execute(
                "SELECT COUNT(*) FROM invoices WHERE status = 'overdue'"
            ).fetchone()[0]
            total_revenue = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments"
            ).fetchone()[0]

            kpis = {
                "open_orders": open_orders,
                "in_progress_mos": in_progress_mos,
                "pending_shipments": pending_shipments,
                "overdue_invoices": overdue_invoices,
                "total_revenue": total_revenue,
            }

        # ------ Recent activity (last 20) ---------------------------------
        recent = activity_service.get_log(limit=20)

        # ------ Daily volumes (from activity_log summary) -----------------
        summary_rows = activity_service.get_daily_summary()
        # Pivot into {date: {created, shipped, invoiced}}
        daily_map: dict = {}
        for row in summary_rows:
            d = row["date"]
            if d not in daily_map:
                daily_map[d] = {"date": d, "created": 0, "shipped": 0, "invoiced": 0}
            action = row["action"]
            count = row["count"]
            if action in ("sales_order.created", "sales_order.confirmed"):
                daily_map[d]["created"] += count
            elif action in ("shipment.dispatched", "shipment.delivered"):
                daily_map[d]["shipped"] += count
            elif action in ("invoice.issued",):
                daily_map[d]["invoiced"] += count
        daily_volumes = sorted(daily_map.values(), key=lambda x: x["date"])

        return _json({
            "status_distributions": status_distributions,
            "kpis": kpis,
            "recent_activity": recent["entries"],
            "daily_volumes": daily_volumes,
        })
