"""API routes – activity log feed and daily summary."""

from api_routes._common import _json, cors_handler
from services import activity_service


def register(mcp):
    """Register activity log routes."""

    @mcp.custom_route("/api/activity-log", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_activity_log(request):
        qp = request.query_params
        result = activity_service.get_log(
            limit=int(qp.get("limit", 50)),
            offset=int(qp.get("offset", 0)),
            category=qp.get("category"),
            action=qp.get("action"),
            entity_type=qp.get("entity_type"),
            entity_id=qp.get("entity_id"),
            since=qp.get("since"),
            until=qp.get("until"),
        )
        return _json(result)

    @mcp.custom_route("/api/activity-log/summary", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_activity_log_summary(request):
        qp = request.query_params
        result = activity_service.get_daily_summary(
            since=qp.get("since"),
            until=qp.get("until"),
        )
        return _json(result)
