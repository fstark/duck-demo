"""API routes – aggregated dashboard payload."""

from api_routes._common import _json, cors_handler
from services._base import db_conn
from services import activity_service


# Status order mappings for logical workflow progression
STATUS_ORDER = {
    "sales_orders": ["draft", "confirmed", "completed", "cancelled"],
    "production_orders": ["planned", "waiting", "ready", "in_progress", "completed", "cancelled"],
    "quotes": ["draft", "sent", "accepted", "rejected", "expired"],
    "invoices": ["draft", "issued", "paid", "overdue", "cancelled"],
    "shipments": ["planned", "in_transit", "delivered", "cancelled"],
}

# Terminal statuses — objects in these states are "done"
TERMINAL_STATUSES = {
    "sales_orders":      ("completed", "cancelled"),
    "production_orders": ("completed", "cancelled"),
    "quotes":            ("accepted", "rejected", "expired"),
    "invoices":          ("paid", "cancelled"),
    "shipments":         ("delivered", "cancelled"),
}

# Best date column per entity for "when was this object active"
DATE_COLUMN = {
    "sales_orders":      "created_at",
    "production_orders": "started_at",
    "quotes":            "created_at",
    "invoices":          "created_at",
    "shipments":         "planned_departure",
}


def _sort_by_status_order(status_list, entity_type):
    """Sort status distribution by logical workflow order."""
    order = STATUS_ORDER.get(entity_type, [])
    order_map = {status: idx for idx, status in enumerate(order)}
    return sorted(status_list, key=lambda x: order_map.get(x["status"], 999))


def _status_distribution_sql(table, since, until):
    """Build SQL + params for 'active in range' status distribution.

    Active means: created/started during the range, OR already existed
    and still open (non-terminal) at range start.
    """
    if not since or not until:
        return f"SELECT status, COUNT(*) as count FROM {table} GROUP BY status", []

    date_col = DATE_COLUMN[table]
    terminals = TERMINAL_STATUSES[table]
    placeholders = ",".join("?" * len(terminals))

    if date_col == "started_at":
        # production_orders: started_at can be NULL for planned/waiting
        sql = (
            f"SELECT status, COUNT(*) as count FROM {table} "
            f"WHERE ({date_col} >= ? AND {date_col} <= ?) "
            f"   OR ({date_col} < ? AND status NOT IN ({placeholders})) "
            f"   OR ({date_col} IS NULL AND status NOT IN ({placeholders})) "
            f"GROUP BY status"
        )
        params = [since, until, since, *terminals, *terminals]
    else:
        sql = (
            f"SELECT status, COUNT(*) as count FROM {table} "
            f"WHERE ({date_col} >= ? AND {date_col} <= ?) "
            f"   OR ({date_col} < ? AND status NOT IN ({placeholders})) "
            f"GROUP BY status"
        )
        params = [since, until, since, *terminals]
    return sql, params


def register(mcp):
    """Register dashboard routes."""

    @mcp.custom_route("/api/dashboard", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_dashboard(request):
        qp = request.query_params
        since = qp.get("since")
        until = qp.get("until")
        # Ensure 'until' covers the full day when given as YYYY-MM-DD
        if until and len(until) == 10:
            until = until + " 23:59:59"

        with db_conn() as conn:
            # ------ Status distributions (time-filtered: active in range) -
            status_distributions = {}
            for table, key in [
                ("sales_orders", "sales_orders"),
                ("production_orders", "production_orders"),
                ("quotes", "quotes"),
                ("invoices", "invoices"),
                ("shipments", "shipments"),
            ]:
                sql, params = _status_distribution_sql(table, since, until)
                rows = conn.execute(sql, params).fetchall()
                status_list = [dict(r) for r in rows]
                status_distributions[key] = _sort_by_status_order(status_list, key)

            # ------ KPIs (counts are instant; revenue is time-filtered) ---
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

            # Revenue is time-filtered when a range is given
            rev_sql = "SELECT COALESCE(SUM(amount), 0) FROM payments"
            rev_params: list = []
            rev_conditions: list[str] = []
            if since:
                rev_conditions.append("payment_date >= ?")
                rev_params.append(since)
            if until:
                rev_conditions.append("payment_date <= ?")
                rev_params.append(until)
            if rev_conditions:
                rev_sql += " WHERE " + " AND ".join(rev_conditions)
            total_revenue = conn.execute(rev_sql, rev_params).fetchone()[0]

            kpis = {
                "open_orders": open_orders,
                "in_progress_mos": in_progress_mos,
                "pending_shipments": pending_shipments,
                "overdue_invoices": overdue_invoices,
                "total_revenue": total_revenue,
            }

        # ------ Recent activity (time-filtered) ---------------------------
        recent = activity_service.get_log(limit=20, since=since, until=until)

        # ------ Daily volumes (time-filtered) -----------------------------
        summary_rows = activity_service.get_daily_summary(since=since, until=until)
        # Pivot into {date: {orders, shipped, invoiced}}
        daily_map: dict = {}
        for row in summary_rows:
            d = row["date"]
            if d not in daily_map:
                daily_map[d] = {"date": d, "orders": 0, "shipped": 0, "invoiced": 0}
            action = row["action"]
            count = row["count"]
            if action in ("sales_order.created", "sales_order.confirmed"):
                daily_map[d]["orders"] += count
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
