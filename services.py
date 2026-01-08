"""Business logic services for the duck-demo application."""

import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from db import dict_rows, generate_id, get_connection
from utils import ui_href, eta_from_days, parse_date
import config


@contextmanager
def db_conn() -> Iterator[sqlite3.Connection]:
    """Database connection context manager."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


class SimulationService:
    """Service for managing simulated time."""
    
    @staticmethod
    def get_current_time() -> str:
        """Get current simulation time."""
        with db_conn() as conn:
            result = conn.execute(
                "SELECT sim_time FROM simulation_state WHERE id = 1"
            ).fetchone()
            return result[0]
    
    @staticmethod
    def advance_time(
        hours: Optional[float] = None,
        days: Optional[int] = None,
        to_time: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Advance the simulated time forward.
        
        Args:
            hours: Number of hours to advance
            days: Number of days to advance
            to_time: ISO datetime to set time to
        
        Returns:
            Dictionary with old_time and new_time
        """
        with db_conn() as conn:
            old_time = conn.execute(
                "SELECT sim_time FROM simulation_state WHERE id = 1"
            ).fetchone()[0]
            
            if to_time:
                conn.execute(
                    "UPDATE simulation_state SET sim_time = ? WHERE id = 1",
                    (to_time,)
                )
            elif hours:
                conn.execute(
                    "UPDATE simulation_state SET sim_time = datetime(sim_time, ? || ' hours') WHERE id = 1",
                    (f'+{hours}',)
                )
            elif days:
                conn.execute(
                    "UPDATE simulation_state SET sim_time = datetime(sim_time, ? || ' days') WHERE id = 1",
                    (f'+{days}',)
                )
            else:
                raise ValueError("Must specify hours, days, or to_time")
            
            conn.commit()
            
            new_time = conn.execute(
                "SELECT sim_time FROM simulation_state WHERE id = 1"
            ).fetchone()[0]
            
            return {
                "old_time": old_time,
                "new_time": new_time
            }


class CustomerService:
    """Service for customer (CRM) operations."""
    
    @staticmethod
    def find_customers(
        name: Optional[str] = None,
        email: Optional[str] = None,
        company: Optional[str] = None,
        city: Optional[str] = None,
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

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        sql = f"SELECT id, name, company, email, city FROM customers {where_clause} ORDER BY id LIMIT ?"
        params.append(limit)

        with db_conn() as conn:
            rows = dict_rows(conn.execute(sql, params))
            for row in rows:
                row["ui_url"] = ui_href("customers", row["id"])
            return {"customers": rows}
    
    @staticmethod
    def create_customer(
        name: str,
        company: Optional[str] = None,
        email: Optional[str] = None,
        city: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new customer."""
        with db_conn() as conn:
            customer_id = generate_id(conn, "CUST", "customers")
            sim_time = simulation_service.get_current_time()
            conn.execute(
                "INSERT INTO customers (id, name, company, email, city, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (customer_id, name, company, email, city, sim_time),
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
    
    @staticmethod
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


class InventoryService:
    """Service for inventory and stock operations."""
    
    @staticmethod
    def get_stock_summary(item_id: str) -> Dict[str, Any]:
        """Get stock summary by location for an item."""
        with db_conn() as conn:
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
    
    @staticmethod
    def check_availability(item_sku: str, qty_required: float) -> Dict[str, Any]:
        """Check if sufficient inventory is available for an item."""
        with db_conn() as conn:
            item = CatalogService.load_item(item_sku)
            if not item:
                raise ValueError(f"Item {item_sku} not found")
            
            summary = InventoryService.get_stock_summary(item["id"])
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


class CatalogService:
    """Service for item/catalog operations."""
    
    @staticmethod
    def load_item(sku: str) -> Optional[Dict[str, Any]]:
        """Load item by SKU."""
        with db_conn() as conn:
            cur = conn.execute(
                "SELECT id, sku, name, type, unit_price, uom, reorder_qty, image FROM items WHERE sku = ?",
                (sku,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_item(sku: str) -> Dict[str, Any]:
        """Fetch an item by SKU."""
        item = CatalogService.load_item(sku)
        if not item:
            raise ValueError("Item not found")
        result = dict(item)
        if result.get("image"):
            result["image_url"] = f"/api/items/{sku}/image"
        result.pop("image", None)
        return result
    
    @staticmethod
    def search_items(words: List[str], limit: int = 10, min_score: int = 1) -> Dict[str, Any]:
        """Fuzzy item search via containment on SKU/name tokens."""
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

                score = len(matched)
                if score >= min_score:
                    item_dict = dict(row)
                    item_dict["ui_url"] = ui_href("items", item_dict["sku"])
                    scored.append({"item": item_dict, "score": score, "matched_words": matched})

            scored.sort(key=lambda entry: (-entry["score"], entry["item"]["sku"]))
            return {"items": scored[:limit], "query": query_tokens}
    
    @staticmethod
    def list_items(in_stock_only: bool = False, limit: int = 50) -> Dict[str, Any]:
        """List items, optionally only those with available stock."""
        with db_conn() as conn:
            base_sql = "SELECT id, sku, name, type, unit_price, image FROM items"
            params: List[Any] = []
            if in_stock_only:
                base_sql += " WHERE id IN (SELECT DISTINCT item_id FROM stock WHERE on_hand > 0)"
            base_sql += " ORDER BY sku LIMIT ?"
            params.append(limit)
            rows = dict_rows(conn.execute(base_sql, params))
            # Attach stock totals for all items
            for row in rows:
                summary = InventoryService.get_stock_summary(row["id"])
                row["on_hand_total"] = summary["on_hand_total"]
                row["available_total"] = summary["available_total"]
            for row in rows:
                row["ui_url"] = ui_href("items", row["sku"])
                if row.get("image"):
                    row["image_url"] = f"/api/items/{row['sku']}/image"
                row.pop("image", None)
            return {"items": rows}


class PricingService:
    """Service for pricing and quoting operations."""
    
    @staticmethod
    def get_unit_price(item_id: str) -> float:
        """Get unit price for an item."""
        with db_conn() as conn:
            item_row = conn.execute("SELECT unit_price FROM items WHERE id = ?", (item_id,)).fetchone()
            if item_row and item_row["unit_price"] is not None:
                return float(item_row["unit_price"])
            return config.PRICING_DEFAULT_UNIT_PRICE
    
    @staticmethod
    def find_substitutions(
        requested_item: Dict[str, Any],
        allowed_subs: List[str],
        price_slack_pct: float = None
    ) -> List[Dict[str, Any]]:
        """Find substitute items based on type and price band."""
        if price_slack_pct is None:
            price_slack_pct = config.SUBSTITUTION_PRICE_SLACK_PCT
        
        base_price = PricingService.get_unit_price(requested_item["id"])
        lower = base_price * (1 - price_slack_pct)
        upper = base_price * (1 + price_slack_pct)

        with db_conn() as conn:
            candidates = conn.execute(
                "SELECT id, sku, name, type FROM items WHERE type = ? AND id != ?",
                (requested_item["type"], requested_item["id"]),
            ).fetchall()

            filtered: List[Dict[str, Any]] = []
            for cand in candidates:
                if allowed_subs and cand["sku"] not in allowed_subs:
                    continue
                cand_price = PricingService.get_unit_price(cand["id"])
                if not (lower <= cand_price <= upper):
                    continue
                cand_stock = inventory_service.get_stock_summary(cand["id"])
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
    
    @staticmethod
    def compute_pricing(sales_order_id: str) -> Dict[str, Any]:
        """Compute pricing for a sales order."""
        with db_conn() as conn:
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
                unit_price = PricingService.get_unit_price(row["item_id"])
                line_total = qty * unit_price
                subtotal += line_total
                line_totals.append({"sku": row["sku"], "qty": qty, "unit_price": unit_price, "line_total": line_total})

            discount = config.PRICING_VOLUME_DISCOUNT_PCT * subtotal if total_qty >= config.PRICING_VOLUME_QTY_THRESHOLD else 0.0
            shipping = 0.0 if subtotal >= config.PRICING_FREE_SHIPPING_THRESHOLD else 20.0
            total = subtotal - discount + shipping
            return {
                "sales_order_id": sales_order_id,
                "pricing": {
                    "currency": config.PRICING_CURRENCY,
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
    
    @staticmethod
    def calculate_quote_options(sku: str, qty: int, need_by: Optional[str], allowed_subs: List[str]) -> Dict[str, Any]:
        """Generate quote / fulfillment options for a request."""
        item = catalog_service.load_item(sku)
        if not item:
            raise ValueError("Unknown item")

        need_by_dt = parse_date(need_by)
        availability = inventory_service.get_stock_summary(item["id"])
        available = max(0, availability["available_total"])
        transit_days = config.TRANSIT_DAYS_DEFAULT
        production_lead_days = config.PRODUCTION_LEAD_DAYS_BY_TYPE.get(item["type"], config.PRODUCTION_LEAD_DAYS_DEFAULT)

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
        substitutions = PricingService.find_substitutions(item, allowed_subs)
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
                sub_prod_lead = config.PRODUCTION_LEAD_DAYS_BY_TYPE.get(sub_item["type"], config.PRODUCTION_LEAD_DAYS_DEFAULT)
                lines = [
                    {"sku": sub_item["sku"], "qty": sub_avail, "source": "stock"},
                    {"sku": sub_item["sku"], "qty": remaining, "source": "production", "lead_days": sub_prod_lead},
                ]
                summary = f"Substitute {sub_avail} stock + {remaining} production of {sub_item['sku']}"
                notes = "Within price band and same type; partial stock, remainder after production."

            add_option(opt_idx, summary, lines, notes)
            opt_idx += 1

        return {"options": options}


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


class LogisticsService:
    """Service for logistics and shipment operations."""
    
    @staticmethod
    def create_shipment(ship_from: Optional[Dict[str, Any]], ship_to: Optional[Dict[str, Any]], planned_departure: Optional[str], planned_arrival: Optional[str], packages: Optional[List[Dict[str, Any]]], reference: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a planned shipment."""
        ship_from = ship_from or {}
        ship_to = ship_to or {}
        packages = packages or []
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


class ProductionService:
    """Service for production order operations."""
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get production statistics."""
        with db_conn() as conn:
            total_production = conn.execute("SELECT COUNT(*) as count FROM production_orders").fetchone()["count"]
            status_rows = dict_rows(conn.execute("SELECT status, COUNT(*) as count FROM production_orders GROUP BY status ORDER BY count DESC"))
            total_qty = conn.execute("SELECT SUM(qty) as total FROM production_orders").fetchone()["total"] or 0
            top_items = dict_rows(conn.execute("SELECT i.sku, i.name, SUM(po.qty) as total_qty, COUNT(*) as order_count FROM production_orders po JOIN items i ON po.item_id = i.id GROUP BY i.id, i.sku, i.name ORDER BY total_qty DESC LIMIT 10"))
            upcoming = dict_rows(conn.execute("SELECT i.sku, i.name, po.qty, po.eta_finish, po.status FROM production_orders po JOIN items i ON po.item_id = i.id WHERE po.eta_finish >= date('now') AND po.eta_finish <= date('now', '+60 days') ORDER BY po.eta_finish LIMIT 20"))
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
        from datetime import datetime, timedelta
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


class RecipeService:
    """Service for recipe operations."""
    
    @staticmethod
    def list_recipes(output_item_sku: Optional[str], limit: int) -> Dict[str, Any]:
        """List recipes."""
        with db_conn() as conn:
            if output_item_sku:
                item = CatalogService.load_item(output_item_sku)
                if not item:
                    raise ValueError(f"Item {output_item_sku} not found")
                rows = dict_rows(conn.execute("SELECT r.*, i.sku as output_sku, i.name as output_name FROM recipes r JOIN items i ON r.output_item_id = i.id WHERE r.output_item_id = ? ORDER BY r.id LIMIT ?", (item["id"], limit)))
            else:
                rows = dict_rows(conn.execute("SELECT r.*, i.sku as output_sku, i.name as output_name FROM recipes r JOIN items i ON r.output_item_id = i.id ORDER BY r.id LIMIT ?", (limit,)))
            return {"recipes": rows}
    
    @staticmethod
    def get_recipe(recipe_id: str) -> Dict[str, Any]:
        """Get detailed recipe information."""
        with db_conn() as conn:
            recipe = conn.execute("SELECT r.*, i.sku as output_sku, i.name as output_name, i.type as output_type FROM recipes r JOIN items i ON r.output_item_id = i.id WHERE r.id = ?", (recipe_id,)).fetchone()
            if not recipe:
                raise ValueError(f"Recipe {recipe_id} not found")
            result = dict(recipe)
            ingredients = dict_rows(conn.execute("SELECT ri.*, i.sku as ingredient_sku, i.name as ingredient_name FROM recipe_ingredients ri JOIN items i ON ri.input_item_id = i.id WHERE ri.recipe_id = ? ORDER BY ri.sequence_order", (recipe_id,)))
            result["ingredients"] = ingredients
            operations = dict_rows(conn.execute("SELECT * FROM recipe_operations WHERE recipe_id = ? ORDER BY sequence_order", (recipe_id,)))
            result["operations"] = operations
            return result


class PurchaseService:
    """Service for purchase order operations."""
    
    @staticmethod
    def create_order(item_sku: str, qty: float, supplier_name: Optional[str]) -> Dict[str, Any]:
        """Create a purchase order."""
        from datetime import datetime, timedelta
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


class MessagingService:
    """Service for email/messaging operations."""
    
    @staticmethod
    def create_email(customer_id: str, subject: str, body: str, sales_order_id: Optional[str], recipient_email: Optional[str], recipient_name: Optional[str]) -> Dict[str, Any]:
        """Create a new email draft."""
        with db_conn() as conn:
            customer = conn.execute("SELECT id, name, email FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if not customer:
                raise ValueError(f"Customer {customer_id} not found")
            if sales_order_id:
                so = conn.execute("SELECT customer_id FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
                if not so:
                    raise ValueError(f"Sales order {sales_order_id} not found")
                if so["customer_id"] != customer_id:
                    raise ValueError(f"Sales order {sales_order_id} does not belong to customer {customer_id}")
            final_recipient_email = recipient_email or customer["email"]
            final_recipient_name = recipient_name or customer["name"]
            if not final_recipient_email:
                raise ValueError(f"No email address available for customer {customer_id}")
            email_id = generate_id(conn, "EMAIL", "emails")
            sim_time = SimulationService.get_current_time()
            conn.execute("INSERT INTO emails (id, customer_id, sales_order_id, recipient_email, recipient_name, subject, body, status, created_at, modified_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)", (email_id, customer_id, sales_order_id, final_recipient_email, final_recipient_name, subject, body, sim_time, sim_time))
            conn.commit()
            email = dict(conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone())
            email["ui_url"] = ui_href("emails", email_id)
            return {"email_id": email_id, "email": email, "message": f"Email draft '{subject}' created with ID {email_id} at {sim_time}"}
    
    @staticmethod
    def list_emails(customer_id: Optional[str], sales_order_id: Optional[str], status: Optional[str], limit: int) -> Dict[str, Any]:
        """List emails with filters."""
        filters = []
        params: List[Any] = []
        if customer_id:
            filters.append("customer_id = ?")
            params.append(customer_id)
        if sales_order_id:
            filters.append("sales_order_id = ?")
            params.append(sales_order_id)
        if status:
            filters.append("status = ?")
            params.append(status)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        sql = f"SELECT * FROM emails {where_clause} ORDER BY modified_at DESC LIMIT ?"
        params.append(limit)
        with db_conn() as conn:
            rows = dict_rows(conn.execute(sql, params))
            for row in rows:
                row["ui_url"] = ui_href("emails", row["id"])
            return {"emails": rows}
    
    @staticmethod
    def get_email(email_id: str) -> Dict[str, Any]:
        """Get detailed email information."""
        with db_conn() as conn:
            email = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
            if not email:
                raise ValueError(f"Email {email_id} not found")
            result = {"email": dict(email)}
            result["email"]["ui_url"] = ui_href("emails", email_id)
            customer = conn.execute("SELECT id, name, company, email, city FROM customers WHERE id = ?", (email["customer_id"],)).fetchone()
            if customer:
                result["customer"] = dict(customer)
                result["customer"]["ui_url"] = ui_href("customers", customer["id"])
            if email["sales_order_id"]:
                so = conn.execute("SELECT id, status, created_at FROM sales_orders WHERE id = ?", (email["sales_order_id"],)).fetchone()
                if so:
                    result["sales_order"] = dict(so)
                    result["sales_order"]["ui_url"] = ui_href("orders", so["id"])
            return result
    
    @staticmethod
    def update_email(email_id: str, subject: Optional[str], body: Optional[str]) -> Dict[str, Any]:
        """Update email subject/body."""
        with db_conn() as conn:
            email = conn.execute("SELECT status FROM emails WHERE id = ?", (email_id,)).fetchone()
            if not email:
                raise ValueError(f"Email {email_id} not found")
            if email["status"] != "draft":
                raise ValueError(f"Cannot update email {email_id}: status is '{email['status']}', must be 'draft'")
            sim_time = SimulationService.get_current_time()
            updates = []
            params: List[Any] = []
            if subject is not None:
                updates.append("subject = ?")
                params.append(subject)
            if body is not None:
                updates.append("body = ?")
                params.append(body)
            if not updates:
                raise ValueError("Must provide at least one field to update (subject or body)")
            updates.append("modified_at = ?")
            params.append(sim_time)
            params.append(email_id)
            sql = f"UPDATE emails SET {', '.join(updates)} WHERE id = ?"
            conn.execute(sql, params)
            conn.commit()
            updated_email = dict(conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone())
            updated_email["ui_url"] = ui_href("emails", email_id)
            return {"email_id": email_id, "email": updated_email, "message": f"Email {email_id} updated at {sim_time}"}
    
    @staticmethod
    def send_email(email_id: str) -> Dict[str, Any]:
        """Mark email as sent."""
        with db_conn() as conn:
            email = conn.execute("SELECT status FROM emails WHERE id = ?", (email_id,)).fetchone()
            if not email:
                raise ValueError(f"Email {email_id} not found")
            if email["status"] != "draft":
                raise ValueError(f"Cannot send email {email_id}: status is '{email['status']}', must be 'draft'")
            sim_time = SimulationService.get_current_time()
            conn.execute("UPDATE emails SET status = 'sent', sent_at = ?, modified_at = ? WHERE id = ?", (sim_time, sim_time, email_id))
            conn.commit()
            sent_email = dict(conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone())
            sent_email["ui_url"] = ui_href("emails", email_id)
            return {"email_id": email_id, "email": sent_email, "message": f"Email {email_id} marked as sent at {sim_time}"}
    
    @staticmethod
    def delete_email(email_id: str) -> Dict[str, Any]:
        """Delete an email."""
        with db_conn() as conn:
            email = conn.execute("SELECT status FROM emails WHERE id = ?", (email_id,)).fetchone()
            if not email:
                raise ValueError(f"Email {email_id} not found")
            if email["status"] != "draft":
                raise ValueError(f"Cannot delete email {email_id}: status is '{email['status']}', must be 'draft'")
            conn.execute("DELETE FROM emails WHERE id = ?", (email_id,))
            conn.commit()
            return {"email_id": email_id, "message": f"Email {email_id} deleted"}


class StatsService:
    """Service for statistics operations."""
    
    @staticmethod
    def get_statistics(entity: str, metric: str, group_by: Optional[str], field: Optional[str], status: Optional[str], item_type: Optional[str], warehouse: Optional[str], city: Optional[str], limit: int) -> Dict[str, Any]:
        """Get flexible statistics for any entity."""
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


class AdminService:
    """Service for admin operations."""
    
    @staticmethod
    def reset_database(confirm: str) -> Dict[str, Any]:
        """Reset database to initial demo state."""
        if confirm != "kondor":
            raise ValueError("Invalid confirmation")
        from seed_demo import seed
        with db_conn() as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
            for table in tables:
                conn.execute(f"DROP TABLE IF EXISTS {table[0]}")
            conn.commit()
        seed(from_admin=True)
        return {"status": "Database reset complete", "initial_time": "2025-12-24 08:30:00"}


# Create singleton instances
simulation_service = SimulationService()
customer_service = CustomerService()
inventory_service = InventoryService()
catalog_service = CatalogService()
pricing_service = PricingService()
sales_service = SalesService()
logistics_service = LogisticsService()
production_service = ProductionService()
recipe_service = RecipeService()
purchase_service = PurchaseService()
messaging_service = MessagingService()
stats_service = StatsService()
admin_service = AdminService()
