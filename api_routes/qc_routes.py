"""API routes – QC hold batches and inspections (read-only)."""

from api_routes._common import _json, cors_handler
from services import qc_service


def register(mcp):
    """Register QC REST routes."""

    @mcp.custom_route("/api/qc/batches", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_qc_batches(request):
        status = request.query_params.get("status", "pending_images")
        batches = qc_service.list_pending_batches(status=status)
        return _json({"batches": batches})

    @mcp.custom_route("/api/qc/batches/{batch_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_qc_batch_detail(request):
        batch_id = request.path_params.get("batch_id")
        try:
            result = qc_service.get_batch(batch_id=batch_id)
            return _json(result)
        except ValueError as exc:
            return _json({"error": str(exc)}, status_code=404)

    @mcp.custom_route("/api/qc/inspections/{inspection_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_qc_inspection(request):
        inspection_id = request.path_params.get("inspection_id")
        try:
            result = qc_service.get_inspection(inspection_id=inspection_id)
            return _json(result)
        except ValueError as exc:
            return _json({"error": str(exc)}, status_code=404)
