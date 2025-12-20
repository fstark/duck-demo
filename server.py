import os
import re
import sqlite3
import json
import functools
import logging
import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse, Response

from db import dict_rows, generate_id, get_connection, init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("duck-demo")
DEMO_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "*",
}


def _json(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status_code, headers=DEMO_CORS_HEADERS)


def _cors_preflight(methods: List[str]) -> Response:
    headers = dict(DEMO_CORS_HEADERS)
    headers["Access-Control-Allow-Methods"] = ", ".join(methods)
    return Response(status_code=204, headers=headers)


def _parse_bool(val: Optional[str]) -> bool:
    if val is None:
        return False
    return val.lower() in {"1", "true", "yes", "y", "on"}


# Demo constants (lifted from SPECIFICATION.md) — tweak here to adjust behavior.
PRICING_DEFAULT_UNIT_PRICE = 12.0
PRICING_VOLUME_QTY_THRESHOLD = 24
PRICING_VOLUME_DISCOUNT_PCT = 0.05
PRICING_FREE_SHIPPING_THRESHOLD = 300.0
PRICING_CURRENCY = "EUR"
SUBSTITUTION_PRICE_SLACK_PCT = 0.15  # within ±15% of requested SKU
TRANSIT_DAYS_DEFAULT = 2  # simple default transit lead
PRODUCTION_LEAD_DAYS_DEFAULT = 30  # demo tweak: long lead makes rush impossible
PRODUCTION_LEAD_DAYS_BY_TYPE = {"finished_good": 30}


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


def log_tool(name: str):
    """Decorator to log tool calls with parameters and results for CallToolRequest traceability."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                params_str = json.dumps({"args": args, "kwargs": kwargs}, default=str)
            except Exception:
                params_str = f"args={args}, kwargs={kwargs}"
            logger.info("[CallToolRequest] tool=%s params=%s", name, params_str)
            try:
                result = func(*args, **kwargs)
                try:
                    result_str = json.dumps(result, default=str)
                except Exception:
                    result_str = str(result)
                logger.info("[CallToolResponse] tool=%s result=%s", name, result_str)
                return result
            except Exception as exc:  # pragma: no cover
                logger.exception("[CallToolError] tool=%s error=%s", name, exc)
                raise

        return wrapper

    return decorator


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


def parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def eta_from_days(days: int) -> str:
    return (datetime.utcnow().date() + timedelta(days=days)).isoformat()


def get_unit_price(conn: sqlite3.Connection, item_id: str) -> float:
    row = conn.execute(
        "SELECT unit_price FROM pricelist_lines WHERE item_id = ? ORDER BY pricelist_id LIMIT 1",
        (item_id,),
    ).fetchone()
    return float(row["unit_price"]) if row else PRICING_DEFAULT_UNIT_PRICE


def find_substitutions(
    conn: sqlite3.Connection,
    requested_item: sqlite3.Row,
    allowed_subs: List[str],
    price_slack_pct: float = SUBSTITUTION_PRICE_SLACK_PCT,
) -> List[Dict[str, Any]]:
    base_price = get_unit_price(conn, requested_item["id"])
    lower = base_price * (1 - price_slack_pct)
    upper = base_price * (1 + price_slack_pct)

    candidates = conn.execute(
        "SELECT id, sku, name, type FROM items WHERE type = ? AND id != ?",
        (requested_item["type"], requested_item["id"]),
    ).fetchall()

    filtered: List[Dict[str, Any]] = []
    for cand in candidates:
        if allowed_subs and cand["sku"] not in allowed_subs:
            continue
        cand_price = get_unit_price(conn, cand["id"])
        if not (lower <= cand_price <= upper):
            continue
        cand_stock = stock_summary(conn, cand["id"])
        if cand_stock["available_total"] <= 0:
            continue
        filtered.append(
            {
                "item": dict(cand),
                "unit_price": cand_price,
                "stock": cand_stock,
            }
        )
    return filtered


@mcp.tool(name="inventory_list_items")
@log_tool("inventory_list_items")
def inventory_list_items(in_stock_only: bool = False, limit: int = 50) -> Dict[str, Any]:
    """List items, optionally only those with available stock."""
    with db_conn() as conn:
        base_sql = "SELECT id, sku, name, type FROM items"
        params: List[Any] = []
        if in_stock_only:
            base_sql += " WHERE id IN (SELECT DISTINCT item_id FROM stock WHERE on_hand - reserved > 0)"
        base_sql += " ORDER BY sku LIMIT ?"
        params.append(limit)
        rows = dict_rows(conn.execute(base_sql, params))
        if in_stock_only:
            # attach available totals
            for row in rows:
                summary = stock_summary(conn, row["id"])
                row["available_total"] = summary["available_total"]
        return {"items": rows}


def compute_pricing(conn: sqlite3.Connection, sales_order_id: str) -> Dict[str, Any]:
    cur = conn.execute(
        "SELECT sol.qty, sol.item_id, i.sku FROM sales_order_lines sol JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?",
        (sales_order_id,),
    )
    lines = cur.fetchall()
    if not lines:
        raise ValueError("Sales order has no lines")
    line_totals = []
    total_qty = 0
    subtotal = 0.0
    for row in lines:
        qty = float(row["qty"])
        total_qty += qty
        unit_price = get_unit_price(conn, row["item_id"])
        line_total = qty * unit_price
        subtotal += line_total
        line_totals.append({"sku": row["sku"], "qty": qty, "unit_price": unit_price, "line_total": line_total})

    discount = PRICING_VOLUME_DISCOUNT_PCT * subtotal if total_qty >= PRICING_VOLUME_QTY_THRESHOLD else 0.0
    shipping = 0.0 if subtotal >= PRICING_FREE_SHIPPING_THRESHOLD else 20.0
    total = subtotal - discount + shipping
    conn.execute(
        "REPLACE INTO sales_order_pricing (sales_order_id, currency, subtotal, discount, shipping, total) VALUES (?, ?, ?, ?, ?, ?)",
        (sales_order_id, PRICING_CURRENCY, subtotal, discount, shipping, total),
    )
    conn.commit()
    return {
        "sales_order_id": sales_order_id,
        "pricing": {
            "currency": PRICING_CURRENCY,
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


def load_sales_order_detail(conn: sqlite3.Connection, sales_order_id: str) -> Optional[Dict[str, Any]]:
    order = conn.execute("SELECT * FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
    if not order:
        return None

    lines = dict_rows(
        conn.execute(
            "SELECT i.sku, sol.qty FROM sales_order_lines sol JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?",
            (sales_order_id,),
        ).fetchall()
    )

    pricing_row = conn.execute(
        "SELECT * FROM sales_order_pricing WHERE sales_order_id = ?",
        (sales_order_id,),
    ).fetchone()
    pricing = dict(pricing_row) if pricing_row else compute_pricing(conn, sales_order_id)["pricing"]

    shipments = dict_rows(
        conn.execute(
            "SELECT s.* FROM sales_order_shipments sos JOIN shipments s ON s.id = sos.shipment_id WHERE sos.sales_order_id = ? ORDER BY s.planned_departure",
            (sales_order_id,),
        ).fetchall()
    )

    return {
        "sales_order": dict(order),
        "lines": lines,
        "pricing": pricing,
        "shipments": shipments,
    }


def quote_options(conn: sqlite3.Connection, sku: str, qty: int, need_by: Optional[str], allowed_subs: List[str]) -> Dict[str, Any]:
    item = load_item(conn, sku)
    if not item:
        raise ValueError("Unknown item")

    need_by_dt = parse_date(need_by)
    availability = stock_summary(conn, item["id"])
    available = max(0, availability["available_total"])
    transit_days = TRANSIT_DAYS_DEFAULT
    production_lead_days = PRODUCTION_LEAD_DAYS_BY_TYPE.get(item["type"], PRODUCTION_LEAD_DAYS_DEFAULT)

    options: List[Dict[str, Any]] = []

    def next_id(idx: int) -> str:
        return f"OPT-{idx}"

    def option_eta(lines: List[Dict[str, Any]]) -> str:
        stock_eta: Optional[str] = None
        latest_prod_eta: Optional[str] = None
        for line in lines:
            source = line.get("source", "")
            if "production" in source:
                lead = int(line.get("lead_days", production_lead_days))
                eta_val = eta_from_days(lead + transit_days)
                if latest_prod_eta is None or eta_val > latest_prod_eta:
                    latest_prod_eta = eta_val
            elif "stock" in source:
                stock_eta = eta_from_days(transit_days)
        candidate = latest_prod_eta or stock_eta or eta_from_days(transit_days)
        return candidate

    def add_option(idx: int, summary: str, lines: List[Dict[str, Any]], notes: str) -> None:
        options.append(
            {
                "option_id": next_id(idx),
                "summary": summary,
                "lines": lines,
                "can_arrive_by": option_eta(lines),
                "notes": notes,
            }
        )

    opt_idx = 1

    # Stock-first options for requested SKU
    if available >= qty:
        add_option(
            opt_idx,
            f"Ship {qty} x {sku} from stock",
            [{"sku": sku, "qty": qty, "source": "stock"}],
            "All units available now; using default transit lead.",
        )
        opt_idx += 1
    elif available > 0:
        remaining = qty - available
        add_option(
            opt_idx,
            f"Ship {available} from stock, {remaining} from production",
            [
                {"sku": sku, "qty": available, "source": "stock"},
                {"sku": sku, "qty": remaining, "source": "production"},
            ],
            "Partial stock now; remainder after production lead.",
        )
        opt_idx += 1
    else:
        add_option(
            opt_idx,
            f"Produce and ship {qty} x {sku}",
            [{"sku": sku, "qty": qty, "source": "production"}],
            "No stock available; production required.",
        )
        opt_idx += 1

    # Substitution options based on type and price band.
    substitutions = find_substitutions(conn, item, allowed_subs)
    for sub in substitutions:
        sub_item = sub["item"]
        sub_avail = max(0, sub["stock"]["available_total"])
        if sub_avail <= 0:
            continue
        # If we can cover the shortage by mixing requested stock with substitute stock, surface that first.
        shortage = max(0, qty - available)
        if available > 0 and shortage > 0 and available + sub_avail >= qty:
            fill_qty = qty - available
            lines = [
                {"sku": sku, "qty": available, "source": "stock"},
                {"sku": sub_item["sku"], "qty": fill_qty, "source": "stock"},
            ]
            summary = f"Stock mix: {available} x {sku} + {fill_qty} x {sub_item['sku']}"
            notes = "Mix requested SKU with substitution from stock to meet requested date."
            add_option(opt_idx, summary, lines, notes)
            opt_idx += 1

        if sub_avail >= qty:
            lines = [{"sku": sub_item["sku"], "qty": qty, "source": "stock"}]
            summary = f"Substitute {qty} x {sub_item['sku']} (price-similar)"
            notes = "Within price band and same type; ships from stock."
        else:
            remaining = qty - sub_avail
            sub_prod_lead = PRODUCTION_LEAD_DAYS_BY_TYPE.get(sub_item["type"], PRODUCTION_LEAD_DAYS_DEFAULT)
            lines = [
                {"sku": sub_item["sku"], "qty": sub_avail, "source": "stock"},
                {"sku": sub_item["sku"], "qty": remaining, "source": "production", "lead_days": sub_prod_lead},
            ]
            summary = f"Substitute {sub_avail} stock + {remaining} production of {sub_item['sku']}"
            notes = "Within price band and same type; partial stock, remainder after production."

        add_option(opt_idx, summary, lines, notes)
        opt_idx += 1

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
@log_tool("crm_find_customers")
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
@log_tool("crm_create_customer")
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
@log_tool("crm_get_customer_details")
def get_customer_details(customer_id: str, include_orders: bool = True) -> Dict[str, Any]:
    """Get customer data plus recent orders."""
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

        return result



@mcp.tool(name="catalog_get_item")
@log_tool("catalog_get_item")
def get_item(sku: str) -> Dict[str, Any]:
    """Fetch an item by SKU."""
    with db_conn() as conn:
        row = load_item(conn, sku)
        if not row:
            raise ValueError("Item not found")
        return dict(row)


@mcp.tool(name="catalog_search_items")
@log_tool("catalog_search_items")
def search_items(words: List[str], limit: int = 10, min_score: int = 1) -> Dict[str, Any]:
    """Fuzzy item search via prefix matches on SKU/name tokens, ordered best to worst."""
    normalized = [w.strip().lower() for w in words if w and w.strip()]
    if not normalized:
        raise ValueError("words required")

    def tokens_for(row: sqlite3.Row) -> List[str]:
        raw = f"{row['sku']} {row['name']}".lower()
        return [tok for tok in re.split(r"[^a-z0-9]+", raw) if tok]

    with db_conn() as conn:
        rows = conn.execute("SELECT id, sku, name, type FROM items").fetchall()
        scored: List[Dict[str, Any]] = []
        for row in rows:
            token_set = set(tokens_for(row))
            matched = [w for w in normalized if any(tok.startswith(w) for tok in token_set)]
            score = len(matched)
            if score >= min_score:
                scored.append({"item": dict(row), "score": score, "matched_words": matched})

        scored.sort(key=lambda entry: (-entry["score"], entry["item"]["sku"]))
        return {"items": scored[:limit], "query": normalized}


@mcp.tool(name="inventory_get_stock_summary")
@log_tool("inventory_get_stock_summary")
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
@log_tool("sales_quote_options")
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
@log_tool("sales_create_sales_order")
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
@log_tool("sales_price_sales_order")
def price_sales_order(sales_order_id: str, pricelist: Optional[str] = None) -> Dict[str, Any]:
    """Apply simple pricing logic (12 EUR each, 5% discount for 24+, free shipping over €300)."""
    with db_conn() as conn:
        return compute_pricing(conn, sales_order_id)


@mcp.tool(name="inventory_reserve_stock")
@log_tool("inventory_reserve_stock")
def reserve_stock_tool(
    reference_id: str,
    reservations: List[Dict[str, Any]],
    reason: str = "sales_order",
) -> Dict[str, Any]:
    """Reserve stock for a reference (e.g., sales order)."""
    with db_conn() as conn:
        return reserve_stock(conn, reference_id, reservations, reference_type=reason)


@mcp.tool(name="logistics_create_shipment")
@log_tool("logistics_create_shipment")
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
@log_tool("sales_link_shipment_to_sales_order")
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
@log_tool("sales_draft_email")
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
@log_tool("sales_mark_email_sent")
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


@mcp.tool(name="sales_list_email_drafts")
@log_tool("sales_list_email_drafts")
def list_email_drafts(sent_only: bool = False, include_body: bool = False, limit: int = 20) -> Dict[str, Any]:
    """Fetch email drafts. Defaults to unsent; set sent_only to True to fetch sent drafts."""
    with db_conn() as conn:
        if sent_only:
            rows = conn.execute(
                "SELECT id, to_address, subject, body, sent_at FROM email_drafts WHERE sent_at IS NOT NULL ORDER BY sent_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, to_address, subject, body, sent_at FROM email_drafts WHERE sent_at IS NULL ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        drafts = []
        for row in rows:
            entry = {
                "draft_id": row["id"],
                "to": row["to_address"],
                "subject": row["subject"],
                "sent_at": row["sent_at"],
            }
            if include_body:
                entry["body"] = row["body"]
            drafts.append(entry)
        return {"drafts": drafts}


@mcp.tool(name="sales_search_sales_orders")
@log_tool("sales_search_sales_orders")
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
@log_tool("logistics_get_shipment_status")
def get_shipment_status(shipment_id: str) -> Dict[str, Any]:
    """Return the status of a shipment."""
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not row:
            raise ValueError("Shipment not found")
        return dict(row)


@mcp.tool(name="production_get_production_order_status")
@log_tool("production_get_production_order_status")
def get_production_order_status(production_order_id: str) -> Dict[str, Any]:
    """Return status of a production order."""
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM production_orders WHERE id = ?", (production_order_id,)).fetchone()
        if not row:
            raise ValueError("Production order not found")
        return dict(row)


# --- Minimal REST API for demo UI (read-only, no auth) ---


@mcp.custom_route("/api/health", methods=["GET", "OPTIONS"])
async def api_health(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    return _json({"status": "ok"})


@mcp.custom_route("/api/customers", methods=["GET", "OPTIONS"])
async def api_customers(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    limit = int(qp.get("limit", 20))
    result = find_customers(
        name=qp.get("name"),
        email=qp.get("email"),
        company=qp.get("company"),
        city=qp.get("city"),
        limit=limit,
    )
    return _json(result)


@mcp.custom_route("/api/items", methods=["GET", "OPTIONS"])
async def api_items(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    limit = int(qp.get("limit", 50))
    in_stock_only = _parse_bool(qp.get("in_stock_only"))
    result = inventory_list_items(in_stock_only=in_stock_only, limit=limit)
    return _json(result)


@mcp.custom_route("/api/items/{sku}/stock", methods=["GET", "OPTIONS"])
async def api_item_stock(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    sku = request.path_params.get("sku")
    try:
        result = get_stock_summary(sku=sku)
        return _json(result)
    except Exception as exc:  # pragma: no cover
        return _json({"error": str(exc)}, status_code=404)


@mcp.custom_route("/api/sales-orders", methods=["GET", "OPTIONS"])
async def api_sales_orders(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    limit = int(qp.get("limit", 20))
    result = search_sales_orders(
        customer_id=qp.get("customer_id"),
        limit=limit,
        sort=qp.get("sort", "most_recent"),
    )
    return _json(result)


@mcp.custom_route("/api/sales-orders/{order_id}", methods=["GET", "OPTIONS"])
async def api_sales_order_detail(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    order_id = request.path_params.get("order_id")
    with db_conn() as conn:
        detail = load_sales_order_detail(conn, order_id)
    if not detail:
        return _json({"error": "Not found"}, status_code=404)
    return _json(detail)


@mcp.custom_route("/api/shipments/{shipment_id}", methods=["GET", "OPTIONS"])
async def api_shipment(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    shipment_id = request.path_params.get("shipment_id")
    try:
        result = get_shipment_status(shipment_id)
        return _json(result)
    except Exception as exc:  # pragma: no cover
        return _json({"error": str(exc)}, status_code=404)


@mcp.custom_route("/api/production-orders/{production_id}", methods=["GET", "OPTIONS"])
async def api_production(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    production_id = request.path_params.get("production_id")
    try:
        result = get_production_order_status(production_id)
        return _json(result)
    except Exception as exc:  # pragma: no cover
        return _json({"error": str(exc)}, status_code=404)


@mcp.custom_route("/api/quotes", methods=["GET", "OPTIONS"])
async def api_quotes(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    sku = qp.get("sku")
    qty = qp.get("qty")
    if not sku or not qty:
        return _json({"error": "sku and qty are required"}, status_code=400)
    try:
        qty_int = int(qty)
    except ValueError:
        return _json({"error": "qty must be an integer"}, status_code=400)

    allowed_subs = []
    subs_param = qp.get("subs")
    if subs_param:
        allowed_subs = [s.strip() for s in subs_param.split(",") if s.strip()]

    result = sales_quote_options(
        sku=sku,
        qty=qty_int,
        need_by=qp.get("need_by"),
        allowed_substitutions=allowed_subs,
    )
    return _json(result)

if __name__ == "__main__":
    # Run as HTTP server using the streamable-http transport (host/port come from FastMCP settings).
    mcp.run(transport="streamable-http")
