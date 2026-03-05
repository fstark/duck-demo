"""API routes – invoices and invoice PDFs."""

from starlette.responses import Response

from api_routes._common import _json, cors_handler
from services import invoice_service, DocumentService


def register(mcp):
    """Register invoice routes."""

    @mcp.custom_route("/api/invoices", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_invoices(request):
        qp = request.query_params
        limit = int(qp.get("limit", 50))
        result = invoice_service.list_invoices(
            customer_ids=[qp["customer_id"]] if "customer_id" in qp else None,
            sales_order_id=qp.get("sales_order_id"),
            status=qp.get("status"),
            limit=limit
        )
        return _json(result)

    @mcp.custom_route("/api/invoices/{invoice_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_invoice_detail(request):
        invoice_id = request.path_params.get("invoice_id")
        try:
            result = invoice_service.get_invoice(invoice_id)
            if not result:
                return _json({"error": "Invoice not found"}, status_code=404)
            return _json(result)
        except Exception as exc:
            return _json({"error": str(exc)}, status_code=404)

    @mcp.custom_route("/api/invoices/{invoice_id}/pdf", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_invoice_pdf(request):
        invoice_id = request.path_params.get("invoice_id")
        try:
            doc = DocumentService.get_document("invoice", invoice_id, "invoice_pdf")

            if doc:
                pdf_bytes = doc["content"]
            else:
                pdf_bytes = invoice_service.generate_invoice_pdf(invoice_id)

            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename=invoice_{invoice_id}.pdf",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        except ValueError as exc:
            return _json({"error": str(exc)}, status_code=404)
        except Exception as exc:
            return _json({"error": f"Failed to generate PDF: {str(exc)}"}, status_code=500)
