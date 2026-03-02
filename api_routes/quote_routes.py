"""API routes – quotes and quote PDFs."""

from starlette.responses import Response

from api_routes._common import _json, cors_handler
from services import quote_service, DocumentService


def register(mcp):
    """Register quote routes."""

    @mcp.custom_route("/api/quotes", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_quotes(request):
        qp = request.query_params
        limit = int(qp.get("limit", 50))
        show_superseded = qp.get("show_superseded", "false").lower() == "true"
        result = quote_service.list_quotes(
            customer_id=qp.get("customer_id"),
            status=qp.get("status"),
            limit=limit,
            show_superseded=show_superseded
        )
        return _json(result)

    @mcp.custom_route("/api/quotes/{quote_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_quote_detail(request):
        quote_id = request.path_params.get("quote_id")
        try:
            result = quote_service.get_quote(quote_id)
            if not result:
                return _json({"error": "Quote not found"}, status_code=404)
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=404)

    @mcp.custom_route("/api/quotes/{quote_id}/pdf", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_quote_pdf(request):
        quote_id = request.path_params.get("quote_id")
        try:
            doc = DocumentService.get_document("quote", quote_id, "quote_pdf")

            if doc:
                pdf_bytes = doc["content"]
            else:
                pdf_bytes = quote_service.generate_quote_pdf(quote_id)

            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename=quote_{quote_id}.pdf",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        except ValueError as exc:
            return _json({"error": str(exc)}, status_code=404)
        except Exception as exc:
            return _json({"error": f"Failed to generate PDF: {str(exc)}"}, status_code=500)
