"""API routes – recipes."""

from api_routes._common import _json, _cors_preflight
from services import recipe_service


def register(mcp):
    """Register recipe routes."""

    @mcp.custom_route("/api/recipes", methods=["GET", "OPTIONS"])
    async def api_recipes(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        qp = request.query_params
        output_item_sku = qp.get("output_item_sku")
        limit = int(qp.get("limit", 50))
        result = recipe_service.list_recipes(output_item_sku=output_item_sku, limit=limit)
        return _json(result)

    @mcp.custom_route("/api/recipes/{recipe_id}", methods=["GET", "OPTIONS"])
    async def api_recipe_detail(request):
        if request.method == "OPTIONS":
            return _cors_preflight(["GET"])
        recipe_id = request.path_params.get("recipe_id")
        try:
            result = recipe_service.get_recipe(recipe_id)
            return _json(result)
        except ValueError as exc:
            return _json({"error": str(exc)}, status_code=404)
