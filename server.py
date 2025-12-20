import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from db import dict_rows, generate_id, get_connection, init_db


# HTTP-based MCP server using FastMCP with stateless JSON responses.
# Allow all hosts/origins so ngrok tunnels work (demo-only; tighten for prod).
mcp = FastMCP(
    "duck-demo",
    host="0.0.0.0",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    ),
)

# Ensure schema exists at startup.
init_db()


@contextmanager
def db_conn() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def load_item(conn: sqlite3.Connection, sku: str) -> Optional[sqlite3.Row]:
    cur = conn.execute("SELECT * FROM items WHERE sku = ?", (sku,))
    return cur.fetchone()


def stock_summary(conn: sqlite3.Connection, item_id: str) -> Dict[str, Any]:
    rows = dict_rows(
        conn.execute(
            "SELECT warehouse, location, on_hand, reserved FROM stock WHERE item_id = ?",
            (item_id,),
        )
    )
    on_hand = sum(r["on_hand"] for r in rows)
    reserved = sum(r["reserved"] for r in rows)
    return {
        "item_id": item_id,
        "on_hand_total": on_hand,
        "reserved_total": reserved,
        "available_total": on_hand - reserved,
        "by_location": rows,
    }


def compute_pricing(conn: sqlite3.Connection, sales_order_id: str) -> Dict[str, Any]:
    cur = conn.execute(
        "SELECT sol.qty, i.sku FROM sales_order_lines sol JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?",
        (sales_order_id,),
    )
    lines = cur.fetchall()
    if not lines:
        raise ValueError("Sales order has no lines")
    unit_price = 12.0
    line_totals = []
    total_qty = 0
    subtotal = 0.0
    for row in lines:
        qty = float(row["qty"])
        total_qty += qty
        line_total = qty * unit_price
        subtotal += line_total
        line_totals.append({"sku": row["sku"], "qty": qty, "unit_price": unit_price, "line_total": line_total})
    discount = 0.05 * subtotal if total_qty >= 24 else 0.0
    shipping = 0.0 if total_qty >= 24 or subtotal >= 300 else 20.0
    total = subtotal - discount + shipping
    conn.execute(
        "REPLACE INTO sales_order_pricing (sales_order_id, currency, subtotal, discount, shipping, total) VALUES (?, ?, ?, ?, ?, ?)",
        (sales_order_id, "EUR", subtotal, discount, shipping, total),
    )
    conn.commit()
    return {
        "sales_order_id": sales_order_id,
        "pricing": {
            "currency": "EUR",
            "lines": line_totals,
            "discounts": []
            if discount == 0
            else [
                {"type": "volume", "description": "24+ units discount", "amount": -discount}
            ],
            "shipping": {"amount": shipping, "description": "Free shipping threshold" if shipping == 0 else "Flat shipping"},
            "total": total,
        },
    }


def quote_options(conn: sqlite3.Connection, sku: str, qty: int, need_by: Optional[str], allowed_subs: List[str]) -> Dict[str, Any]:
    item = load_item(conn, sku)
    if not item:
        raise ValueError("Unknown item")
    summary = stock_summary(conn, item["id"])
    available = summary["available_total"]
    options: List[Dict[str, Any]] = []
    if sku == "ELVIS-DUCK-20CM" and qty >= 24 and (not need_by or need_by <= "2026-01-10"):
        sub_item = None
        if allowed_subs:
            for s in allowed_subs:
                row = load_item(conn, s)
                if row:
                    sub_item = row
                    break
        if sub_item:
            sub_summary = stock_summary(conn, sub_item["id"])
            if sub_summary["available_total"] >= 12:
                options.append(
                    {
                        "option_id": "OPT-1",
                        "summary": "Ship 12 Elvis + 12 Marilyn to arrive by Jan 10",
                        "lines": [
                            {"sku": sku, "qty": 12, "source": "stock"},
                            {"sku": sub_item["sku"], "qty": 12, "source": "stock"},
                        ],
                        "can_arrive_by": "2026-01-10",
                        "notes": "All stock available now.",
                    }
                )
        if available >= 12:
            options.append(
                {
                    "option_id": "OPT-2",
                    "summary": "Split shipment: 12 Elvis by Jan 10, remaining 12 Elvis by Jan 12",
                    "lines": [
                        {"sku": sku, "qty": 12, "source": "stock", "shipment": "S1"},
                        {"sku": sku, "qty": qty - 12, "source": "production", "shipment": "S2"},
                    ],
                    "can_arrive_by": "2026-01-12",
                    "notes": "Production earliest completion Jan 11; delivery Jan 12.",
                }
            )
        options.append(
            {
                "option_id": "OPT-3",
                "summary": "Ship all Elvis as one shipment arriving by Jan 12",
                "lines": [{"sku": sku, "qty": qty, "source": "stock+production"}],
                "can_arrive_by": "2026-01-12",
                "notes": "Not possible by Jan 10.",
            }
        )
    else:
        options.append(
            {
                "option_id": "OPT-STD",
                "summary": f"Ship {qty} x {sku}",
                "lines": [{"sku": sku, "qty": qty, "source": "stock" if available >= qty else "stock+production"}],
                "can_arrive_by": need_by or "asap",
                "notes": "Based on current stock snapshot.",
            }
        )
    return {"options": options}


def reserve_stock(conn: sqlite3.Connection, reference_id: str, reservations: List[Dict[str, Any]], reference_type: str = "sales_order") -> Dict[str, Any]:
    reservation_id = generate_id(conn, "RSV", "stock_reservations")
    for res in reservations:
        item = load_item(conn, res["sku"])
        if not item:
            raise ValueError(f"Unknown SKU {res['sku']}")
        conn.execute(
            "INSERT INTO stock_reservations (id, reference_type, reference_id, item_id, qty, warehouse, location) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                reservation_id,
                reference_type,
                reference_id,
                item["id"],
                res["qty"],
                res.get("warehouse"),
                res.get("location"),
            ),
        )
        conn.execute(
            "UPDATE stock SET reserved = reserved + ? WHERE item_id = ? AND warehouse = ? AND location = ?",
            (res["qty"], item["id"], res.get("warehouse"), res.get("location")),
        )
    conn.commit()
    return {"status": "reserved", "reservation_id": reservation_id}


@mcp.tool(name="crm_find_customers")
def find_customers(
    name: Optional[str] = None,
    email: Optional[str] = None,
    company: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Find matching customers. Any provided field is used as a case-insensitive contains filter."""
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

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    sql = f"SELECT id, name, company, email, city FROM customers {where_clause} ORDER BY id LIMIT ?"
    params.append(limit)

    with db_conn() as conn:
        rows = dict_rows(conn.execute(sql, params))
        return {"customers": rows}


@mcp.tool(name="crm_create_customer")
def create_customer(name: str, company: Optional[str] = None, email: Optional[str] = None, city: Optional[str] = None) -> Dict[str, Any]:
    """Create a new customer explicitly."""
    with db_conn() as conn:
        customer_id = generate_id(conn, "CUST", "customers")
        conn.execute(
            "INSERT INTO customers (id, name, company, email, city) VALUES (?, ?, ?, ?, ?)",
            (customer_id, name, company, email, city),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return {"customer_id": customer_id, "customer": dict(row)}


@mcp.tool(name="crm_get_customer_details")
def get_customer_details(customer_id: str, include_orders: bool = True, include_interactions: bool = False) -> Dict[str, Any]:
    """Get customer data plus recent orders/interactions."""
    with db_conn() as conn:
        cust = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not cust:
            raise ValueError("Customer not found")

        result: Dict[str, Any] = {"customer": dict(cust)}

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
                pending = True
                if ship and ship["status"] and ship["status"].lower() == "delivered":
                    pending = False
                elif order["status"] and order["status"].lower() == "draft":
                    pending = True
                orders.append(
                    {
                        "sales_order_id": order["id"],
                        "status": order["status"],
                        "requested_delivery_date": order["requested_delivery_date"],
                        "pending": pending,
                        "lines": lines,
                        "shipment": dict(ship) if ship else None,
                    }
                )
            result["orders"] = orders

        if include_interactions:
            recent = dict_rows(
                conn.execute(
                    "SELECT id, channel, direction, subject, interaction_at FROM interactions WHERE customer_id = ? ORDER BY interaction_at DESC LIMIT 5",
                    (customer_id,),
                ).fetchall()
            )
            result["interactions"] = recent

        return result


@mcp.tool(name="crm_log_interaction")
def log_interaction(
    customer_id: str,
    channel: str,
    direction: str,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    interaction_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Log an inbound or outbound interaction."""
    when = interaction_at or datetime.utcnow().isoformat()
    with db_conn() as conn:
        interaction_id = generate_id(conn, "INT", "interactions")
        conn.execute(
            "INSERT INTO interactions (id, customer_id, channel, direction, subject, body, interaction_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (interaction_id, customer_id, channel, direction, subject, body, when),
        )
        conn.commit()
        return {"interaction_id": interaction_id, "status": "logged"}


@mcp.tool(name="catalog_get_item")
def get_item(sku: str) -> Dict[str, Any]:
    """Fetch an item by SKU."""
    with db_conn() as conn:
        row = load_item(conn, sku)
        if not row:
            raise ValueError("Item not found")
        return dict(row)


@mcp.tool(name="inventory_get_stock_summary")
def get_stock_summary(item_id: Optional[str] = None, sku: Optional[str] = None) -> Dict[str, Any]:
    """Return on-hand, reserved, and available by location for an item."""
    if not item_id and not sku:
        raise ValueError("Provide item_id or sku")
    with db_conn() as conn:
        if sku and not item_id:
            row = load_item(conn, sku)
            if not row:
                raise ValueError("Item not found")
            item_id = row["id"]
        return stock_summary(conn, item_id)  # type: ignore[arg-type]


@mcp.tool(name="sales_quote_options")
def sales_quote_options(
    sku: str,
    qty: int,
    need_by: Optional[str] = None,
    allowed_substitutions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate quote / fulfillment options for a request."""
    with db_conn() as conn:
        return quote_options(conn, sku, qty, need_by, allowed_substitutions or [])


@mcp.tool(name="sales_create_sales_order")
def create_sales_order(
    customer_id: str,
    requested_delivery_date: Optional[str] = None,
    ship_to: Optional[Dict[str, Any]] = None,
    lines: Optional[List[Dict[str, Any]]] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a draft sales order with lines."""
    if not lines:
        raise ValueError("lines required")
    ship_to = ship_to or {}
    with db_conn() as conn:
        so_id = generate_id(conn, "SO", "sales_orders")
        conn.execute(
            "INSERT INTO sales_orders (id, customer_id, requested_delivery_date, ship_to_line1, ship_to_postal_code, ship_to_city, ship_to_country, note, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                so_id,
                customer_id,
                requested_delivery_date,
                ship_to.get("line1"),
                ship_to.get("postal_code"),
                ship_to.get("city"),
                ship_to.get("country"),
                note,
                "draft",
            ),
        )
        line_results = []
        for idx, line in enumerate(lines, start=1):
            item_row = load_item(conn, line["sku"])
            if not item_row:
                raise ValueError(f"Unknown SKU {line['sku']}")
            line_id = f"{so_id}-{idx:02d}"
            conn.execute(
                "INSERT INTO sales_order_lines (id, sales_order_id, item_id, qty) VALUES (?, ?, ?, ?)",
                (line_id, so_id, item_row["id"], float(line["qty"])),
            )
            line_results.append({"line_id": line_id, "sku": line["sku"], "qty": float(line["qty"])} )
        conn.commit()
        return {"sales_order_id": so_id, "status": "draft", "lines": line_results}


@mcp.tool(name="sales_price_sales_order")
def price_sales_order(sales_order_id: str, pricelist: Optional[str] = None) -> Dict[str, Any]:
    """Apply simple pricing logic (12 EUR each, 5% discount for 24+, free shipping over €300)."""
    with db_conn() as conn:
        return compute_pricing(conn, sales_order_id)


@mcp.tool(name="inventory_reserve_stock")
def reserve_stock_tool(
    reference_id: str,
    reservations: List[Dict[str, Any]],
    reason: str = "sales_order",
) -> Dict[str, Any]:
    """Reserve stock for a reference (e.g., sales order)."""
    with db_conn() as conn:
        return reserve_stock(conn, reference_id, reservations, reference_type=reason)


@mcp.tool(name="logistics_create_shipment")
def create_shipment(
    ship_from: Optional[Dict[str, Any]] = None,
    ship_to: Optional[Dict[str, Any]] = None,
    planned_departure: Optional[str] = None,
    planned_arrival: Optional[str] = None,
    packages: Optional[List[Dict[str, Any]]] = None,
    reference: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a planned shipment with basic package contents."""
    ship_from = ship_from or {}
    ship_to = ship_to or {}
    packages = packages or []
    with db_conn() as conn:
        shipment_id = generate_id(conn, "SHIP", "shipments")
        conn.execute(
            "INSERT INTO shipments (id, ship_from_warehouse, ship_to_line1, ship_to_postal_code, ship_to_city, ship_to_country, planned_departure, planned_arrival, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                shipment_id,
                ship_from.get("warehouse"),
                ship_to.get("line1"),
                ship_to.get("postal_code"),
                ship_to.get("city"),
                ship_to.get("country"),
                planned_departure,
                planned_arrival,
                "planned",
            ),
        )

        line_counter = 1
        for pkg in packages:
            for content in pkg.get("contents", []):
                item_row = load_item(conn, content["sku"])
                if not item_row:
                    raise ValueError(f"Unknown SKU {content['sku']}")
                line_id = f"{shipment_id}-{line_counter:02d}"
                conn.execute(
                    "INSERT INTO shipment_lines (id, shipment_id, item_id, qty) VALUES (?, ?, ?, ?)",
                    (line_id, shipment_id, item_row["id"], float(content["qty"])),
                )
                line_counter += 1

        if reference and reference.get("type") == "sales_order" and reference.get("id"):
            conn.execute(
                "INSERT OR IGNORE INTO sales_order_shipments (sales_order_id, shipment_id) VALUES (?, ?)",
                (reference["id"], shipment_id),
            )

        conn.commit()
        return {
            "shipment_id": shipment_id,
            "status": "planned",
            "planned_departure": planned_departure,
            "planned_arrival": planned_arrival,
        }


@mcp.tool(name="sales_link_shipment_to_sales_order")
def link_shipment_to_sales_order(sales_order_id: str, shipment_id: str) -> Dict[str, Any]:
    """Link an existing shipment to a sales order."""
    with db_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sales_order_shipments (sales_order_id, shipment_id) VALUES (?, ?)",
            (sales_order_id, shipment_id),
        )
        conn.commit()
        return {"status": "linked"}


def _render_body(subject: str, context: Optional[Dict[str, Any]]) -> str:
    if not context:
        return f"Draft for {subject}"
    lines = [f"Draft: {subject}", "", "Context:"]
    for key, value in context.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


@mcp.tool(name="sales_draft_email")
def draft_email(
    to: str,
    subject: str,
    body: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Store an email draft for later sending."""
    with db_conn() as conn:
        draft_id = generate_id(conn, "DRAFT", "email_drafts")
        draft_body = body or _render_body(subject, context)
        conn.execute(
            "INSERT INTO email_drafts (id, to_address, subject, body) VALUES (?, ?, ?, ?)",
            (draft_id, to, subject, draft_body),
        )
        conn.commit()
        return {"draft_id": draft_id, "body": draft_body}


@mcp.tool(name="sales_mark_email_sent")
def mark_email_sent(draft_id: str, sent_at: Optional[str] = None) -> Dict[str, Any]:
    """Mark a draft as sent."""
    when = sent_at or datetime.utcnow().isoformat()
    with db_conn() as conn:
        conn.execute(
            "UPDATE email_drafts SET sent_at = ? WHERE id = ?",
            (when, draft_id),
        )
        conn.commit()
        return {"status": "sent", "draft_id": draft_id, "sent_at": when}


@mcp.tool(name="sales_search_sales_orders")
def search_sales_orders(customer_id: Optional[str] = None, limit: int = 5, sort: str = "most_recent") -> Dict[str, Any]:
    """Return recent sales orders for a customer."""
    order_clause = "ORDER BY created_at DESC" if sort == "most_recent" else "ORDER BY id"
    with db_conn() as conn:
        if customer_id:
            cur = conn.execute(
                f"SELECT * FROM sales_orders WHERE customer_id = ? {order_clause} LIMIT ?",
                (customer_id, limit),
            )
        else:
            cur = conn.execute(f"SELECT * FROM sales_orders {order_clause} LIMIT ?", (limit,))
        rows = cur.fetchall()
        sales_orders = []
        for row in rows:
            line_cur = conn.execute(
                "SELECT i.sku, sol.qty FROM sales_order_lines sol JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?",
                (row["id"],),
            )
            lines = dict_rows(line_cur.fetchall())
            summary = ", ".join([f"{l['qty']} x {l['sku']}" for l in lines])
            fulfillment_state = row["status"] or "draft"
            ship_row = conn.execute(
                "SELECT s.status FROM sales_order_shipments sos JOIN shipments s ON s.id = sos.shipment_id WHERE sos.sales_order_id = ? LIMIT 1",
                (row["id"],),
            ).fetchone()
            if ship_row and ship_row["status"]:
                fulfillment_state = ship_row["status"]
            sales_orders.append(
                {
                    "sales_order_id": row["id"],
                    "created_at": row["created_at"],
                    "summary": summary,
                    "fulfillment_state": fulfillment_state,
                    "lines": lines,
                }
            )
        return {"sales_orders": sales_orders}


@mcp.tool(name="logistics_get_shipment_status")
def get_shipment_status(shipment_id: str) -> Dict[str, Any]:
    """Return the status of a shipment."""
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not row:
            raise ValueError("Shipment not found")
        return dict(row)


@mcp.tool(name="production_get_production_order_status")
def get_production_order_status(production_order_id: str) -> Dict[str, Any]:
    """Return status of a production order."""
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM production_orders WHERE id = ?", (production_order_id,)).fetchone()
        if not row:
            raise ValueError("Production order not found")
        return dict(row)


if __name__ == "__main__":
    # Run as HTTP server using the streamable-http transport (host/port come from FastMCP settings).
    mcp.run(transport="streamable-http")
