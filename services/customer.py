"""Service for customer (CRM) operations."""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from db import dict_rows, generate_id
from utils import ui_href
from services._base import db_conn


def find_customers(
    name: Optional[str] = None,
    email: Optional[str] = None,
    company: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    phone: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Find matching customers with filters."""
    filters = []
    params: List[str] = []
    if name:
        filters.append("LOWER(name) LIKE ?")
        params.append(f"%{name.lower()}%")
    if email:
        filters.append("LOWER(email) LIKE ?")
        params.append(f"%{email.lower()}%")
    if company:
        filters.append("LOWER(company) LIKE ?")
        params.append(f"%{company.lower()}%")
    if city:
        filters.append("LOWER(city) LIKE ?")
        params.append(f"%{city.lower()}%")
    if country:
        filters.append("UPPER(country) = ?")
        params.append(country.upper())
    if phone:
        filters.append("phone LIKE ?")
        params.append(f"%{phone}%")

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    sql = f"SELECT id, name, company, email, phone, city, country, created_at FROM customers {where_clause} ORDER BY id LIMIT ?"
    params.append(limit)

    with db_conn() as conn:
        rows = dict_rows(conn.execute(sql, params))
        for row in rows:
            row["ui_url"] = ui_href("customers", row["id"])
        return {"customers": rows}

def create_customer(
    name: str,
    company: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    address_line1: Optional[str] = None,
    address_line2: Optional[str] = None,
    city: Optional[str] = None,
    postal_code: Optional[str] = None,
    country: Optional[str] = None,
    tax_id: Optional[str] = None,
    payment_terms: Optional[int] = None,
    currency: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new customer."""
    from services.simulation import simulation_service

    with db_conn() as conn:
        customer_id = generate_id(conn, "CUST", "customers")
        sim_time = simulation_service.get_current_time()
        conn.execute(
            """INSERT INTO customers 
               (id, name, company, email, phone, address_line1, address_line2, city, postal_code, country, tax_id, payment_terms, currency, notes, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, name, company, email, phone, address_line1, address_line2, city, postal_code, country, tax_id, payment_terms, currency, notes, sim_time),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        row_dict = dict(row)
        row_dict["ui_url"] = ui_href("customers", customer_id)
        return {
            "customer_id": customer_id,
            "customer": row_dict,
            "message": f"Customer '{name}' created with ID {customer_id} at {sim_time}"
        }

def update_customer(
    customer_id: str,
    name: Optional[str] = None,
    company: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    address_line1: Optional[str] = None,
    address_line2: Optional[str] = None,
    city: Optional[str] = None,
    postal_code: Optional[str] = None,
    country: Optional[str] = None,
    tax_id: Optional[str] = None,
    payment_terms: Optional[int] = None,
    currency: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an existing customer. Only provided fields are updated."""
    with db_conn() as conn:
        cust = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not cust:
            raise ValueError(f"Customer {customer_id} not found")

        updates = []
        params: List[Any] = []
        field_map = {
            "name": name, "company": company, "email": email, "phone": phone,
            "address_line1": address_line1, "address_line2": address_line2,
            "city": city, "postal_code": postal_code, "country": country,
            "tax_id": tax_id, "payment_terms": payment_terms, "currency": currency, "notes": notes,
        }
        for field, value in field_map.items():
            if value is not None:
                updates.append(f"{field} = ?")
                params.append(value)

        if not updates:
            raise ValueError("No fields to update")

        params.append(customer_id)
        conn.execute(
            f"UPDATE customers SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        row_dict = dict(row)
        row_dict["ui_url"] = ui_href("customers", customer_id)
        return {
            "customer_id": customer_id,
            "customer": row_dict,
            "message": f"Customer {customer_id} updated successfully"
        }

def get_customer_details(customer_id: str, include_orders: bool = True) -> Dict[str, Any]:
    """Get customer data plus recent orders."""
    with db_conn() as conn:
        cust = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not cust:
            raise ValueError("Customer not found")

        result: Dict[str, Any] = {"customer": dict(cust)}
        result["customer"]["ui_url"] = ui_href("customers", customer_id)

        if include_orders:
            order_rows = conn.execute(
                "SELECT * FROM sales_orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT 10",
                (customer_id,),
            ).fetchall()
            orders: List[Dict[str, Any]] = []
            for order in order_rows:
                lines = dict_rows(
                    conn.execute(
                        "SELECT i.sku, sol.qty FROM sales_order_lines sol JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?",
                        (order["id"],),
                    ).fetchall()
                )
                ship = conn.execute(
                    "SELECT s.id, s.status, s.planned_departure, s.planned_arrival, s.tracking_ref FROM sales_order_shipments sos JOIN shipments s ON s.id = sos.shipment_id WHERE sos.sales_order_id = ? ORDER BY s.planned_departure DESC LIMIT 1",
                    (order["id"],),
                ).fetchone()
                ship_dict = dict(ship) if ship else None
                pending = True
                if ship_dict and ship_dict.get("status") and ship_dict["status"].lower() == "delivered":
                    pending = False
                elif order["status"] and order["status"].lower() == "draft":
                    pending = True
                if ship_dict:
                    ship_dict["ui_url"] = ui_href("shipments", ship_dict["id"])
                orders.append(
                    {
                        "sales_order_id": order["id"],
                        "status": order["status"],
                        "requested_delivery_date": order["requested_delivery_date"],
                        "pending": pending,
                        "lines": lines,
                        "shipment": ship_dict,
                        "ui_url": ui_href("orders", order["id"]),
                    }
                )
            result["orders"] = orders

        return result


# Namespace for backward compatibility
customer_service = SimpleNamespace(
    find_customers=find_customers,
    create_customer=create_customer,
    update_customer=update_customer,
    get_customer_details=get_customer_details,
)
CustomerService = customer_service
