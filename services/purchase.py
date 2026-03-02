"""Service for purchase order operations."""

from types import SimpleNamespace
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from db import generate_id
from services._base import db_conn


def create_order(item_sku: str, qty: int, supplier_name: Optional[str]) -> Dict[str, Any]:
    """Create a purchase order."""
    from services.catalog import catalog_service
    from services.simulation import simulation_service

    with db_conn() as conn:
        item = catalog_service.load_item(item_sku)
        if not item:
            raise ValueError(f"Item {item_sku} not found")
        if not supplier_name:
            if item.get("default_supplier_id"):
                supplier = conn.execute("SELECT * FROM suppliers WHERE id = ?", (item["default_supplier_id"],)).fetchone()
                if supplier:
                    supplier_name = supplier["name"]
        if not supplier_name:
            raise ValueError(f"No supplier specified and no default supplier configured for item {item_sku}")
        supplier = conn.execute("SELECT * FROM suppliers WHERE name = ?", (supplier_name,)).fetchone()
        if not supplier:
            raise ValueError(f"Supplier {supplier_name} not found")
        po_id = generate_id(conn, "PO", "purchase_orders")
        sim_time = simulation_service.get_current_time()
        sim_date = datetime.fromisoformat(sim_time).date()
        expected_delivery = (sim_date + timedelta(days=supplier["lead_time_days"] if supplier["lead_time_days"] else 7)).isoformat()
        cost = item.get("cost_price") or item.get("unit_price") or 0
        conn.execute("INSERT INTO purchase_orders (id, supplier_id, item_id, qty, unit_price, total, currency, status, expected_delivery, ordered_at) VALUES (?, ?, ?, ?, ?, ?, 'EUR', 'ordered', ?, ?)", (po_id, supplier["id"], item["id"], qty, cost, cost * qty, expected_delivery, sim_time))
        conn.commit()
        return {"purchase_order_id": po_id, "supplier_name": supplier["name"], "item_sku": item_sku, "item_name": item["name"], "qty": qty, "status": "ordered", "expected_delivery": expected_delivery, "message": f"Purchase order {po_id} created for {qty} {item['uom']} of {item['name']} from {supplier['name']}"}

def restock_materials() -> Dict[str, Any]:
    """Check and create purchase orders for low stock items."""
    from db import dict_rows
    with db_conn() as conn:
        items_to_reorder = dict_rows(conn.execute("SELECT i.*, COALESCE(SUM(s.on_hand), 0) as current_stock FROM items i LEFT JOIN stock s ON i.id = s.item_id WHERE i.type IN ('raw_material', 'component', 'material') AND i.reorder_qty > 0 GROUP BY i.id HAVING current_stock < i.reorder_qty ORDER BY i.sku"))
        purchase_orders = []
        for item in items_to_reorder:
            qty_to_order = item["reorder_qty"] - item["current_stock"]
            po = create_order(item["sku"], qty_to_order, None)
            purchase_orders.append(po)
        return {"items_checked": len(items_to_reorder), "purchase_orders_created": len(purchase_orders), "purchase_orders": purchase_orders}

def receive(purchase_order_id: str, warehouse: str, location: str) -> Dict[str, Any]:
    """Receive a purchase order."""
    with db_conn() as conn:
        po = conn.execute("SELECT po.*, i.sku as item_sku, i.name as item_name FROM purchase_orders po JOIN items i ON po.item_id = i.id WHERE po.id = ?", (purchase_order_id,)).fetchone()
        if not po:
            raise ValueError(f"Purchase order {purchase_order_id} not found")
        if po["status"] == "received":
            raise ValueError(f"Purchase order {purchase_order_id} already received")
        from services.simulation import simulation_service
        sim_time = simulation_service.get_current_time()
        conn.execute("UPDATE purchase_orders SET status = 'received', received_at = ? WHERE id = ?", (sim_time, purchase_order_id,))
        stock_id = generate_id(conn, "STK", "stock")
        conn.execute("INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)", (stock_id, po["item_id"], warehouse, location, po["qty"]))
        conn.commit()
        return {"purchase_order_id": purchase_order_id, "item_sku": po["item_sku"], "item_name": po["item_name"], "qty_received": po["qty"], "stock_id": stock_id, "warehouse": warehouse, "location": location, "message": f"Purchase order {purchase_order_id} received, {po['qty']} units added to stock"}


# Namespace for backward compatibility
purchase_service = SimpleNamespace(
    create_order=create_order,
    restock_materials=restock_materials,
    receive=receive,
)
PurchaseService = type(purchase_service)
