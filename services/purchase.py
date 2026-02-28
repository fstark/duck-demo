"""Service for purchase order operations."""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from db import generate_id
from services._base import db_conn


class PurchaseService:
    """Service for purchase order operations."""

    @staticmethod
    def create_order(item_sku: str, qty: float, supplier_name: Optional[str]) -> Dict[str, Any]:
        """Create a purchase order."""
        from services.catalog import CatalogService
        from services.simulation import SimulationService

        with db_conn() as conn:
            item = CatalogService.load_item(item_sku)
            if not item:
                raise ValueError(f"Item {item_sku} not found")
            if not supplier_name:
                if "pvc" in item["name"].lower() or "plastic" in item["name"].lower():
                    supplier_name = "PlasticCorp"
                elif "dye" in item["name"].lower() or "color" in item["name"].lower():
                    supplier_name = "ColorMaster"
                elif "box" in item["name"].lower() or "packaging" in item["name"].lower():
                    supplier_name = "PackagingPlus"
                else:
                    supplier_name = "PlasticCorp"
            supplier = conn.execute("SELECT * FROM suppliers WHERE name = ?", (supplier_name,)).fetchone()
            if not supplier:
                raise ValueError(f"Supplier {supplier_name} not found")
            po_id = generate_id(conn, "PO", "purchase_orders")
            sim_time = SimulationService.get_current_time()
            expected_delivery = (datetime.utcnow().date() + timedelta(days=7)).isoformat()
            conn.execute("INSERT INTO purchase_orders (id, supplier_id, item_id, qty, status, expected_delivery, ordered_at) VALUES (?, ?, ?, ?, 'ordered', ?, ?)", (po_id, supplier["id"], item["id"], qty, expected_delivery, sim_time))
            conn.commit()
            return {"purchase_order_id": po_id, "supplier_name": supplier["name"], "item_sku": item_sku, "item_name": item["name"], "qty": qty, "status": "ordered", "expected_delivery": expected_delivery, "message": f"Purchase order {po_id} created for {qty} {item['uom']} of {item['name']} from {supplier['name']}"}

    @staticmethod
    def restock_materials() -> Dict[str, Any]:
        """Check and create purchase orders for low stock items."""
        from db import dict_rows
        with db_conn() as conn:
            items_to_reorder = dict_rows(conn.execute("SELECT i.*, COALESCE(SUM(s.on_hand), 0) as current_stock FROM items i LEFT JOIN stock s ON i.id = s.item_id WHERE i.type IN ('raw_material', 'component') AND i.reorder_qty > 0 GROUP BY i.id HAVING current_stock < i.reorder_qty ORDER BY i.sku"))
            purchase_orders = []
            for item in items_to_reorder:
                qty_to_order = item["reorder_qty"] - item["current_stock"]
                po = PurchaseService.create_order(item["sku"], qty_to_order, None)
                purchase_orders.append(po)
            return {"items_checked": len(items_to_reorder), "purchase_orders_created": len(purchase_orders), "purchase_orders": purchase_orders}

    @staticmethod
    def receive(purchase_order_id: str, warehouse: str, location: str) -> Dict[str, Any]:
        """Receive a purchase order."""
        with db_conn() as conn:
            po = conn.execute("SELECT po.*, i.sku as item_sku, i.name as item_name FROM purchase_orders po JOIN items i ON po.item_id = i.id WHERE po.id = ?", (purchase_order_id,)).fetchone()
            if not po:
                raise ValueError(f"Purchase order {purchase_order_id} not found")
            if po["status"] == "received":
                raise ValueError(f"Purchase order {purchase_order_id} already received")
            conn.execute("UPDATE purchase_orders SET status = 'received' WHERE id = ?", (purchase_order_id,))
            stock_id = generate_id(conn, "STK", "stock")
            conn.execute("INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)", (stock_id, po["item_id"], warehouse, location, po["qty"]))
            conn.commit()
            return {"purchase_order_id": purchase_order_id, "item_sku": po["item_sku"], "item_name": po["item_name"], "qty_received": po["qty"], "stock_id": stock_id, "warehouse": warehouse, "location": location, "message": f"Purchase order {purchase_order_id} received, {po['qty']} units added to stock"}


purchase_service = PurchaseService()
