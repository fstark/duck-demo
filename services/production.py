"""Service for production order operations."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from db import dict_rows, generate_id
from utils import ui_href
from services._base import db_conn


class ProductionService:
    """Service for production order operations."""

    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get production statistics."""
        with db_conn() as conn:
            total_production = conn.execute("SELECT COUNT(*) as count FROM production_orders").fetchone()["count"]
            status_rows = dict_rows(conn.execute("SELECT status, COUNT(*) as count FROM production_orders GROUP BY status ORDER BY count DESC"))
            total_qty = conn.execute("SELECT SUM(r.output_qty) as total FROM production_orders po JOIN recipes r ON po.recipe_id = r.id").fetchone()["total"] or 0
            top_items = dict_rows(conn.execute("SELECT i.sku, i.name, SUM(r.output_qty) as total_qty, COUNT(*) as order_count FROM production_orders po JOIN recipes r ON po.recipe_id = r.id JOIN items i ON po.item_id = i.id GROUP BY i.id, i.sku, i.name ORDER BY total_qty DESC LIMIT 10"))
            upcoming = dict_rows(conn.execute("SELECT i.sku, i.name, r.output_qty as qty, po.eta_finish, po.status FROM production_orders po JOIN recipes r ON po.recipe_id = r.id JOIN items i ON po.item_id = i.id WHERE po.eta_finish >= date('now') AND po.eta_finish <= date('now', '+60 days') ORDER BY po.eta_finish LIMIT 20"))
            return {"total_production_orders": total_production, "production_orders_by_status": status_rows, "total_quantity_in_production": total_qty, "top_items_in_production": top_items, "upcoming_production": upcoming}

    @staticmethod
    def get_order_status(production_order_id: str) -> Dict[str, Any]:
        """Return status of a production order."""
        with db_conn() as conn:
            query = "SELECT po.*, i.name as item_name, i.sku as item_sku, i.type as item_type FROM production_orders po LEFT JOIN items i ON po.item_id = i.id WHERE po.id = ?"
            row = conn.execute(query, (production_order_id,)).fetchone()
            if not row:
                return {"error": "Production order not found", "production_order_id": production_order_id}
            result = dict(row)
            result["ui_url"] = ui_href("production-orders", production_order_id)
            operations = dict_rows(conn.execute("SELECT * FROM production_operations WHERE production_order_id = ? ORDER BY sequence_order", (production_order_id,)))
            result["operations"] = operations
            if result.get("recipe_id"):
                recipe = conn.execute("SELECT r.*, i.sku as output_sku, i.name as output_name FROM recipes r JOIN items i ON r.output_item_id = i.id WHERE r.id = ?", (result["recipe_id"],)).fetchone()
                if recipe:
                    result["recipe"] = dict(recipe)
                    ingredients = dict_rows(conn.execute("SELECT ri.*, i.sku as ingredient_sku, i.name as ingredient_name, i.uom as ingredient_uom FROM recipe_ingredients ri JOIN items i ON ri.input_item_id = i.id WHERE ri.recipe_id = ?", (result["recipe_id"],)))
                    result["recipe"]["ingredients"] = ingredients
                    recipe_operations = dict_rows(conn.execute("SELECT * FROM recipe_operations WHERE recipe_id = ? ORDER BY sequence_order", (result["recipe_id"],)))
                    result["recipe"]["operations"] = recipe_operations
            return result

    @staticmethod
    def find_orders_by_date_range(start_date: str, end_date: str, limit: int) -> List[Dict[str, Any]]:
        """Retrieve production orders by date range."""
        with db_conn() as conn:
            query = "SELECT po.*, i.name as item_name, i.sku as item_sku, i.type as item_type FROM production_orders po LEFT JOIN items i ON po.item_id = i.id WHERE po.eta_finish >= ? AND po.eta_finish <= ? ORDER BY po.eta_finish LIMIT ?"
            rows = conn.execute(query, (start_date, end_date, limit)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_order(recipe_id: str, notes: Optional[str]) -> Dict[str, Any]:
        """Create a new production order."""
        from services.recipe import RecipeService
        from services.inventory import InventoryService

        with db_conn() as conn:
            recipe_data = RecipeService.get_recipe(recipe_id)
            shortfalls = []
            for ing in recipe_data["ingredients"]:
                qty_needed = ing["input_qty"]
                check = InventoryService.check_availability(ing["ingredient_sku"], qty_needed)
                if not check["is_available"]:
                    shortfalls.append({"ingredient_sku": ing["ingredient_sku"], "ingredient_name": ing["ingredient_name"], "qty_needed": qty_needed, "qty_available": check["qty_available"], "shortfall": check["shortfall"]})
            status = "waiting" if shortfalls else "ready"
            prod_time_days = recipe_data["production_time_hours"] / 24.0
            eta_finish = (datetime.utcnow().date() + timedelta(days=1 + int(prod_time_days))).isoformat()
            eta_ship = (datetime.utcnow().date() + timedelta(days=2 + int(prod_time_days))).isoformat()
            order_id = generate_id(conn, "MO", "production_orders")
            conn.execute("INSERT INTO production_orders (id, recipe_id, item_id, status, eta_finish, eta_ship) VALUES (?, ?, ?, ?, ?, ?)", (order_id, recipe_id, recipe_data["output_item_id"], status, eta_finish, eta_ship))
            for op in recipe_data["operations"]:
                pop_id = generate_id(conn, "POP", "production_operations")
                conn.execute("INSERT INTO production_operations (id, production_order_id, recipe_operation_id, sequence_order, operation_name, duration_hours, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (pop_id, order_id, op["id"], op["sequence_order"], op["operation_name"], op["duration_hours"], "pending"))
            conn.commit()
            return {"production_order_id": order_id, "recipe_id": recipe_id, "output_item": recipe_data["output_sku"], "output_qty": recipe_data["output_qty"], "status": status, "eta_finish": eta_finish, "eta_ship": eta_ship, "ingredient_shortfalls": shortfalls, "ui_url": ui_href("production-orders", order_id)}

    @staticmethod
    def start_order(production_order_id: str) -> Dict[str, Any]:
        """Start a production order."""
        with db_conn() as conn:
            order = conn.execute("SELECT * FROM production_orders WHERE id = ?", (production_order_id,)).fetchone()
            if not order:
                raise ValueError(f"Production order {production_order_id} not found")
            if order["status"] != "ready":
                raise ValueError(f"Production order {production_order_id} is not ready (current status: {order['status']})")
            first_op = conn.execute("SELECT operation_name FROM recipe_operations WHERE recipe_id = ? ORDER BY sequence_order LIMIT 1", (order["recipe_id"],)).fetchone()
            current_operation = first_op["operation_name"] if first_op else None
            conn.execute("UPDATE production_orders SET status = 'in_progress', current_operation = ? WHERE id = ?", (current_operation, production_order_id))
            conn.commit()
            return {"production_order_id": production_order_id, "status": "in_progress", "current_operation": current_operation, "message": f"Production order {production_order_id} started"}

    @staticmethod
    def complete_order(production_order_id: str, qty_produced: int, warehouse: str, location: str) -> Dict[str, Any]:
        """Complete a production order."""
        with db_conn() as conn:
            order = conn.execute("SELECT * FROM production_orders WHERE id = ?", (production_order_id,)).fetchone()
            if not order:
                raise ValueError(f"Production order {production_order_id} not found")
            if order["status"] == "completed":
                raise ValueError(f"Production order {production_order_id} already completed")
            conn.execute("UPDATE production_orders SET status = 'completed', qty_produced = ?, current_operation = NULL WHERE id = ?", (qty_produced, production_order_id))
            stock_id = generate_id(conn, "STK", "stock")
            conn.execute("INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)", (stock_id, order["item_id"], warehouse, location, qty_produced))
            conn.commit()
            return {"production_order_id": production_order_id, "status": "completed", "qty_produced": qty_produced, "stock_id": stock_id, "warehouse": warehouse, "location": location, "message": f"Production order {production_order_id} completed, {qty_produced} units added to stock"}


production_service = ProductionService()
