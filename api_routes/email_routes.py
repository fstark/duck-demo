"""API routes – emails."""

from api_routes._common import _json, cors_handler
from services import messaging_service


def register(mcp):
    """Register email routes."""

    @mcp.custom_route("/api/emails", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_emails(request):
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
    @cors_handler(["GET"])
    async def api_email_detail(request):
        email_id = request.path_params.get("email_id")
        try:
            result = messaging_service.get_email(email_id)
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=404)
