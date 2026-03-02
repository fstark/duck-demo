"""Service for logistics and shipment operations."""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from db import dict_rows, generate_id
from utils import ship_to_columns, ui_href
from services._base import db_conn


def create_shipment(ship_from: Dict[str, Any], ship_to: Dict[str, Any], planned_departure: str, planned_arrival: str, packages: List[Dict[str, Any]], reference: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a planned shipment."""
    from services.catalog import catalog_service

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
        conn.execute("INSERT INTO shipments (id, ship_from_warehouse, ship_to_line1, ship_to_line2, ship_to_postal_code, ship_to_city, ship_to_country, planned_departure, planned_arrival, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (shipment_id, ship_from.get("warehouse"), *ship_to_columns(ship_to), planned_departure, planned_arrival, "planned"))
        line_counter = 1
        for pkg in packages:
            for content in pkg.get("contents", []):
                item = catalog_service.load_item(content["sku"])
                if not item:
                    raise ValueError(f"Unknown SKU {content['sku']}")
                line_id = f"{shipment_id}-{line_counter:02d}"
                conn.execute("INSERT INTO shipment_lines (id, shipment_id, item_id, qty) VALUES (?, ?, ?, ?)", (line_id, shipment_id, item["id"], int(content["qty"])))
                line_counter += 1
        if reference and reference.get("type") == "sales_order" and reference.get("id"):
            conn.execute("INSERT OR IGNORE INTO sales_order_shipments (sales_order_id, shipment_id) VALUES (?, ?)", (reference["id"], shipment_id))
        conn.commit()
        return {"shipment_id": shipment_id, "status": "planned", "planned_departure": planned_departure, "planned_arrival": planned_arrival, "ui_url": ui_href("shipments", shipment_id)}

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

def dispatch_shipment(shipment_id: str) -> Dict[str, Any]:
    """Dispatch a planned shipment: transition to in_transit and deduct stock."""
    from services.inventory import inventory_service
    from services.simulation import simulation_service

    with db_conn() as conn:
        row = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not row:
            raise ValueError(f"Shipment {shipment_id} not found")
        if row["status"] != "planned":
            raise ValueError(f"Shipment {shipment_id} is not planned (current status: {row['status']})")

        # Deduct stock for each shipment line
        lines = conn.execute(
            "SELECT item_id, qty FROM shipment_lines WHERE shipment_id = ?",
            (shipment_id,)
        ).fetchall()
        for line in lines:
            inventory_service.deduct_stock(line["item_id"], line["qty"], conn=conn)

        sim_time = simulation_service.get_current_time()
        conn.execute(
            "UPDATE shipments SET status = 'in_transit', tracking_ref = ?, dispatched_at = ? WHERE id = ?",
            (f"TRK-{shipment_id}", sim_time, shipment_id)
        )
        conn.commit()
        return {
            "shipment_id": shipment_id,
            "status": "in_transit",
            "dispatched_at": sim_time,
            "lines_shipped": len(lines),
            "message": f"Shipment {shipment_id} dispatched",
            "ui_url": ui_href("shipments", shipment_id),
        }

def deliver_shipment(shipment_id: str) -> Dict[str, Any]:
    """Mark a shipment as delivered."""
    from services.simulation import simulation_service

    with db_conn() as conn:
        row = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not row:
            raise ValueError(f"Shipment {shipment_id} not found")
        if row["status"] != "in_transit":
            raise ValueError(f"Shipment {shipment_id} is not in transit (current status: {row['status']})")

        sim_time = simulation_service.get_current_time()
        conn.execute(
            "UPDATE shipments SET status = 'delivered', delivered_at = ? WHERE id = ?",
            (sim_time, shipment_id,)
        )
        conn.commit()
        return {
            "shipment_id": shipment_id,
            "status": "delivered",
            "delivered_at": sim_time,
            "message": f"Shipment {shipment_id} delivered",
            "ui_url": ui_href("shipments", shipment_id),
        }


# Namespace for backward compatibility
logistics_service = SimpleNamespace(
    create_shipment=create_shipment,
    get_shipment_status=get_shipment_status,
    dispatch_shipment=dispatch_shipment,
    deliver_shipment=deliver_shipment,
)
LogisticsService = type(logistics_service)
