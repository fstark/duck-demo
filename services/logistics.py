"""Service for logistics and shipment operations."""

from typing import Any, Dict, List, Optional

from db import dict_rows, generate_id
from utils import ui_href
from services._base import db_conn


class LogisticsService:
    """Service for logistics and shipment operations."""

    @staticmethod
    def create_shipment(ship_from: Dict[str, Any], ship_to: Dict[str, Any], planned_departure: str, planned_arrival: str, packages: List[Dict[str, Any]], reference: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a planned shipment."""
        from services.catalog import CatalogService

        if not packages:
            raise ValueError("Cannot create shipment: packages list cannot be empty. At least one package with contents is required.")

        if not ship_from.get("warehouse"):
            raise ValueError("Cannot create shipment: ship_from must contain a 'warehouse' field.")

        missing_fields = []
        if not ship_to.get("line1"):
            missing_fields.append("line1 (street address)")
        if not ship_to.get("city"):
            missing_fields.append("city")
        if not ship_to.get("postal_code"):
            missing_fields.append("postal_code")
        if not ship_to.get("country"):
            missing_fields.append("country")
        if missing_fields:
            raise ValueError(f"Cannot create shipment: ship_to address is missing required fields: {', '.join(missing_fields)}. Please provide a complete shipping address.")

        with db_conn() as conn:
            shipment_id = generate_id(conn, "SHIP", "shipments")
            conn.execute("INSERT INTO shipments (id, ship_from_warehouse, ship_to_line1, ship_to_postal_code, ship_to_city, ship_to_country, planned_departure, planned_arrival, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (shipment_id, ship_from.get("warehouse"), ship_to.get("line1"), ship_to.get("postal_code"), ship_to.get("city"), ship_to.get("country"), planned_departure, planned_arrival, "planned"))
            line_counter = 1
            for pkg in packages:
                for content in pkg.get("contents", []):
                    item = CatalogService.load_item(content["sku"])
                    if not item:
                        raise ValueError(f"Unknown SKU {content['sku']}")
                    line_id = f"{shipment_id}-{line_counter:02d}"
                    conn.execute("INSERT INTO shipment_lines (id, shipment_id, item_id, qty) VALUES (?, ?, ?, ?)", (line_id, shipment_id, item["id"], float(content["qty"])))
                    line_counter += 1
            if reference and reference.get("type") == "sales_order" and reference.get("id"):
                conn.execute("INSERT OR IGNORE INTO sales_order_shipments (sales_order_id, shipment_id) VALUES (?, ?)", (reference["id"], shipment_id))
            conn.commit()
            return {"shipment_id": shipment_id, "status": "planned", "planned_departure": planned_departure, "planned_arrival": planned_arrival, "ui_url": ui_href("shipments", shipment_id)}

    @staticmethod
    def get_shipment_status(shipment_id: str) -> Dict[str, Any]:
        """Return the status of a shipment."""
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
            if not row:
                raise ValueError("Shipment not found")
            data = dict(row)
            data["ui_url"] = ui_href("shipments", shipment_id)
            orders_query = "SELECT so.id as sales_order_id, so.customer_id, c.name as customer_name, c.company as customer_company, so.status FROM sales_order_shipments sos JOIN sales_orders so ON sos.sales_order_id = so.id LEFT JOIN customers c ON so.customer_id = c.id WHERE sos.shipment_id = ?"
            orders = dict_rows(conn.execute(orders_query, (shipment_id,)).fetchall())
            data["sales_orders"] = orders
            return data


logistics_service = LogisticsService()
