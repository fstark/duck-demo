"""Service for sales order operations."""

from typing import Any, Dict, List, Optional

from db import dict_rows, generate_id
from utils import ui_href
from services._base import db_conn
from services.catalog import CatalogService
from services.simulation import SimulationService
from services.pricing import PricingService


class SalesService:
    """Service for sales order operations."""

    @staticmethod
    def create_order(customer_id: str, requested_delivery_date: Optional[str], ship_to: Optional[Dict[str, Any]], lines: Optional[List[Dict[str, Any]]], note: Optional[str]) -> Dict[str, Any]:
        """Create a draft sales order with lines."""
        if not lines:
            raise ValueError("lines required")
        ship_to = ship_to or {}
        with db_conn() as conn:
            so_id = generate_id(conn, "SO", "sales_orders")
            sim_time = SimulationService.get_current_time()
            conn.execute("INSERT INTO sales_orders (id, customer_id, requested_delivery_date, ship_to_line1, ship_to_postal_code, ship_to_city, ship_to_country, note, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (so_id, customer_id, requested_delivery_date, ship_to.get("line1"), ship_to.get("postal_code"), ship_to.get("city"), ship_to.get("country"), note, "draft", sim_time))
            line_results = []
            for idx, line in enumerate(lines, start=1):
                item = CatalogService.load_item(line["sku"])
                if not item:
                    raise ValueError(f"Unknown SKU {line['sku']}")
                line_id = f"{so_id}-{idx:02d}"
                conn.execute("INSERT INTO sales_order_lines (id, sales_order_id, item_id, qty) VALUES (?, ?, ?, ?)", (line_id, so_id, item["id"], float(line["qty"])))
                line_results.append({"line_id": line_id, "sku": line["sku"], "qty": float(line["qty"])})
            conn.commit()
            return {"sales_order_id": so_id, "status": "draft", "lines": line_results, "ui_url": ui_href("orders", so_id)}

    @staticmethod
    def search_orders(customer_id: Optional[str], limit: int, sort: str) -> Dict[str, Any]:
        """Return recent sales orders."""
        order_clause = "ORDER BY created_at DESC" if sort == "most_recent" else "ORDER BY id"
        with db_conn() as conn:
            if customer_id:
                cur = conn.execute(f"SELECT * FROM sales_orders WHERE customer_id = ? {order_clause} LIMIT ?", (customer_id, limit))
            else:
                cur = conn.execute(f"SELECT * FROM sales_orders {order_clause} LIMIT ?", (limit,))
            rows = cur.fetchall()
            sales_orders = []
            for row in rows:
                line_cur = conn.execute("SELECT i.sku, sol.qty FROM sales_order_lines sol JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?", (row["id"],))
                lines = dict_rows(line_cur.fetchall())
                summary = ", ".join([f"{l['qty']} x {l['sku']}" for l in lines])
                fulfillment_state = row["status"] or "draft"
                ship_row = conn.execute("SELECT s.status FROM sales_order_shipments sos JOIN shipments s ON s.id = sos.shipment_id WHERE sos.sales_order_id = ? LIMIT 1", (row["id"],)).fetchone()
                if ship_row and ship_row["status"]:
                    fulfillment_state = ship_row["status"]
                customer_row = conn.execute("SELECT name, company FROM customers WHERE id = ?", (row["customer_id"],)).fetchone()
                customer_name = customer_row["name"] if customer_row else None
                customer_company = customer_row["company"] if customer_row else None
                pricing_data = PricingService.compute_pricing(row["id"])["pricing"]
                sales_orders.append({"sales_order_id": row["id"], "customer_id": row["customer_id"], "customer_name": customer_name, "customer_company": customer_company, "created_at": row["created_at"], "summary": summary, "fulfillment_state": fulfillment_state, "lines": lines, "total": pricing_data["total"], "currency": pricing_data["currency"], "ui_url": ui_href("orders", row["id"])})
            return {"sales_orders": sales_orders}

    @staticmethod
    def get_order_details(sales_order_id: str) -> Optional[Dict[str, Any]]:
        """Load full sales order detail."""
        with db_conn() as conn:
            order = conn.execute("SELECT * FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
            if not order:
                return None
            customer = conn.execute("SELECT * FROM customers WHERE id = ?", (order["customer_id"],)).fetchone()
            customer_dict = dict(customer) if customer else None
            if customer_dict:
                customer_dict["ui_url"] = ui_href("customers", customer_dict["id"])
            lines = dict_rows(conn.execute("SELECT i.sku, sol.qty FROM sales_order_lines sol JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?", (sales_order_id,)).fetchall())
            pricing = PricingService.compute_pricing(sales_order_id)["pricing"]
            shipments = dict_rows(conn.execute("SELECT s.* FROM sales_order_shipments sos JOIN shipments s ON s.id = sos.shipment_id WHERE sos.sales_order_id = ? ORDER BY s.planned_departure", (sales_order_id,)).fetchall())
            order_dict = dict(order)
            order_dict["ui_url"] = ui_href("orders", sales_order_id)
            for shipment in shipments:
                shipment["ui_url"] = ui_href("shipments", shipment["id"])
            return {"sales_order": order_dict, "customer": customer_dict, "lines": lines, "pricing": pricing, "shipments": shipments}

    @staticmethod
    def link_shipment(sales_order_id: str, shipment_id: str) -> Dict[str, Any]:
        """Link an existing shipment to a sales order."""
        with db_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO sales_order_shipments (sales_order_id, shipment_id) VALUES (?, ?)", (sales_order_id, shipment_id))
            conn.commit()
            return {"status": "linked"}

    @staticmethod
    def confirm_order(sales_order_id: str) -> Dict[str, Any]:
        """Confirm a draft sales order (draft -> confirmed)."""
        with db_conn() as conn:
            order = conn.execute("SELECT * FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
            if not order:
                raise ValueError(f"Sales order {sales_order_id} not found")
            if order["status"] != "draft":
                raise ValueError(f"Sales order {sales_order_id} is not draft (current status: {order['status']})")
            conn.execute("UPDATE sales_orders SET status = 'confirmed' WHERE id = ?", (sales_order_id,))
            conn.commit()
            return {
                "sales_order_id": sales_order_id,
                "status": "confirmed",
                "message": f"Sales order {sales_order_id} confirmed",
                "ui_url": ui_href("orders", sales_order_id),
            }

    @staticmethod
    def complete_order(sales_order_id: str) -> Dict[str, Any]:
        """Mark a sales order as completed."""
        with db_conn() as conn:
            order = conn.execute("SELECT * FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
            if not order:
                raise ValueError(f"Sales order {sales_order_id} not found")
            if order["status"] == "completed":
                raise ValueError(f"Sales order {sales_order_id} already completed")
            conn.execute("UPDATE sales_orders SET status = 'completed' WHERE id = ?", (sales_order_id,))
            conn.commit()
            return {
                "sales_order_id": sales_order_id,
                "status": "completed",
                "message": f"Sales order {sales_order_id} completed",
                "ui_url": ui_href("orders", sales_order_id),
            }


sales_service = SalesService()
