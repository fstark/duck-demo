"""Service for recipe operations."""

from typing import Any, Dict, Optional

from db import dict_rows
from services._base import db_conn


class RecipeService:
    """Service for recipe operations."""

    @staticmethod
    def list_recipes(output_item_sku: Optional[str], limit: int) -> Dict[str, Any]:
        """List recipes."""
        with db_conn() as conn:
            if output_item_sku:
                from services.catalog import CatalogService
                item = CatalogService.load_item(output_item_sku)
                if not item:
                    raise ValueError(f"Item {output_item_sku} not found")
                rows = dict_rows(conn.execute("SELECT r.*, i.sku as output_sku, i.name as output_name FROM recipes r JOIN items i ON r.output_item_id = i.id WHERE r.output_item_id = ? ORDER BY r.id LIMIT ?", (item["id"], limit)))
            else:
                rows = dict_rows(conn.execute("SELECT r.*, i.sku as output_sku, i.name as output_name FROM recipes r JOIN items i ON r.output_item_id = i.id ORDER BY r.id LIMIT ?", (limit,)))
            return {"recipes": rows}

    @staticmethod
    def get_recipe(recipe_id: str) -> Dict[str, Any]:
        """Get detailed recipe information."""
        with db_conn() as conn:
            recipe = conn.execute("SELECT r.*, i.sku as output_sku, i.name as output_name, i.type as output_type FROM recipes r JOIN items i ON r.output_item_id = i.id WHERE r.id = ?", (recipe_id,)).fetchone()
            if not recipe:
                raise ValueError(f"Recipe {recipe_id} not found")
            result = dict(recipe)
            ingredients = dict_rows(conn.execute("SELECT ri.*, i.sku as ingredient_sku, i.name as ingredient_name FROM recipe_ingredients ri JOIN items i ON ri.input_item_id = i.id WHERE ri.recipe_id = ? ORDER BY ri.sequence_order", (recipe_id,)))
            result["ingredients"] = ingredients
            operations = dict_rows(conn.execute("SELECT * FROM recipe_operations WHERE recipe_id = ? ORDER BY sequence_order", (recipe_id,)))
            result["operations"] = operations
            return result


recipe_service = RecipeService()
