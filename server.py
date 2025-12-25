import os
import re
import sqlite3
import json
import functools
import logging
import re
from urllib.parse import quote
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
UI_BASE = os.getenv("UI_BASE", "http://127.0.0.1:5173")


def ui_href(page: str, identifier: str) -> str:
    safe_id = quote(str(identifier), safe="")
    return f"{UI_BASE}#/{page}/{safe_id}"


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
            "SELECT id, warehouse, location, on_hand FROM stock WHERE item_id = ?",
            (item_id,),
        )
    )
    on_hand = sum(r["on_hand"] for r in rows)
    return {
        "item_id": item_id,
        "on_hand_total": on_hand,
        "available_total": on_hand,
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
    item_row = conn.execute("SELECT unit_price FROM items WHERE id = ?", (item_id,)).fetchone()
    if item_row and item_row["unit_price"] is not None:
        return float(item_row["unit_price"])
    return PRICING_DEFAULT_UNIT_PRICE


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
        base_sql = "SELECT id, sku, name, type, unit_price FROM items"
        params: List[Any] = []
        if in_stock_only:
            base_sql += " WHERE id IN (SELECT DISTINCT item_id FROM stock WHERE on_hand > 0)"
        base_sql += " ORDER BY sku LIMIT ?"
        params.append(limit)
        rows = dict_rows(conn.execute(base_sql, params))
        # Always attach stock totals for all items
        for row in rows:
            summary = stock_summary(conn, row["id"])
            row["on_hand_total"] = summary["on_hand_total"]
            row["available_total"] = summary["available_total"]
        for row in rows:
            row["ui_url"] = ui_href("items", row["sku"])
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
    return {
        "sales_order_id": sales_order_id,
        "pricing": {
            "currency": PRICING_CURRENCY,
            "subtotal": subtotal,
            "discount": discount,
            "lines": line_totals,
            "discounts": []
            if discount == 0
            else [
                {"type": "volume", "description": "24+ units discount", "amount": -discount}
            ],
            "shipping": {"amount": shipping, "description": "Free shipping threshold" if shipping == 0 else "Flat shipping"},
            "total": total,
            "subtotal": subtotal,
            "discount": discount,
        },
    }


def load_sales_order_detail(conn: sqlite3.Connection, sales_order_id: str) -> Optional[Dict[str, Any]]:
    order = conn.execute("SELECT * FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
    if not order:
        return None

    # Fetch customer information
    customer = conn.execute("SELECT * FROM customers WHERE id = ?", (order["customer_id"],)).fetchone()
    customer_dict = dict(customer) if customer else None
    if customer_dict:
        customer_dict["ui_url"] = ui_href("customers", customer_dict["id"])

    lines = dict_rows(
        conn.execute(
            "SELECT i.sku, sol.qty FROM sales_order_lines sol JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?",
            (sales_order_id,),
        ).fetchall()
    )

    pricing = compute_pricing(conn, sales_order_id)["pricing"]

    shipments = dict_rows(
        conn.execute(
            "SELECT s.* FROM sales_order_shipments sos JOIN shipments s ON s.id = sos.shipment_id WHERE sos.sales_order_id = ? ORDER BY s.planned_departure",
            (sales_order_id,),
        ).fetchall()
    )

    order_dict = dict(order)
    order_dict["ui_url"] = ui_href("orders", sales_order_id)
    for shipment in shipments:
        shipment["ui_url"] = ui_href("shipments", shipment["id"])

    return {
        "sales_order": order_dict,
        "customer": customer_dict,
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





@mcp.tool(name="get_statistics")
@log_tool("get_statistics")
def get_statistics(
    entity: str,
    metric: str = "count",
    group_by: Optional[str] = None,
    field: Optional[str] = None,
    status: Optional[str] = None,
    item_type: Optional[str] = None,
    warehouse: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Get flexible statistics for any entity with optional grouping and filtering.
    
    Args:
        entity: The entity to query (customers, sales_orders, items, stock, production_orders, shipments)
        metric: The metric to calculate (count, sum, avg, min, max)
        group_by: Optional field to group by (status, type, city, warehouse, etc.)
        field: Field name for sum/avg/min/max operations (qty, on_hand, unit_price, etc.)
        status: Filter by status (for sales_orders, production_orders, shipments)
        item_type: Filter by item type (for items)
        warehouse: Filter by warehouse (for stock)
        city: Filter by city (for customers)
        limit: Maximum results for grouped queries
    
    Examples:
        - Total customers: entity="customers", metric="count"
        - Sales orders by status: entity="sales_orders", metric="count", group_by="status"
        - Total stock by warehouse: entity="stock", metric="sum", field="on_hand", group_by="warehouse"
        - Items by type: entity="items", metric="count", group_by="type"
    """
    
    # Map entities to tables and valid fields
    entity_config = {
        "customers": {"table": "customers", "valid_fields": ["id"], "valid_groups": ["city", "company"]},
        "sales_orders": {"table": "sales_orders", "valid_fields": ["id"], "valid_groups": ["status", "customer_id"]},
        "items": {"table": "items", "valid_fields": ["unit_price"], "valid_groups": ["type"]},
        "stock": {"table": "stock", "valid_fields": ["on_hand"], "valid_groups": ["warehouse", "location", "item_id"]},
        "production_orders": {"table": "production_orders", "valid_fields": ["qty"], "valid_groups": ["status", "item_id"]},
        "shipments": {"table": "shipments", "valid_fields": ["id"], "valid_groups": ["status"]},
    }
    
    if entity not in entity_config:
        return {"error": f"Invalid entity: {entity}. Valid options: {', '.join(entity_config.keys())}"}
    
    table = entity_config[entity]["table"]
    
    # Build the query
    if metric == "count":
        select_clause = "COUNT(*) as value"
    elif metric in ["sum", "avg", "min", "max"]:
        if not field:
            return {"error": f"Field is required for {metric} operation"}
        if field not in entity_config[entity]["valid_fields"]:
            return {"error": f"Invalid field '{field}' for entity '{entity}'. Valid: {entity_config[entity]['valid_fields']}"}
        select_clause = f"{metric.upper()}({field}) as value"
    else:
        return {"error": f"Invalid metric: {metric}. Valid options: count, sum, avg, min, max"}
    
    # Build filters
    filters = []
    params: List[Any] = []
    
    if status:
        filters.append("status = ?")
        params.append(status)
    if item_type:
        filters.append("type = ?")
        params.append(item_type)
    if warehouse:
        filters.append("warehouse = ?")
        params.append(warehouse)
    if city:
        filters.append("city = ?")
        params.append(city)
    
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    
    with db_conn() as conn:
        if group_by:
            if group_by not in entity_config[entity]["valid_groups"]:
                return {"error": f"Invalid group_by '{group_by}' for entity '{entity}'. Valid: {entity_config[entity]['valid_groups']}"}
            
            sql = f"SELECT {group_by}, {select_clause} FROM {table} {where_clause} GROUP BY {group_by} ORDER BY value DESC LIMIT ?"
            params.append(limit)
            rows = dict_rows(conn.execute(sql, params))
            return {"entity": entity, "metric": metric, "group_by": group_by, "results": rows}
        else:
            sql = f"SELECT {select_clause} FROM {table} {where_clause}"
            result = conn.execute(sql, params).fetchone()
            return {"entity": entity, "metric": metric, "value": result["value"] if result["value"] is not None else 0}


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
        for row in rows:
            row["ui_url"] = ui_href("customers", row["id"])
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
        row_dict = dict(row)
        row_dict["ui_url"] = ui_href("customers", customer_id)
        return {"customer_id": customer_id, "customer": row_dict}


@mcp.tool(name="crm_get_customer_details")
@log_tool("crm_get_customer_details")
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
    """Fuzzy item search via containment on SKU/name tokens, ordered best to worst (demo-friendly)."""
    normalized_phrases = [w.strip().lower() for w in words if w and w.strip()]

    def phrase_tokens(phrase: str) -> List[str]:
        return [tok for tok in re.split(r"[^a-z0-9]+", phrase) if tok]

    query_tokens: List[str] = []
    for phrase in normalized_phrases:
        query_tokens.extend(phrase_tokens(phrase))

    if not query_tokens:
        raise ValueError("words required")

    def tokens_for(row: sqlite3.Row) -> List[str]:
        raw = f"{row['sku']} {row['name']}".lower()
        return [tok for tok in re.split(r"[^a-z0-9]+", raw) if tok]

    with db_conn() as conn:
        rows = conn.execute("SELECT id, sku, name, type, unit_price FROM items").fetchall()
        scored: List[Dict[str, Any]] = []
        for row in rows:
            token_set = set(tokens_for(row))
            matched = [w for w in query_tokens if any(w in tok for tok in token_set)]

            # Simple scoring: count matches; containment only (demo convenience).
            score = len(matched)
            if score >= min_score:
                item_dict = dict(row)
                item_dict["ui_url"] = ui_href("items", item_dict["sku"])
                scored.append({"item": item_dict, "score": score, "matched_words": matched})

        scored.sort(key=lambda entry: (-entry["score"], entry["item"]["sku"]))
        return {"items": scored[:limit], "query": query_tokens}


@mcp.tool(name="inventory_get_stock_summary")
@log_tool("inventory_get_stock_summary")
def get_stock_summary(item_id: Optional[str] = None, sku: Optional[str] = None) -> Dict[str, Any]:
    """Return on-hand and available by location for an item."""
    if not item_id and not sku:
        raise ValueError("Provide item_id or sku")
    with db_conn() as conn:
        if sku and not item_id:
            row = load_item(conn, sku)
            if not row:
                raise ValueError("Item not found")
            item_id = row["id"]
        elif item_id and not sku:
            sku_row = conn.execute("SELECT sku FROM items WHERE id = ?", (item_id,)).fetchone()
            sku = sku_row["sku"] if sku_row else str(item_id)
        summary = stock_summary(conn, item_id)  # type: ignore[arg-type]
        summary["ui_url"] = ui_href("items", sku or item_id)
        return summary


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
        return {"sales_order_id": so_id, "status": "draft", "lines": line_results, "ui_url": ui_href("orders", so_id)}


@mcp.tool(name="sales_price_sales_order")
@log_tool("sales_price_sales_order")
def price_sales_order(sales_order_id: str, pricelist: Optional[str] = None) -> Dict[str, Any]:
    """Apply simple pricing logic (12 EUR each, 5% discount for 24+, free shipping over €300)."""
    with db_conn() as conn:
        return compute_pricing(conn, sales_order_id)


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
            "ui_url": ui_href("shipments", shipment_id),
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
            
            # Get customer info
            customer_row = conn.execute(
                "SELECT name, company FROM customers WHERE id = ?",
                (row["customer_id"],),
            ).fetchone()
            customer_name = customer_row["name"] if customer_row else None
            customer_company = customer_row["company"] if customer_row else None
            
            # Compute pricing on-the-fly
            pricing_data = compute_pricing(conn, row["id"])["pricing"]
            
            sales_orders.append(
                {
                    "sales_order_id": row["id"],
                    "customer_id": row["customer_id"],
                    "customer_name": customer_name,
                    "customer_company": customer_company,
                    "created_at": row["created_at"],
                    "summary": summary,
                    "fulfillment_state": fulfillment_state,
                    "lines": lines,
                    "total": pricing_data["total"],
                    "currency": pricing_data["currency"],
                    "ui_url": ui_href("orders", row["id"]),
                }
            )
        return {"sales_orders": sales_orders}


@mcp.tool(name="sales_get_sales_order")
@log_tool("sales_get_sales_order")
def get_sales_order(sales_order_id: str) -> Dict[str, Any]:
    """Return a sales order with lines, pricing, and linked shipments."""
    with db_conn() as conn:
        detail = load_sales_order_detail(conn, sales_order_id)
    if not detail:
        raise ValueError("Sales order not found")
    return detail


@mcp.tool(name="logistics_get_shipment_status")
@log_tool("logistics_get_shipment_status")
def get_shipment_status(shipment_id: str) -> Dict[str, Any]:
    """Return the status of a shipment."""
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not row:
            raise ValueError("Shipment not found")
        data = dict(row)
        data["ui_url"] = ui_href("shipments", shipment_id)
        
        # Get associated sales orders
        orders_query = """
            SELECT 
                so.id as sales_order_id,
                so.customer_id,
                c.name as customer_name,
                c.company as customer_company,
                so.status
            FROM sales_order_shipments sos
            JOIN sales_orders so ON sos.sales_order_id = so.id
            LEFT JOIN customers c ON so.customer_id = c.id
            WHERE sos.shipment_id = ?
        """
        orders = dict_rows(conn.execute(orders_query, (shipment_id,)).fetchall())
        data["sales_orders"] = orders
        
        return data


@mcp.tool(name="production_get_statistics")
@log_tool("production_get_statistics")
def get_production_statistics() -> Dict[str, Any]:
    """Get production statistics including total production orders and breakdown by status."""
    with db_conn() as conn:
        # Total production orders
        total_production = conn.execute("SELECT COUNT(*) as count FROM production_orders").fetchone()["count"]
        
        # Production orders by status
        status_rows = dict_rows(
            conn.execute(
                "SELECT status, COUNT(*) as count FROM production_orders GROUP BY status ORDER BY count DESC"
            )
        )
        
        # Total quantity being produced
        total_qty = conn.execute("SELECT SUM(qty) as total FROM production_orders").fetchone()["total"] or 0
        
        # Top items being produced
        top_items = dict_rows(
            conn.execute(
                """SELECT i.sku, i.name, SUM(po.qty) as total_qty, COUNT(*) as order_count
                FROM production_orders po
                JOIN items i ON po.item_id = i.id
                GROUP BY i.id, i.sku, i.name
                ORDER BY total_qty DESC
                LIMIT 10"""
            )
        )
        
        # Upcoming production (next 60 days)
        upcoming = dict_rows(
            conn.execute(
                """SELECT i.sku, i.name, po.qty, po.eta_finish, po.status
                FROM production_orders po
                JOIN items i ON po.item_id = i.id
                WHERE po.eta_finish >= date('now') AND po.eta_finish <= date('now', '+60 days')
                ORDER BY po.eta_finish
                LIMIT 20"""
            )
        )
        
        return {
            "total_production_orders": total_production,
            "production_orders_by_status": status_rows,
            "total_quantity_in_production": total_qty,
            "top_items_in_production": top_items,
            "upcoming_production": upcoming,
        }


@mcp.tool(name="production_get_production_order_status")
@log_tool("production_get_production_order_status")
def get_production_order_status(production_order_id: str) -> Dict[str, Any]:
    """Return status of a production order."""
    with db_conn() as conn:
        query = """
            SELECT 
                po.*,
                i.name as item_name,
                i.sku as item_sku,
                i.type as item_type
            FROM production_orders po
            LEFT JOIN items i ON po.item_id = i.id
            WHERE po.id = ?
        """
        row = conn.execute(query, (production_order_id,)).fetchone()
        if not row:
            return {"error": "Production order not found", "production_order_id": production_order_id}
        
        result = dict(row)
        result["ui_url"] = ui_href("production-orders", production_order_id)
        
        # Get production operations for this order
        operations = dict_rows(conn.execute(
            """SELECT * FROM production_operations
               WHERE production_order_id = ?
               ORDER BY sequence_order""",
            (production_order_id,)
        ))
        result["operations"] = operations
        
        # If recipe-based production order, include recipe details
        if result.get("recipe_id"):
            recipe = conn.execute(
                """SELECT r.*, i.sku as output_sku, i.name as output_name
                   FROM recipes r
                   JOIN items i ON r.output_item_id = i.id
                   WHERE r.id = ?""",
                (result["recipe_id"],)
            ).fetchone()
            
            if recipe:
                result["recipe"] = dict(recipe)
                
                # Get recipe ingredients
                ingredients = dict_rows(conn.execute(
                    """SELECT ri.*, i.sku as ingredient_sku, i.name as ingredient_name, i.uom as ingredient_uom
                       FROM recipe_ingredients ri
                       JOIN items i ON ri.input_item_id = i.id
                       WHERE ri.recipe_id = ?""",
                    (result["recipe_id"],)
                ))
                result["recipe"]["ingredients"] = ingredients
                
                # Get recipe operations template
                recipe_operations = dict_rows(conn.execute(
                    """SELECT * FROM recipe_operations
                       WHERE recipe_id = ?
                       ORDER BY sequence_order""",
                    (result["recipe_id"],)
                ))
                result["recipe"]["operations"] = recipe_operations
        
        return result


@mcp.tool(name="production_find_orders_by_date_range")
@log_tool("production_find_orders_by_date_range")
def find_production_orders_by_date_range(
    start_date: str,
    end_date: str,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
        Retrieve all production orders scheduled to finish within a specific date range.
        Useful for:
        Determine the most produced items within a specific timeframe.
        Analyze production scheduling and capacity utilization.
        Identify trends in production focus or priorities.
    Parameters:
        Start Date: Beginning of the date range in YYYY-MM-DD format.
        End Date: End of the date range in YYYY-MM-DD format.
        Limit: Maximum number of production order records to return.
    """
    with db_conn() as conn:
        query = """
            SELECT 
                po.*,
                i.name as item_name,
                i.sku as item_sku,
                i.type as item_type
            FROM production_orders po
            LEFT JOIN items i ON po.item_id = i.id
            WHERE po.eta_finish >= ? AND po.eta_finish <= ?
            ORDER BY po.eta_finish
            LIMIT ?
        """
        rows = conn.execute(query, (start_date, end_date, limit)).fetchall()
        return [dict(row) for row in rows]


@mcp.tool(name="inventory_check_availability")
@log_tool("inventory_check_availability")
def inventory_check_availability(item_sku: str, qty_required: float) -> Dict[str, Any]:
    """
    Check if sufficient inventory is available for an item.
    Returns availability status, on_hand total, and shortfall if any.
    
    Parameters:
        item_sku: The SKU of the item to check
        qty_required: The quantity needed
    """
    with db_conn() as conn:
        item = load_item(conn, item_sku)
        if not item:
            raise ValueError(f"Item {item_sku} not found")
        
        summary = stock_summary(conn, item["id"])
        available = summary["available_total"]
        is_available = available >= qty_required
        shortfall = 0.0 if is_available else (qty_required - available)
        
        return {
            "item_sku": item_sku,
            "item_name": item["name"],
            "qty_required": qty_required,
            "qty_available": available,
            "is_available": is_available,
            "shortfall": shortfall,
            "stock_locations": summary["by_location"]
        }


@mcp.tool(name="recipe_list")
@log_tool("recipe_list")
def recipe_list(output_item_sku: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    """
    List recipes, optionally filtering by output item SKU.
    
    Parameters:
        output_item_sku: Optional SKU to filter recipes that produce this item
        limit: Maximum number of recipes to return
    """
    with db_conn() as conn:
        if output_item_sku:
            item = load_item(conn, output_item_sku)
            if not item:
                raise ValueError(f"Item {output_item_sku} not found")
            rows = dict_rows(conn.execute(
                """SELECT r.*, i.sku as output_sku, i.name as output_name 
                   FROM recipes r 
                   JOIN items i ON r.output_item_id = i.id 
                   WHERE r.output_item_id = ?
                   ORDER BY r.id LIMIT ?""",
                (item["id"], limit)
            ))
        else:
            rows = dict_rows(conn.execute(
                """SELECT r.*, i.sku as output_sku, i.name as output_name 
                   FROM recipes r 
                   JOIN items i ON r.output_item_id = i.id 
                   ORDER BY r.id LIMIT ?""",
                (limit,)
            ))
        
        return {"recipes": rows}


@mcp.tool(name="recipe_get")
@log_tool("recipe_get")
def recipe_get(recipe_id: str) -> Dict[str, Any]:
    """
    Get detailed recipe information including ingredients and operations.
    
    Parameters:
        recipe_id: The recipe ID (e.g., 'RCP-ELVIS-20')
    """
    with db_conn() as conn:
        # Get recipe header
        recipe = conn.execute(
            """SELECT r.*, i.sku as output_sku, i.name as output_name, i.type as output_type
               FROM recipes r 
               JOIN items i ON r.output_item_id = i.id 
               WHERE r.id = ?""",
            (recipe_id,)
        ).fetchone()
        
        if not recipe:
            raise ValueError(f"Recipe {recipe_id} not found")
        
        result = dict(recipe)
        
        # Get ingredients
        ingredients = dict_rows(conn.execute(
            """SELECT ri.*, i.sku as ingredient_sku, i.name as ingredient_name, i.uom as ingredient_uom
               FROM recipe_ingredients ri
               JOIN items i ON ri.input_item_id = i.id
               WHERE ri.recipe_id = ?""",
            (recipe_id,)
        ))
        result["ingredients"] = ingredients
        
        # Get operations
        operations = dict_rows(conn.execute(
            """SELECT * FROM recipe_operations 
               WHERE recipe_id = ?
               ORDER BY sequence_order""",
            (recipe_id,)
        ))
        result["operations"] = operations
        
        return result


@mcp.tool(name="production_create_order")
@log_tool("production_create_order")
def production_create_order(
    recipe_id: str,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new production order to execute one batch of a recipe.
    Checks ingredient availability and creates order with 'planned' status.
    Creates production operations for each step in the recipe.
    
    Parameters:
        recipe_id: The recipe to execute (e.g., 'RCP-ELVIS-20')
        notes: Optional notes for the production order
    """
    with db_conn() as conn:
        # Get recipe details
        recipe_data = recipe_get(recipe_id)
        
        # Check ingredient availability for one batch
        shortfalls = []
        for ing in recipe_data["ingredients"]:
            qty_needed = ing["input_qty"]
            check = inventory_check_availability(ing["ingredient_sku"], qty_needed)
            if not check["is_available"]:
                shortfalls.append({
                    "ingredient_sku": ing["ingredient_sku"],
                    "ingredient_name": ing["ingredient_name"],
                    "qty_needed": qty_needed,
                    "qty_available": check["qty_available"],
                    "shortfall": check["shortfall"]
                })
        
        # Determine initial status
        status = "waiting" if shortfalls else "ready"
        
        # Calculate dates
        prod_time_days = recipe_data["production_time_hours"] / 24.0
        eta_finish = (datetime.utcnow().date() + timedelta(days=1 + int(prod_time_days))).isoformat()
        eta_ship = (datetime.utcnow().date() + timedelta(days=2 + int(prod_time_days))).isoformat()
        
        # Create production order
        order_id = generate_id("MO")
        conn.execute(
            """INSERT INTO production_orders 
               (id, recipe_id, item_id, status, eta_finish, eta_ship)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (order_id, recipe_id, recipe_data["output_item_id"], status, eta_finish, eta_ship)
        )
        
        # Create production operations from recipe operations
        for op in recipe_data["operations"]:
            pop_id = generate_id("POP")
            conn.execute(
                """INSERT INTO production_operations
                   (id, production_order_id, recipe_operation_id, sequence_order, operation_name, duration_hours, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pop_id, order_id, op["id"], op["sequence_order"], op["operation_name"], op["duration_hours"], "pending")
            )
        
        conn.commit()
        
        return {
            "production_order_id": order_id,
            "recipe_id": recipe_id,
            "output_item": recipe_data["output_sku"],
            "output_qty": recipe_data["output_qty"],
            "status": status,
            "eta_finish": eta_finish,
            "eta_ship": eta_ship,
            "ingredient_shortfalls": shortfalls,
            "ui_url": ui_href("production-orders", order_id)
        }



@mcp.tool(name="production_start_order")
@log_tool("production_start_order")
def production_start_order(production_order_id: str) -> Dict[str, Any]:
    """
    Start a production order (change status from 'ready' to 'in_progress').
    Sets current_operation to the first operation in the recipe.
    
    Parameters:
        production_order_id: The production order ID (e.g., 'MO-1000')
    """
    with db_conn() as conn:
        order = conn.execute(
            "SELECT * FROM production_orders WHERE id = ?",
            (production_order_id,)
        ).fetchone()
        
        if not order:
            raise ValueError(f"Production order {production_order_id} not found")
        
        if order["status"] != "ready":
            raise ValueError(f"Production order {production_order_id} is not ready (current status: {order['status']})")
        
        # Get first operation
        first_op = conn.execute(
            "SELECT operation_name FROM recipe_operations WHERE recipe_id = ? ORDER BY sequence_order LIMIT 1",
            (order["recipe_id"],)
        ).fetchone()
        
        current_operation = first_op["operation_name"] if first_op else None
        
        conn.execute(
            "UPDATE production_orders SET status = 'in_progress', current_operation = ? WHERE id = ?",
            (current_operation, production_order_id)
        )
        conn.commit()
        
        return {
            "production_order_id": production_order_id,
            "status": "in_progress",
            "current_operation": current_operation,
            "message": f"Production order {production_order_id} started"
        }


@mcp.tool(name="production_complete_order")
@log_tool("production_complete_order")
def production_complete_order(
    production_order_id: str,
    qty_produced: int,
    warehouse: str = "MAIN",
    location: str = "FG-A"
) -> Dict[str, Any]:
    """
    Complete a production order and add produced goods to stock.
    
    Parameters:
        production_order_id: The production order ID (e.g., 'MO-1000')
        qty_produced: Actual quantity produced
        warehouse: Warehouse to add stock to (default: MAIN)
        location: Location within warehouse (default: FG-A)
    """
    with db_conn() as conn:
        order = conn.execute(
            "SELECT * FROM production_orders WHERE id = ?",
            (production_order_id,)
        ).fetchone()
        
        if not order:
            raise ValueError(f"Production order {production_order_id} not found")
        
        if order["status"] == "completed":
            raise ValueError(f"Production order {production_order_id} already completed")
        
        # Update production order
        conn.execute(
            "UPDATE production_orders SET status = 'completed', qty_produced = ?, current_operation = NULL WHERE id = ?",
            (qty_produced, production_order_id)
        )
        
        # Add to stock
        stock_id = generate_id("STK")
        conn.execute(
            "INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)",
            (stock_id, order["item_id"], warehouse, location, qty_produced)
        )
        
        conn.commit()
        
        return {
            "production_order_id": production_order_id,
            "status": "completed",
            "qty_produced": qty_produced,
            "stock_id": stock_id,
            "warehouse": warehouse,
            "location": location,
            "message": f"Production order {production_order_id} completed, {qty_produced} units added to stock"
        }


@mcp.tool(name="purchase_create_order")
@log_tool("purchase_create_order")
def purchase_create_order(
    item_sku: str,
    qty: float,
    supplier_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a purchase order for raw materials or components.
    If supplier_name not provided, auto-selects based on item type.
    
    Parameters:
        item_sku: SKU of item to purchase (e.g., 'ITEM-PVC')
        qty: Quantity to order
        supplier_name: Optional supplier name (auto-selected if not provided)
    """
    with db_conn() as conn:
        item = load_item(conn, item_sku)
        if not item:
            raise ValueError(f"Item {item_sku} not found")
        
        # Auto-select supplier if not provided
        if not supplier_name:
            if "pvc" in item["name"].lower() or "plastic" in item["name"].lower():
                supplier_name = "PlasticCorp"
            elif "dye" in item["name"].lower() or "color" in item["name"].lower():
                supplier_name = "ColorMaster"
            elif "box" in item["name"].lower() or "packaging" in item["name"].lower():
                supplier_name = "PackagingPlus"
            else:
                supplier_name = "PlasticCorp"  # default
        
        supplier = conn.execute(
            "SELECT * FROM suppliers WHERE name = ?",
            (supplier_name,)
        ).fetchone()
        
        if not supplier:
            raise ValueError(f"Supplier {supplier_name} not found")
        
        # Create purchase order
        po_id = generate_id("PO")
        expected_delivery = (datetime.utcnow().date() + timedelta(days=7)).isoformat()
        
        conn.execute(
            """INSERT INTO purchase_orders 
               (id, supplier_id, item_id, qty, status, expected_delivery)
               VALUES (?, ?, ?, ?, 'ordered', ?)""",
            (po_id, supplier["id"], item["id"], qty, expected_delivery)
        )
        conn.commit()
        
        return {
            "purchase_order_id": po_id,
            "supplier_name": supplier["name"],
            "item_sku": item_sku,
            "item_name": item["name"],
            "qty": qty,
            "status": "ordered",
            "expected_delivery": expected_delivery,
            "message": f"Purchase order {po_id} created for {qty} {item['uom']} of {item['name']} from {supplier['name']}"
        }


@mcp.tool(name="purchase_restock_materials")
@log_tool("purchase_restock_materials")
def purchase_restock_materials() -> Dict[str, Any]:
    """
    Check all raw materials and create purchase orders for items below reorder quantity.
    Returns list of purchase orders created.
    """
    with db_conn() as conn:
        # Find items below reorder point
        items_to_reorder = dict_rows(conn.execute(
            """SELECT i.*, COALESCE(SUM(s.on_hand), 0) as current_stock
               FROM items i
               LEFT JOIN stock s ON i.id = s.item_id
               WHERE i.type IN ('raw_material', 'component') AND i.reorder_qty > 0
               GROUP BY i.id
               HAVING current_stock < i.reorder_qty
               ORDER BY i.sku"""
        ))
        
        purchase_orders = []
        for item in items_to_reorder:
            qty_to_order = item["reorder_qty"] - item["current_stock"]
            po = purchase_create_order(item["sku"], qty_to_order)
            purchase_orders.append(po)
        
        return {
            "items_checked": len(items_to_reorder),
            "purchase_orders_created": len(purchase_orders),
            "purchase_orders": purchase_orders
        }


@mcp.tool(name="purchase_receive")
@log_tool("purchase_receive")
def purchase_receive(
    purchase_order_id: str,
    warehouse: str = "MAIN",
    location: str = "RM-A"
) -> Dict[str, Any]:
    """
    Receive a purchase order and add materials to stock.
    
    Parameters:
        purchase_order_id: The purchase order ID (e.g., 'PO-1000')
        warehouse: Warehouse to add stock to (default: MAIN)
        location: Location within warehouse (default: RM-A for raw materials)
    """
    with db_conn() as conn:
        po = conn.execute(
            """SELECT po.*, i.sku as item_sku, i.name as item_name
               FROM purchase_orders po
               JOIN items i ON po.item_id = i.id
               WHERE po.id = ?""",
            (purchase_order_id,)
        ).fetchone()
        
        if not po:
            raise ValueError(f"Purchase order {purchase_order_id} not found")
        
        if po["status"] == "received":
            raise ValueError(f"Purchase order {purchase_order_id} already received")
        
        # Update purchase order
        conn.execute(
            "UPDATE purchase_orders SET status = 'received' WHERE id = ?",
            (purchase_order_id,)
        )
        
        # Add to stock
        stock_id = generate_id("STK")
        conn.execute(
            "INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)",
            (stock_id, po["item_id"], warehouse, location, po["qty"])
        )
        
        conn.commit()
        
        return {
            "purchase_order_id": purchase_order_id,
            "item_sku": po["item_sku"],
            "item_name": po["item_name"],
            "qty_received": po["qty"],
            "stock_id": stock_id,
            "warehouse": warehouse,
            "location": location,
            "message": f"Purchase order {purchase_order_id} received, {po['qty']} units added to stock"
        }


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


@mcp.custom_route("/api/customers/{customer_id}", methods=["GET", "OPTIONS"])
async def api_customer_detail(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    customer_id = request.path_params.get("customer_id")
    with db_conn() as conn:
        # Get customer
        customer_row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not customer_row:
            return _json({"error": "Customer not found"}, status_code=404)
        
        customer = dict(customer_row)
        customer["ui_url"] = ui_href("customers", customer_id)
        
        # Get sales orders
        orders_query = """
            SELECT id as sales_order_id, status, created_at, requested_delivery_date
            FROM sales_orders
            WHERE customer_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        """
        orders = dict_rows(conn.execute(orders_query, (customer_id,)).fetchall())
        customer["sales_orders"] = orders
        
        # Get shipments (via sales orders)
        shipments_query = """
            SELECT DISTINCT
                s.id,
                s.status,
                s.planned_departure,
                s.planned_arrival,
                sos.sales_order_id
            FROM shipments s
            JOIN sales_order_shipments sos ON s.id = sos.shipment_id
            JOIN sales_orders so ON sos.sales_order_id = so.id
            WHERE so.customer_id = ?
            ORDER BY s.planned_departure DESC
            LIMIT 50
        """
        shipments = dict_rows(conn.execute(shipments_query, (customer_id,)).fetchall())
        customer["shipments"] = shipments
        
        return _json(customer)


@mcp.custom_route("/api/items", methods=["GET", "OPTIONS"])
async def api_items(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    limit = int(qp.get("limit", 50))
    in_stock_only = _parse_bool(qp.get("in_stock_only"))
    result = inventory_list_items(in_stock_only=in_stock_only, limit=limit)
    return _json(result)


@mcp.custom_route("/api/items/{sku}", methods=["GET", "OPTIONS"])
async def api_item_detail(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    sku = request.path_params.get("sku")
    
    with db_conn() as conn:
        item = load_item(conn, sku)
        if not item:
            return _json({"error": "Item not found"}, status_code=404)
        
        result = dict(item)
        result["ui_url"] = ui_href("items", sku)
        
        # Add stock summary
        stock = stock_summary(conn, item["id"])
        result["stock"] = stock
        
        # Find recipes that produce this item
        recipes = dict_rows(conn.execute(
            """SELECT r.*, 
               (SELECT COUNT(*) FROM recipe_ingredients WHERE recipe_id = r.id) as ingredient_count,
               (SELECT COUNT(*) FROM recipe_operations WHERE recipe_id = r.id) as operation_count
               FROM recipes r
               WHERE r.output_item_id = ?
               ORDER BY r.id""",
            (item["id"],)
        ))
        result["recipes"] = recipes
        
        # Find recipes that use this item as an ingredient
        used_in_recipes = dict_rows(conn.execute(
            """SELECT DISTINCT r.id as recipe_id, r.output_item_id, 
                      i.sku as output_sku, i.name as output_name,
                      ri.input_qty as qty_per_batch
               FROM recipe_ingredients ri
               JOIN recipes r ON ri.recipe_id = r.id
               JOIN items i ON r.output_item_id = i.id
               WHERE ri.input_item_id = ?
               ORDER BY r.id""",
            (item["id"],)
        ))
        result["used_in_recipes"] = used_in_recipes
        
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


@mcp.custom_route("/api/stock", methods=["GET", "OPTIONS"])
async def api_stock(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    limit = int(qp.get("limit", 200))
    with db_conn() as conn:
        query = """
            SELECT 
                s.id,
                s.item_id,
                i.sku as item_sku,
                i.name as item_name,
                i.type as item_type,
                s.warehouse,
                s.location,
                s.on_hand
            FROM stock s
            JOIN items i ON s.item_id = i.id
            ORDER BY s.warehouse, s.location
            LIMIT ?
        """
        rows = dict_rows(conn.execute(query, (limit,)).fetchall())
        for row in rows:
            row["ui_url"] = ui_href("stock", row["id"])
        return _json({"stock": rows})


@mcp.custom_route("/api/stock/{stock_id}", methods=["GET", "OPTIONS"])
async def api_stock_detail(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    stock_id = request.path_params.get("stock_id")
    with db_conn() as conn:
        query = """
            SELECT 
                s.id,
                s.item_id,
                i.sku as item_sku,
                i.name as item_name,
                i.type as item_type,
                s.warehouse,
                s.location,
                s.on_hand
            FROM stock s
            JOIN items i ON s.item_id = i.id
            WHERE s.id = ?
        """
        row = conn.execute(query, (stock_id,)).fetchone()
        if not row:
            return _json({"error": "Stock record not found"}, status_code=404)
        return _json(dict(row))


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


@mcp.custom_route("/api/shipments", methods=["GET", "OPTIONS"])
async def api_shipments(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    with db_conn() as conn:
        rows = dict_rows(conn.execute("SELECT * FROM shipments ORDER BY planned_departure DESC").fetchall())
        for row in rows:
            row["ui_url"] = ui_href("shipments", row["id"])
    return _json({"shipments": rows})


@mcp.custom_route("/api/production-orders", methods=["GET", "OPTIONS"])
async def api_production_orders(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    limit = int(qp.get("limit", 100))
    with db_conn() as conn:
        query = """
            SELECT 
                po.*,
                i.name as item_name,
                i.sku as item_sku,
                i.type as item_type
            FROM production_orders po
            LEFT JOIN items i ON po.item_id = i.id
            ORDER BY po.eta_finish DESC
            LIMIT ?
        """
        rows = dict_rows(conn.execute(query, (limit,)).fetchall())
        for row in rows:
            row["ui_url"] = ui_href("production", row["id"])
    return _json({"production_orders": rows})


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


@mcp.custom_route("/api/recipes", methods=["GET", "OPTIONS"])
async def api_recipes(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    output_item_sku = qp.get("output_item_sku")
    limit = int(qp.get("limit", 50))
    result = recipe_list(output_item_sku=output_item_sku, limit=limit)
    return _json(result)


@mcp.custom_route("/api/recipes/{recipe_id}", methods=["GET", "OPTIONS"])
async def api_recipe_detail(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    recipe_id = request.path_params.get("recipe_id")
    try:
        result = recipe_get(recipe_id)
        return _json(result)
    except ValueError as exc:
        return _json({"error": str(exc)}, status_code=404)


@mcp.custom_route("/api/suppliers", methods=["GET", "OPTIONS"])
async def api_suppliers(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    limit = int(qp.get("limit", 50))
    with db_conn() as conn:
        rows = dict_rows(conn.execute(
            "SELECT * FROM suppliers ORDER BY name LIMIT ?",
            (limit,)
        ))
        return _json({"suppliers": rows})


@mcp.custom_route("/api/suppliers/{supplier_id}", methods=["GET", "OPTIONS"])
async def api_supplier_detail(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    supplier_id = request.path_params.get("supplier_id")
    with db_conn() as conn:
        supplier = conn.execute(
            "SELECT * FROM suppliers WHERE id = ?",
            (supplier_id,)
        ).fetchone()
        
        if not supplier:
            return _json({"error": "Supplier not found"}, status_code=404)
        
        result = dict(supplier)
        
        # Get purchase orders
        po_rows = dict_rows(conn.execute(
            """SELECT po.*, i.sku as item_sku, i.name as item_name
               FROM purchase_orders po
               JOIN items i ON po.item_id = i.id
               WHERE po.supplier_id = ?
               ORDER BY po.expected_delivery DESC
               LIMIT 100""",
            (supplier_id,)
        ))
        result["purchase_orders"] = po_rows
        
        return _json(result)


@mcp.custom_route("/api/purchase-orders", methods=["GET", "OPTIONS"])
async def api_purchase_orders(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    qp = request.query_params
    limit = int(qp.get("limit", 100))
    status = qp.get("status")
    
    with db_conn() as conn:
        if status:
            rows = dict_rows(conn.execute(
                """SELECT po.*, s.name as supplier_name, i.sku as item_sku, i.name as item_name
                   FROM purchase_orders po
                   JOIN suppliers s ON po.supplier_id = s.id
                   JOIN items i ON po.item_id = i.id
                   WHERE po.status = ?
                   ORDER BY po.expected_delivery DESC
                   LIMIT ?""",
                (status, limit)
            ))
        else:
            rows = dict_rows(conn.execute(
                """SELECT po.*, s.name as supplier_name, i.sku as item_sku, i.name as item_name
                   FROM purchase_orders po
                   JOIN suppliers s ON po.supplier_id = s.id
                   JOIN items i ON po.item_id = i.id
                   ORDER BY po.expected_delivery DESC
                   LIMIT ?""",
                (limit,)
            ))
        
        return _json({"purchase_orders": rows})


@mcp.custom_route("/api/purchase-orders/{po_id}", methods=["GET", "OPTIONS"])
async def api_purchase_order_detail(request):
    if request.method == "OPTIONS":
        return _cors_preflight(["GET"])
    po_id = request.path_params.get("po_id")
    
    with db_conn() as conn:
        po = conn.execute(
            """SELECT po.*, s.name as supplier_name, s.contact_email,
                      i.sku as item_sku, i.name as item_name, i.type as item_type, i.uom
               FROM purchase_orders po
               JOIN suppliers s ON po.supplier_id = s.id
               JOIN items i ON po.item_id = i.id
               WHERE po.id = ?""",
            (po_id,)
        ).fetchone()
        
        if not po:
            return _json({"error": "Purchase order not found"}, status_code=404)
        
        return _json(dict(po))


if __name__ == "__main__":
    # Run as HTTP server using the streamable-http transport (host/port come from FastMCP settings).
    mcp.run(transport="streamable-http")
