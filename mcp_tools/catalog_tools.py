"""MCP tools – catalog items, search, and 3D inspection."""

import logging
import os
from typing import Any, Dict, List, Optional

from mcp.types import CallToolResult, TextContent

from mcp_tools._common import log_tool
from services import catalog_service

logger = logging.getLogger("duck-demo")


def register(mcp):
    """Register catalog tools."""

    @mcp.tool(name="catalog_get_item", meta={"tags": ["shared"]})
    @log_tool("catalog_get_item")
    def get_item(sku: str) -> Dict[str, Any]:
        """
        Fetch complete item details by SKU or item_id.
        Use this after search to get full details including image_url, uom, and reorder_qty.
        Accepts either SKU (e.g., 'ELVIS-RED-20') or item_id (e.g., 'ITEM-ELVIS-20').

        Parameters:
            sku: The item SKU or item_id

        Returns:
            Complete item details: id, sku, name, type, unit_price, uom, reorder_qty, image_url
        """
        return catalog_service.get_item(sku)

    @mcp.tool(name="catalog_inspect_item", meta={
        "tags": ["shared"],
        "ui": {
            "resourceUri": "ui://item-inspect/viewer",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("catalog_inspect_item")
    def inspect_item(sku: str) -> Dict[str, Any]:
        """
        Launch interactive 3D viewer to inspect an item in detail.
        This tool returns an MCP App UI with a rotating 3D wireframe model and item details overlay.

        Parameters:
            sku: The item SKU or item_id to inspect

        Returns:
            UI metadata for interactive 3D viewer. The viewer displays the item as a rotating
            wireframe model with mouse-controlled rotation and overlaid product details.
        """
        try:
            item = catalog_service.get_item(sku)

            # Load the 3D model data to send to the MCP app based on SKU
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", f"{item['sku']}.obj")
            model_data = None
            try:
                with open(model_path, 'r') as f:
                    model_data = f.read()
            except Exception as model_error:
                logger.warning(f"Failed to load 3D model for {item['sku']}: {model_error}")

            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Launching 3D inspector for: **{item['name']}**"
                    )
                ],
                structuredContent={
                    **item,
                    "model_obj": model_data
                },
                isError=False
            )
        except Exception as e:
            logger.error(f"Error in catalog_inspect_item for sku={sku}: {e}", exc_info=True)
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Error inspecting item {sku}: {e}"
                    )
                ],
                structuredContent={
                    "sku": sku,
                    "name": "Item Not Found",
                    "type": "unknown",
                    "unit_price": 0.0
                },
                isError=True
            )

    @mcp.tool(name="catalog_search_items", meta={"tags": ["shared"]})
    @log_tool("catalog_search_items")
    def search_items(words: List[str], limit: int = 10, min_score: int = 1) -> Dict[str, Any]:
        """
        Fuzzy search for items by keywords in SKU or name, ranked by relevance.
        Returns MINIMAL fields only for efficient browsing.
        Use catalog_get_item(sku) to get complete details including image_url.

        Parameters:
            words: List of search terms to match
            limit: Maximum results to return (default: 10)
            min_score: Minimum match score (default: 1)

        Returns:
            Nested structure: {"items": [{"item": {...}, "score": N, "matched_words": [...]}]}
            Item object includes ONLY: id, sku, name, type, unit_price, ui_url
        """
        return catalog_service.search_items(words, limit, min_score)

    @mcp.tool(name="catalog_list_recipes", meta={"tags": ["shared"]})
    @log_tool("catalog_list_recipes")
    def recipe_list(output_item_sku: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        List recipes, optionally filtering by output item SKU.

        Parameters:
            output_item_sku: Optional SKU to filter recipes that produce this item
            limit: Maximum number of recipes to return
        """
        from services import recipe_service
        return recipe_service.list_recipes(output_item_sku, limit)

    @mcp.tool(name="catalog_get_recipe", meta={"tags": ["shared"]})
    @log_tool("catalog_get_recipe")
    def recipe_get(recipe_id: str) -> Dict[str, Any]:
        """
        Get detailed recipe information including ingredients and operations.

        Parameters:
            recipe_id: The recipe ID (e.g., 'RCP-ELVIS-20')
        """
        from services import recipe_service
        return recipe_service.get_recipe(recipe_id)
