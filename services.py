"""Business logic services for the duck-demo application."""

import os
import re
import sqlite3
import uuid
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Union

import config

logger = logging.getLogger(__name__)

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from io import BytesIO

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
            
            # Auto-mark overdue invoices based on new sim time
            overdue_count = conn.execute(
                "UPDATE invoices SET status = 'overdue' "
                "WHERE status = 'issued' AND due_date IS NOT NULL AND due_date < ?",
                (new_time[:10],)
            ).rowcount
            conn.commit()
            
            result = {
                "old_time": old_time,
                "new_time": new_time
            }
            if overdue_count > 0:
                result["invoices_marked_overdue"] = overdue_count
            return result


class CustomerService:
    """Service for customer (CRM) operations."""
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
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
    def check_availability(item_sku: str, quantity: float) -> Dict[str, Any]:
        """Check if sufficient inventory is available for an item."""
        with db_conn() as conn:
            item = CatalogService.load_item(item_sku)
            if not item:
                raise ValueError(f"Item {item_sku} not found")
            
            summary = InventoryService.get_stock_summary(item["id"])
            available = summary["available_total"]
            is_available = available >= quantity
            shortfall = 0.0 if is_available else (quantity - available)
            
            return {
                "item_sku": item_sku,
                "item_name": item["name"],
                "qty_required": quantity,
                "qty_available": available,
                "is_available": is_available,
                "shortfall": shortfall,
                "stock_locations": summary["by_location"]
            }


class CatalogService:
    """Service for item/catalog operations."""
    
    @staticmethod
    def load_item(sku_or_id: str) -> Optional[Dict[str, Any]]:
        """Load item by SKU or item_id."""
        with db_conn() as conn:
            cur = conn.execute(
                "SELECT id, sku, name, type, unit_price, uom, reorder_qty, image FROM items WHERE sku = ? OR id = ?",
                (sku_or_id, sku_or_id)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_item(sku_or_id: str) -> Dict[str, Any]:
        """Fetch an item by SKU or item_id."""
        item = CatalogService.load_item(sku_or_id)
        if not item:
            raise ValueError("Item not found")
        result = dict(item)
        if result.get("image"):
            # Use the actual sku from the result for image URL
            result["image_url"] = f"{config.API_BASE}/api/items/{result['sku']}/image.png"
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
    def list_items(in_stock_only: bool = False, item_type: Optional[str] = "finished_good", limit: int = 50) -> Dict[str, Any]:
        """List items, optionally only those with available stock."""
        with db_conn() as conn:
            base_sql = "SELECT id, sku, name, type, unit_price, image FROM items"
            params: List[Any] = []
            filters = []
            
            if item_type:
                filters.append("type = ?")
                params.append(item_type)
            
            if in_stock_only:
                filters.append("id IN (SELECT DISTINCT item_id FROM stock WHERE on_hand > 0)")
            
            if filters:
                base_sql += " WHERE " + " AND ".join(filters)
            
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
                    row["image_url"] = f"{config.API_BASE}/api/items/{row['sku']}/image.png"
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
    def calculate_quote_options(sku: str, qty: int, delivery_date: Optional[str], allowed_subs: List[str]) -> Dict[str, Any]:
        """Generate quote / fulfillment options for a request."""
        item = catalog_service.load_item(sku)
        if not item:
            raise ValueError("Unknown item")

        need_by_dt = parse_date(delivery_date)
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
        
        # Validate ship_to address
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
            raise ValueError(f"Cannot create shipment: missing address fields: {', '.join(missing_fields)}. Please provide a complete shipping address.")
        
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
            total_qty = conn.execute("SELECT SUM(r.output_qty) as total FROM production_orders po JOIN recipes r ON po.recipe_id = r.id").fetchone()["total"] or 0
            top_items = dict_rows(conn.execute("SELECT i.sku, i.name, SUM(r.output_qty) as total_qty, COUNT(*) as order_count FROM production_orders po JOIN recipes r ON po.recipe_id = r.id JOIN items i ON po.item_id = i.id GROUP BY i.id, i.sku, i.name ORDER BY total_qty DESC LIMIT 10"))
            upcoming = dict_rows(conn.execute("SELECT i.sku, i.name, r.output_qty as qty, po.eta_finish, po.status FROM production_orders po JOIN recipes r ON po.recipe_id = r.id JOIN items i ON po.item_id = i.id WHERE po.eta_finish >= date('now') AND po.eta_finish <= date('now', '+60 days') ORDER BY po.eta_finish LIMIT 20"))
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
                raise ValueError(f"Cannot send email to {customer['name']} ({customer_id}): no email address on file. Please update the customer record with an email address.")
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


class QuoteService:
    """Service for quote operations."""

    @staticmethod
    def create_quote(
        customer_id: str,
        requested_delivery_date: Optional[str],
        ship_to: Optional[Dict[str, Any]],
        lines: List[Dict[str, Any]],
        note: Optional[str] = None,
        valid_days: int = 30
    ) -> Dict[str, Any]:
        """Create a draft quote with frozen pricing."""
        with db_conn() as conn:
            # Validate customer
            customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if not customer:
                raise ValueError(f"Customer {customer_id} not found")
            
            sim_time = SimulationService.get_current_time()
            quote_id = generate_id(conn, "QUOTE", "quotes")
            
            # Calculate pricing for each line (freeze prices)
            subtotal = 0.0
            quote_lines = []
            
            for idx, line in enumerate(lines, start=1):
                item = conn.execute("SELECT * FROM items WHERE sku = ?", (line["sku"],)).fetchone()
                if not item:
                    raise ValueError(f"Item {line['sku']} not found")
                
                qty = line["qty"]
                unit_price = item["unit_price"]
                line_total = qty * unit_price
                subtotal += line_total
                
                line_id = f"{quote_id}-{idx:02d}"
                quote_lines.append({
                    "id": line_id,
                    "item_id": item["id"],
                    "sku": item["sku"],
                    "name": item["name"],
                    "qty": qty,
                    "unit_price": unit_price,
                    "line_total": line_total
                })
            
            # Apply business rules for discount and shipping
            total_qty = sum(line["qty"] for line in lines)
            discount = config.PRICING_VOLUME_DISCOUNT_PCT * subtotal if total_qty >= config.PRICING_VOLUME_QTY_THRESHOLD else 0.0
            shipping = 0.0 if subtotal >= config.PRICING_FREE_SHIPPING_THRESHOLD else 20.0
            tax = 0.0  # Tax calculation not implemented
            total = subtotal - discount + shipping + tax
            
            # Calculate valid_until date
            from datetime import datetime, timedelta
            valid_until = (datetime.fromisoformat(sim_time) + timedelta(days=valid_days)).strftime("%Y-%m-%d")
            
            # Insert quote header
            conn.execute(
                "INSERT INTO quotes (id, customer_id, revision_number, requested_delivery_date, "
                "ship_to_line1, ship_to_postal_code, ship_to_city, ship_to_country, note, "
                "subtotal, discount, shipping, tax, total, currency, valid_until, status, created_at) "
                "VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                (
                    quote_id, customer_id, requested_delivery_date,
                    ship_to.get("line1") if ship_to else None,
                    ship_to.get("postal_code") if ship_to else None,
                    ship_to.get("city") if ship_to else None,
                    ship_to.get("country") if ship_to else None,
                    note,
                    subtotal, discount, shipping, tax, total, config.PRICING_CURRENCY,
                    valid_until, sim_time
                )
            )
            
            # Insert quote lines
            for line in quote_lines:
                conn.execute(
                    "INSERT INTO quote_lines (id, quote_id, item_id, qty, unit_price, line_total) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (line["id"], quote_id, line["item_id"], line["qty"], line["unit_price"], line["line_total"])
                )
            
            conn.commit()
            
            return {
                "quote_id": quote_id,
                "customer_id": customer_id,
                "status": "draft",
                "total": total,
                "currency": config.PRICING_CURRENCY,
                "valid_until": valid_until,
                "lines": quote_lines,
                "ui_url": ui_href("quotes", quote_id),
                "message": f"📋 Quote {quote_id} created — {config.PRICING_CURRENCY} {total:.2f} (valid until {valid_until})"
            }
    
    @staticmethod
    def get_quote(quote_id: str) -> Optional[Dict[str, Any]]:
        """Get full quote details with customer, lines, and pricing."""
        with db_conn() as conn:
            quote = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            if not quote:
                return None
            
            quote_dict = dict(quote)
            quote_dict["ui_url"] = ui_href("quotes", quote_id)
            
            # Get customer
            customer = conn.execute("SELECT * FROM customers WHERE id = ?", (quote["customer_id"],)).fetchone()
            customer_dict = dict(customer) if customer else None
            if customer_dict:
                customer_dict["ui_url"] = ui_href("customers", customer_dict["id"])
            
            # Get quote lines with item details
            lines = dict_rows(conn.execute(
                "SELECT ql.*, i.sku, i.name, i.uom FROM quote_lines ql "
                "JOIN items i ON ql.item_id = i.id "
                "WHERE ql.quote_id = ? ORDER BY ql.id",
                (quote_id,)
            ).fetchall())
            
            # Get superseded quote if this is a revision
            superseded_quote = None
            if quote["supersedes_quote_id"]:
                superseded_quote = {"id": quote["supersedes_quote_id"], "ui_url": ui_href("quotes", quote["supersedes_quote_id"])}
            
            # Get newer revision if this quote was superseded
            newer_revision = conn.execute(
                "SELECT id FROM quotes WHERE supersedes_quote_id = ? ORDER BY revision_number DESC LIMIT 1",
                (quote_id,)
            ).fetchone()
            newer_revision_dict = None
            if newer_revision:
                newer_revision_dict = {"id": newer_revision[0], "ui_url": ui_href("quotes", newer_revision[0])}
            
            return {
                "quote": quote_dict,
                "customer": customer_dict,
                "lines": lines,
                "superseded_quote": superseded_quote,
                "newer_revision": newer_revision_dict
            }
    
    @staticmethod
    def list_quotes(
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        show_superseded: bool = False
    ) -> Dict[str, Any]:
        """List quotes with optional filters. By default, hides superseded quotes."""
        filters: List[str] = []
        params: List[Any] = []
        
        if customer_id:
            filters.append("q.customer_id = ?")
            params.append(customer_id)
        if status:
            filters.append("q.status = ?")
            params.append(status)
        if not show_superseded:
            filters.append("q.status != 'superseded'")
        
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        
        sql = (
            f"SELECT q.*, c.name as customer_name, c.company as customer_company "
            f"FROM quotes q LEFT JOIN customers c ON q.customer_id = c.id "
            f"{where_clause} ORDER BY q.created_at DESC LIMIT ?"
        )
        params.append(limit)
        
        with db_conn() as conn:
            rows = dict_rows(conn.execute(sql, params))
            for row in rows:
                row["ui_url"] = ui_href("quotes", row["id"])
            return {"quotes": rows}
    
    @staticmethod
    def send_quote(quote_id: str) -> Dict[str, Any]:
        """Send a draft quote to customer: sets status='sent', sent_at, and generates PDF."""
        with db_conn() as conn:
            quote = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            if not quote:
                raise ValueError(f"Quote {quote_id} not found")
            if quote["status"] != "draft":
                raise ValueError(f"Quote {quote_id} is '{quote['status']}', must be 'draft' to send")
            
            sim_time = SimulationService.get_current_time()
            conn.execute(
                "UPDATE quotes SET status = 'sent', sent_at = ? WHERE id = ?",
                (sim_time, quote_id)
            )
            conn.commit()
            
            # Generate and store PDF
            try:
                pdf_bytes = QuoteService.generate_quote_pdf(quote_id)
                DocumentService.store_document(
                    entity_type="quote",
                    entity_id=quote_id,
                    document_type="quote_pdf",
                    content=pdf_bytes,
                    filename=f"quote_{quote_id}.pdf",
                    notes="Generated when quote was sent"
                )
            except Exception as e:
                logger.error(f"Failed to generate PDF for {quote_id}: {e}")
                # Don't fail the send operation if PDF generation fails
            
            return {
                "quote_id": quote_id,
                "status": "sent",
                "sent_at": sim_time,
                "valid_until": quote["valid_until"],
                "ui_url": ui_href("quotes", quote_id),
                "message": f"📨 Quote {quote_id} sent to customer (valid until {quote['valid_until']})"
            }
    
    @staticmethod
    def accept_quote(quote_id: str) -> Dict[str, Any]:
        """Accept a sent quote: creates sales order and updates quote status."""
        with db_conn() as conn:
            quote = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            if not quote:
                raise ValueError(f"Quote {quote_id} not found")
            if quote["status"] not in ("sent", "draft"):
                raise ValueError(f"Quote {quote_id} is '{quote['status']}', must be 'sent' or 'draft' to accept")
            
            # Check if quote is expired
            sim_time = SimulationService.get_current_time()
            if quote["valid_until"] and quote["valid_until"] < sim_time[:10]:
                raise ValueError(f"Quote {quote_id} expired on {quote['valid_until']}")
            
            # Get quote lines
            lines = dict_rows(conn.execute(
                "SELECT ql.*, i.sku FROM quote_lines ql JOIN items i ON ql.item_id = i.id WHERE ql.quote_id = ?",
                (quote_id,)
            ).fetchall())
            
            # Create sales order from quote
            sales_order_lines = [{"sku": line["sku"], "qty": line["qty"]} for line in lines]
            
            ship_to = None
            if quote["ship_to_line1"]:
                ship_to = {
                    "line1": quote["ship_to_line1"],
                    "postal_code": quote["ship_to_postal_code"],
                    "city": quote["ship_to_city"],
                    "country": quote["ship_to_country"]
                }
            
            # Create sales order
            sales_result = SalesService.create_order(
                customer_id=quote["customer_id"],
                requested_delivery_date=quote["requested_delivery_date"],
                ship_to=ship_to,
                lines=sales_order_lines,
                note=f"Created from quote {quote_id}"
            )
            
            # Update quote status
            conn.execute(
                "UPDATE quotes SET status = 'accepted', accepted_at = ? WHERE id = ?",
                (sim_time, quote_id)
            )
            conn.commit()
            
            return {
                "quote_id": quote_id,
                "status": "accepted",
                "sales_order_id": sales_result["sales_order_id"],
                "sales_order_url": sales_result.get("ui_url"),
                "ui_url": ui_href("quotes", quote_id),
                "message": f"✅ Quote {quote_id} accepted → Sales order {sales_result['sales_order_id']} created"
            }
    
    @staticmethod
    def reject_quote(quote_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Reject a quote."""
        with db_conn() as conn:
            quote = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            if not quote:
                raise ValueError(f"Quote {quote_id} not found")
            if quote["status"] not in ("sent", "draft"):
                raise ValueError(f"Quote {quote_id} is '{quote['status']}', cannot reject")
            
            sim_time = SimulationService.get_current_time()
            note = quote["note"] or ""
            if reason:
                note = f"{note}\nRejection reason: {reason}".strip()
            
            conn.execute(
                "UPDATE quotes SET status = 'rejected', rejected_at = ?, note = ? WHERE id = ?",
                (sim_time, note, quote_id)
            )
            conn.commit()
            
            return {
                "quote_id": quote_id,
                "status": "rejected",
                "ui_url": ui_href("quotes", quote_id),
                "message": f"❌ Quote {quote_id} rejected"
            }
    
    @staticmethod
    def revise_quote(quote_id: str, changes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new revision of a quote, marking the old one as superseded."""
        with db_conn() as conn:
            original_quote = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            if not original_quote:
                raise ValueError(f"Quote {quote_id} not found")
            if original_quote["status"] in ("accepted", "superseded"):
                raise ValueError(f"Quote {quote_id} is '{original_quote['status']}', cannot revise")
            
            # Get original lines
            original_lines = dict_rows(conn.execute(
                "SELECT ql.*, i.sku FROM quote_lines ql JOIN items i ON ql.item_id = i.id WHERE ql.quote_id = ?",
                (quote_id,)
            ).fetchall())
            
            # Extract base quote number (QUOTE-0001-R1 -> QUOTE-0001)
            import re
            match = re.match(r"(QUOTE-\d+)(?:-R\d+)?", quote_id)
            base_id = match.group(1) if match else quote_id.rsplit('-R', 1)[0]
            
            # Generate new revision ID
            new_revision_num = original_quote["revision_number"] + 1
            new_quote_id = f"{base_id}-R{new_revision_num}"
            
            sim_time = SimulationService.get_current_time()
            
            # Apply changes if provided, otherwise copy everything
            lines_to_use = changes.get("lines") if changes and "lines" in changes else [{"sku": line["sku"], "qty": line["qty"]} for line in original_lines]
            requested_delivery_date = changes.get("requested_delivery_date", original_quote["requested_delivery_date"]) if changes else original_quote["requested_delivery_date"]
            note = changes.get("note", original_quote["note"]) if changes else original_quote["note"]
            
            ship_to = None
            if changes and "ship_to" in changes:
                ship_to = changes["ship_to"]
            elif original_quote["ship_to_line1"]:
                ship_to = {
                    "line1": original_quote["ship_to_line1"],
                    "postal_code": original_quote["ship_to_postal_code"],
                    "city": original_quote["ship_to_city"],
                    "country": original_quote["ship_to_country"]
                }
            
            # Calculate pricing for revised lines
            subtotal = 0.0
            revised_lines = []
            
            for idx, line in enumerate(lines_to_use, start=1):
                item = conn.execute("SELECT * FROM items WHERE sku = ?", (line["sku"],)).fetchone()
                if not item:
                    raise ValueError(f"Item {line['sku']} not found")
                
                qty = line["qty"]
                unit_price = item["unit_price"]
                line_total = qty * unit_price
                subtotal += line_total
                
                line_id = f"{new_quote_id}-{idx:02d}"
                revised_lines.append({
                    "id": line_id,
                    "item_id": item["id"],
                    "sku": item["sku"],
                    "qty": qty,
                    "unit_price": unit_price,
                    "line_total": line_total
                })
            
            # Apply business rules
            total_qty = sum(line["qty"] for line in lines_to_use)
            discount = config.PRICING_VOLUME_DISCOUNT_PCT * subtotal if total_qty >= config.PRICING_VOLUME_QTY_THRESHOLD else 0.0
            shipping = 0.0 if subtotal >= config.PRICING_FREE_SHIPPING_THRESHOLD else 20.0
            tax = 0.0
            total = subtotal - discount + shipping + tax
            
            # Calculate new valid_until
            from datetime import datetime, timedelta
            valid_days = changes.get("valid_days", 30) if changes else 30
            valid_until = (datetime.fromisoformat(sim_time) + timedelta(days=valid_days)).strftime("%Y-%m-%d")
            
            # Insert new revision
            conn.execute(
                "INSERT INTO quotes (id, customer_id, revision_number, supersedes_quote_id, requested_delivery_date, "
                "ship_to_line1, ship_to_postal_code, ship_to_city, ship_to_country, note, "
                "subtotal, discount, shipping, tax, total, currency, valid_until, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                (
                    new_quote_id, original_quote["customer_id"], new_revision_num, quote_id, requested_delivery_date,
                    ship_to.get("line1") if ship_to else None,
                    ship_to.get("postal_code") if ship_to else None,
                    ship_to.get("city") if ship_to else None,
                    ship_to.get("country") if ship_to else None,
                    note,
                    subtotal, discount, shipping, tax, total, config.PRICING_CURRENCY,
                    valid_until, sim_time
                )
            )
            
            # Insert revised lines
            for line in revised_lines:
                conn.execute(
                    "INSERT INTO quote_lines (id, quote_id, item_id, qty, unit_price, line_total) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (line["id"], new_quote_id, line["item_id"], line["qty"], line["unit_price"], line["line_total"])
                )
            
            # Mark original quote as superseded
            conn.execute(
                "UPDATE quotes SET status = 'superseded' WHERE id = ?",
                (quote_id,)
            )
            
            conn.commit()
            
            return {
                "quote_id": new_quote_id,
                "revision_number": new_revision_num,
                "supersedes": quote_id,
                "status": "draft",
                "total": total,
                "currency": config.PRICING_CURRENCY,
                "valid_until": valid_until,
                "ui_url": ui_href("quotes", new_quote_id),
                "message": f"📝 Quote revised: {quote_id} → {new_quote_id} (R{new_revision_num})"
            }
    
    @staticmethod
    def generate_quote_pdf(quote_id: str) -> bytes:
        """Generate a PDF for a quote using ReportLab."""
        # Get quote data
        quote_data = QuoteService.get_quote(quote_id)
        if not quote_data:
            raise ValueError(f"Quote {quote_id} not found")
        
        quote = quote_data["quote"]
        customer = quote_data["customer"]
        lines = quote_data["lines"]
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                              topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=30,
        )
        
        # Title
        title_text = f"<b>QUOTATION {quote['id']}</b>"
        if quote["revision_number"] > 1:
            title_text += f" <font size='18'>(Revision {quote['revision_number']})</font>"
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Company header
        story.append(Paragraph("<b>Duck Inc</b>", styles['Normal']))
        story.append(Paragraph("World Leading Manufacturer of Rubber Ducks", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Customer and Quote info section
        info_data = [
            [Paragraph("<b>Quote For:</b>", styles['Normal']), 
             Paragraph("<b>Quote Details:</b>", styles['Normal'])],
            [Paragraph(customer['name'] if customer else quote['customer_id'], styles['Normal']),
             Paragraph(f"<b>Date:</b> {quote['created_at'][:10]}", styles['Normal'])],
        ]
        
        if customer and customer.get('company'):
            info_data.append([Paragraph(customer['company'], styles['Normal']), 
                            Paragraph(f"<b>Valid Until:</b> {quote['valid_until']}", styles['Normal'])])
        else:
            info_data.append(['', Paragraph(f"<b>Valid Until:</b> {quote['valid_until']}", styles['Normal'])])
        
        if customer and customer.get('email'):
            info_data.append([Paragraph(customer['email'], styles['Normal']), 
                            Paragraph(f"<b>Status:</b> {quote['status'].upper()}", styles['Normal'])])
        else:
            info_data.append(['', Paragraph(f"<b>Status:</b> {quote['status'].upper()}", styles['Normal'])])
        
        if quote.get('requested_delivery_date'):
            info_data.append(['', Paragraph(f"<b>Requested Delivery:</b> {quote['requested_delivery_date']}", styles['Normal'])])
        
        info_table = Table(info_data, colWidths=[3*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.4*inch))
        
        # Line items table
        line_items_data = [['Item (SKU)', 'Quantity', 'Unit Price', 'Total']]
        
        for line in lines:
            line_items_data.append([
                f"{line['name']} ({line['sku']})",
                f"{int(line['qty'])} {line.get('uom', 'ea')}",
                f"{quote['currency']} {line['unit_price']:.2f}",
                f"{quote['currency']} {line['line_total']:.2f}"
            ])
        
        line_items_table = Table(line_items_data, colWidths=[3*inch, 1*inch, 1.25*inch, 1.25*inch])
        line_items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(line_items_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Totals section
        totals_data = [
            ['Subtotal:', f"{quote['currency']} {quote['subtotal']:.2f}"],
        ]
        
        if quote['discount'] > 0:
            totals_data.append(['Discount:', f"-{quote['currency']} {quote['discount']:.2f}"])
        if quote['shipping'] > 0:
            totals_data.append(['Shipping:', f"{quote['currency']} {quote['shipping']:.2f}"])
        if quote['tax'] > 0:
            totals_data.append(['Tax:', f"{quote['currency']} {quote['tax']:.2f}"])
        
        totals_data.append(['<b>Total:</b>', f"<b>{quote['currency']} {quote['total']:.2f}</b>"])
        
        # Convert to Paragraphs
        totals_styled = [[Paragraph(cell, styles['Normal']) for cell in row] for row in totals_data]
        
        totals_table = Table(totals_styled, colWidths=[4.5*inch, 2*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#1e293b')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(totals_table)
        
        # Validity notice
        story.append(Spacer(1, 0.3*inch))
        validity_text = f"<b>This quotation is valid until {quote['valid_until']}</b>"
        story.append(Paragraph(validity_text, ParagraphStyle(
            'Validity',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#dc2626'),
            alignment=TA_CENTER,
        )))
        
        # Footer
        story.append(Spacer(1, 0.3*inch))
        footer_text = "<i>Thank you for considering Duck Inc for your rubber duck needs!</i>"
        story.append(Paragraph(footer_text, ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER,
        )))
        
        # Build PDF
        try:
            doc.build(story)
        except Exception as e:
            logger.error(f"Error building PDF: {e}", exc_info=True)
            raise
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes


class InvoiceService:
    """Service for invoice and payment operations."""

    @staticmethod
    def create_invoice(sales_order_id: str) -> Dict[str, Any]:
        """Create a draft invoice from a sales order, pulling pricing automatically."""
        with db_conn() as conn:
            # Validate the sales order exists
            so = conn.execute("SELECT * FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
            if not so:
                raise ValueError(f"Sales order {sales_order_id} not found")

            # Get customer for tax_id check
            customer = conn.execute("SELECT name, tax_id FROM customers WHERE id = ?", (so["customer_id"],)).fetchone()

            # Compute pricing from the sales order lines
            pricing_result = PricingService.compute_pricing(sales_order_id)
            p = pricing_result["pricing"]

            sim_time = SimulationService.get_current_time()
            inv_id = generate_id(conn, "INV", "invoices")

            conn.execute(
                "INSERT INTO invoices (id, sales_order_id, customer_id, invoice_date, due_date, subtotal, discount, shipping, tax, total, currency, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                (
                    inv_id,
                    sales_order_id,
                    so["customer_id"],
                    sim_time[:10],  # invoice_date = today
                    None,  # due_date set on issue
                    p["subtotal"],
                    p["discount"],
                    p["shipping"],
                    p.get("tax", 0.0),
                    p["total"],
                    p["currency"],
                    sim_time,
                ),
            )
            conn.commit()
            
            # Build message with optional warning
            message = f"📄 Invoice {inv_id} created for order {sales_order_id} — {p['currency']} {p['total']:.2f}"
            warning = None
            if customer and not customer["tax_id"]:
                warning = f"⚠️ Customer {customer['name']} has no tax_id/VAT number on file. The invoice will be created without it."
            
            return {
                "invoice_id": inv_id,
                "sales_order_id": sales_order_id,
                "customer_id": so["customer_id"],
                "total": p["total"],
                "currency": p["currency"],
                "status": "draft",
                "ui_url": ui_href("invoices", inv_id),
                "message": message,
                "warning": warning,
            }

    @staticmethod
    def issue_invoice(invoice_id: str) -> Dict[str, Any]:
        """Issue a draft invoice: sets due_date, status='issued', and generates PDF."""
        with db_conn() as conn:
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if not inv:
                raise ValueError(f"Invoice {invoice_id} not found")
            if inv["status"] != "draft":
                raise ValueError(f"Invoice {invoice_id} is '{inv['status']}', must be 'draft' to issue")

            sim_time = SimulationService.get_current_time()
            # due_date = invoice_date + payment terms
            from datetime import datetime, timedelta
            invoice_date = datetime.fromisoformat(inv["invoice_date"])
            due_date = (invoice_date + timedelta(days=config.INVOICE_PAYMENT_TERMS_DAYS)).strftime("%Y-%m-%d")

            conn.execute(
                "UPDATE invoices SET status = 'issued', due_date = ?, issued_at = ? WHERE id = ?",
                (due_date, sim_time, invoice_id),
            )
            conn.commit()
            
            # Generate and store PDF
            try:
                pdf_bytes = InvoiceService.generate_invoice_pdf(invoice_id)
                DocumentService.store_document(
                    entity_type="invoice",
                    entity_id=invoice_id,
                    document_type="invoice_pdf",
                    content=pdf_bytes,
                    filename=f"invoice_{invoice_id}.pdf",
                    notes="Generated when invoice was issued"
                )
            except Exception as e:
                logger.error(f"Failed to generate PDF for {invoice_id}: {e}")
                # Don't fail the issue operation if PDF generation fails
            
            return {
                "invoice_id": invoice_id,
                "status": "issued",
                "due_date": due_date,
                "ui_url": ui_href("invoices", invoice_id),
                "message": f"📨 Invoice {invoice_id} issued — due {due_date}",
            }

    @staticmethod
    def get_invoice(invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get full invoice details with customer, sales order lines, and payments."""
        with db_conn() as conn:
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if not inv:
                return None
            inv_dict = dict(inv)
            inv_dict["ui_url"] = ui_href("invoices", invoice_id)

            # Customer
            customer = conn.execute("SELECT * FROM customers WHERE id = ?", (inv["customer_id"],)).fetchone()
            customer_dict = dict(customer) if customer else None
            if customer_dict:
                customer_dict["ui_url"] = ui_href("customers", customer_dict["id"])

            # Sales order lines (computed, not stored)
            lines = dict_rows(conn.execute(
                "SELECT i.sku, sol.qty FROM sales_order_lines sol "
                "JOIN items i ON sol.item_id = i.id "
                "WHERE sol.sales_order_id = ?",
                (inv["sales_order_id"],),
            ).fetchall())

            # Sales order summary
            so = conn.execute("SELECT id, status, created_at FROM sales_orders WHERE id = ?", (inv["sales_order_id"],)).fetchone()
            so_dict = dict(so) if so else None
            if so_dict:
                so_dict["ui_url"] = ui_href("orders", so_dict["id"])

            # Payments
            payments = dict_rows(conn.execute(
                "SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date",
                (invoice_id,),
            ).fetchall())
            amount_paid = sum(p["amount"] for p in payments)

            return {
                "invoice": inv_dict,
                "customer": customer_dict,
                "sales_order": so_dict,
                "lines": lines,
                "payments": payments,
                "amount_paid": amount_paid,
                "balance_due": inv_dict["total"] - amount_paid,
            }

    @staticmethod
    def list_invoices(
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List invoices with optional filters."""
        filters: List[str] = []
        params: List[Any] = []
        if customer_id:
            filters.append("inv.customer_id = ?")
            params.append(customer_id)
        if status:
            filters.append("inv.status = ?")
            params.append(status)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        sql = (
            f"SELECT inv.*, c.name as customer_name, c.company as customer_company "
            f"FROM invoices inv LEFT JOIN customers c ON inv.customer_id = c.id "
            f"{where_clause} ORDER BY inv.created_at DESC LIMIT ?"
        )
        params.append(limit)
        with db_conn() as conn:
            rows = dict_rows(conn.execute(sql, params))
            for row in rows:
                row["ui_url"] = ui_href("invoices", row["id"])
            return {"invoices": rows}

    @staticmethod
    def record_payment(
        invoice_id: str,
        amount: float,
        payment_method: str = "bank_transfer",
        reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a payment against an invoice. Auto-marks as 'paid' when fully covered."""
        with db_conn() as conn:
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if not inv:
                raise ValueError(f"Invoice {invoice_id} not found")
            if inv["status"] not in ("issued", "overdue"):
                raise ValueError(f"Invoice {invoice_id} is '{inv['status']}', must be 'issued' or 'overdue' to accept payment")

            sim_time = SimulationService.get_current_time()
            pay_id = generate_id(conn, "PAY", "payments")
            conn.execute(
                "INSERT INTO payments (id, invoice_id, amount, payment_method, payment_date, reference, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (pay_id, invoice_id, amount, payment_method, sim_time[:10], reference, notes, sim_time),
            )

            # Check if fully paid
            total_paid = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()["total"]

            new_status = inv["status"]
            if total_paid >= inv["total"]:
                new_status = "paid"
                conn.execute(
                    "UPDATE invoices SET status = 'paid', paid_at = ? WHERE id = ?",
                    (sim_time, invoice_id),
                )

            conn.commit()
            return {
                "payment_id": pay_id,
                "invoice_id": invoice_id,
                "amount": amount,
                "total_paid": total_paid,
                "balance_due": inv["total"] - total_paid,
                "invoice_status": new_status,
                "ui_url": ui_href("invoices", invoice_id),
            }
            balance = inv["total"] - total_paid
            currency = inv["currency"]
            if new_status == "paid":
                result["message"] = f"💰 Payment {pay_id} of {currency} {amount:.2f} recorded on invoice {invoice_id}. ✅ Invoice fully paid!"
            else:
                result["message"] = f"💰 Payment {pay_id} of {currency} {amount:.2f} recorded on invoice {invoice_id}. Balance due: {currency} {balance:.2f}"
            return result

    @staticmethod
    def mark_overdue(sim_time: str) -> int:
        """Mark issued invoices as overdue if sim_time > due_date. Returns count updated."""
        with db_conn() as conn:
            cur = conn.execute(
                "UPDATE invoices SET status = 'overdue' "
                "WHERE status = 'issued' AND due_date IS NOT NULL AND due_date < ?",
                (sim_time[:10],),
            )
            conn.commit()
            return cur.rowcount

    @staticmethod
    def generate_invoice_pdf(invoice_id: str) -> bytes:
        """Generate a PDF for an invoice using ReportLab."""
        # Get invoice data
        invoice_data = InvoiceService.get_invoice(invoice_id)
        if not invoice_data:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        inv = invoice_data.get("invoice")
        customer = invoice_data.get("customer")
        lines = invoice_data.get("lines", [])
        payments = invoice_data.get("payments", [])
        
        if not inv:
            raise ValueError(f"Invoice data missing 'invoice' key")
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                              topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        # Container for PDF elements
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=30,
        )
        
        right_align_style = ParagraphStyle(
            'RightAlign',
            parent=styles['Normal'],
            alignment=TA_RIGHT,
        )
        
        # Title
        story.append(Paragraph(f"<b>INVOICE {inv['id']}</b>", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Company header
        story.append(Paragraph("<b>Duck Inc</b>", styles['Normal']))
        story.append(Paragraph("World Leading Manufacturer of Rubber Ducks", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Customer and Invoice info section
        info_data = [
            [Paragraph("<b>Bill To:</b>", styles['Normal']), 
             Paragraph("<b>Invoice Details:</b>", styles['Normal'])],
            [Paragraph(customer['name'] if customer else inv['customer_id'], styles['Normal']),
             Paragraph(f"<b>Date:</b> {inv['invoice_date'] or 'N/A'}", styles['Normal'])],
        ]
        
        if customer and customer.get('company'):
            info_data.append([Paragraph(customer['company'], styles['Normal']), 
                            Paragraph(f"<b>Due Date:</b> {inv['due_date'] or 'N/A'}", styles['Normal'])])
        else:
            info_data.append(['', Paragraph(f"<b>Due Date:</b> {inv['due_date'] or 'N/A'}", styles['Normal'])])
            
        if customer and customer.get('email'):
            info_data.append([Paragraph(customer['email'], styles['Normal']), 
                            Paragraph(f"<b>Status:</b> {inv['status'].upper()}", styles['Normal'])])
        else:
            info_data.append(['', Paragraph(f"<b>Status:</b> {inv['status'].upper()}", styles['Normal'])])
        
        info_table = Table(info_data, colWidths=[3*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.4*inch))
        
        # Line items table
        line_items_data = [['Item (SKU)', 'Quantity', 'Unit Price', 'Total']]
        
        # Get pricing details for each line
        with db_conn() as conn:
            for line in lines:
                item = conn.execute("SELECT * FROM items WHERE sku = ?", (line['sku'],)).fetchone()
                if item:
                    unit_price = item['unit_price']
                    line_total = unit_price * line['qty']
                    line_items_data.append([
                        f"{item['name']} ({line['sku']})",
                        str(int(line['qty'])),
                        f"{inv['currency']} {unit_price:.2f}",
                        f"{inv['currency']} {line_total:.2f}"
                    ])
        
        line_items_table = Table(line_items_data, colWidths=[3*inch, 1*inch, 1.25*inch, 1.25*inch])
        line_items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(line_items_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Totals section
        totals_data = [
            ['Subtotal:', f"{inv['currency']} {inv['subtotal']:.2f}"],
        ]
        
        if inv['discount'] > 0:
            totals_data.append(['Discount:', f"-{inv['currency']} {inv['discount']:.2f}"])
        if inv['shipping'] > 0:
            totals_data.append(['Shipping:', f"{inv['currency']} {inv['shipping']:.2f}"])
        if inv['tax'] > 0:
            totals_data.append(['Tax:', f"{inv['currency']} {inv['tax']:.2f}"])
        
        totals_data.append(['<b>Total:</b>', f"<b>{inv['currency']} {inv['total']:.2f}</b>"])
        
        if payments:
            amount_paid = sum(p['amount'] for p in payments)
            totals_data.append(['Amount Paid:', f"{inv['currency']} {amount_paid:.2f}"])
            balance = inv['total'] - amount_paid
            totals_data.append(['<b>Balance Due:</b>', f"<b>{inv['currency']} {balance:.2f}</b>"])
        
        # Convert to Paragraphs for styling
        totals_styled = [[Paragraph(cell, styles['Normal']) for cell in row] for row in totals_data]
        
        totals_table = Table(totals_styled, colWidths=[4.5*inch, 2*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#1e293b')),
            ('LINEABOVE', (0, -3), (-1, -3), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(totals_table)
        
        # Payment information if any
        if payments:
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("<b>Payment History:</b>", styles['Heading3']))
            story.append(Spacer(1, 0.1*inch))
            
            payment_data = [['Date', 'Method', 'Reference', 'Amount']]
            for payment in payments:
                payment_data.append([
                    payment['payment_date'][:10] if payment.get('payment_date') else 'N/A',
                    payment.get('payment_method', 'N/A'),
                    payment.get('reference', 'N/A'),
                    f"{inv['currency']} {payment['amount']:.2f}"
                ])
            
            payment_table = Table(payment_data, colWidths=[1.5*inch, 1.5*inch, 2*inch, 1.5*inch])
            payment_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(payment_table)
        
        # Footer
        story.append(Spacer(1, 0.5*inch))
        footer_text = "<i>Thank you for your business!</i>"
        story.append(Paragraph(footer_text, ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER,
        )))
        
        # Build PDF
        try:
            doc.build(story)
        except Exception as e:
            logger.error(f"Error building PDF: {e}", exc_info=True)
            raise
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes


class DocumentService:
    """Service for document storage and retrieval."""
    
    @staticmethod
    def store_document(
        entity_type: str,
        entity_id: str,
        document_type: str,
        content: bytes,
        filename: str,
        mime_type: str = "application/pdf",
        notes: Optional[str] = None
    ) -> str:
        """Store a document in the database."""
        with db_conn() as conn:
            sim_time = SimulationService.get_current_time()
            doc_id = generate_id(conn, "DOC", "documents")
            
            conn.execute(
                "INSERT INTO documents (id, entity_type, entity_id, document_type, content, mime_type, filename, generated_at, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_id, entity_type, entity_id, document_type, content, mime_type, filename, sim_time, notes)
            )
            conn.commit()
            return doc_id
    
    @staticmethod
    def get_document(entity_type: str, entity_id: str, document_type: str) -> Optional[Dict[str, Any]]:
        """Get the most recent document for an entity."""
        with db_conn() as conn:
            row = conn.execute(
                "SELECT id, entity_type, entity_id, document_type, content, mime_type, filename, generated_at, notes "
                "FROM documents "
                "WHERE entity_type = ? AND entity_id = ? AND document_type = ? "
                "ORDER BY generated_at DESC LIMIT 1",
                (entity_type, entity_id, document_type)
            ).fetchone()
            
            if not row:
                return None
            
            return {
                "id": row[0],
                "entity_type": row[1],
                "entity_id": row[2],
                "document_type": row[3],
                "content": row[4],
                "mime_type": row[5],
                "filename": row[6],
                "generated_at": row[7],
                "notes": row[8]
            }
    
    @staticmethod
    def list_documents(entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
        """List all documents for an entity (excluding content)."""
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT id, entity_type, entity_id, document_type, mime_type, filename, generated_at, notes "
                "FROM documents "
                "WHERE entity_type = ? AND entity_id = ? "
                "ORDER BY generated_at DESC",
                (entity_type, entity_id)
            ).fetchall()
            
            return [
                {
                    "id": row[0],
                    "entity_type": row[1],
                    "entity_id": row[2],
                    "document_type": row[3],
                    "mime_type": row[4],
                    "filename": row[5],
                    "generated_at": row[6],
                    "notes": row[7]
                }
                for row in rows
            ]


class StatsService:
    """Service for statistics operations."""
    
    @staticmethod
    def get_statistics(
        entity: str, 
        metric: str, 
        group_by: Optional[Union[str, List[str]]], 
        field: Optional[str], 
        status: Optional[str], 
        item_type: Optional[str], 
        warehouse: Optional[str], 
        city: Optional[str], 
        limit: int,
        return_chart: Optional[str] = None,
        chart_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get flexible statistics for any entity, optionally returning a chart.
        
        Args:
            entity: Entity type to query
            metric: Aggregation function (count, sum, avg, min, max)
            group_by: Field(s) to group by - string or list for multi-dimensional grouping
            field: Field to aggregate (required for sum/avg/min/max)
            status, item_type, warehouse, city: Optional filters
            limit: Max number of results
            return_chart: Optional chart type (pie, bar, line, stacked_bar, etc.)
            chart_title: Optional chart title
            
        Returns:
            If return_chart: {"chart_url": "...", "data": [...], ...}
            Otherwise: {"entity": "...", "results": [...], ...}
        """
        entity_config = {
            "customers": {"table": "customers", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["id"], "valid_groups": ["city", "company"], "date_fields": ["created_at"]},
            "sales_orders": {"table": "sales_orders", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["id"], "valid_groups": ["status", "customer_id"], "date_fields": ["created_at", "requested_delivery_date"]},
            "sales_order_lines": {"table": "sales_order_lines", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["qty"], "valid_groups": ["sales_order_id", "item_id"], "date_fields": []},
            "items": {"table": "items", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["unit_price"], "valid_groups": ["type"], "date_fields": []},
            "stock": {"table": "stock", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["on_hand"], "valid_groups": ["warehouse", "location", "item_id"], "date_fields": []},
            "production_orders": {"table": "production_orders", "join": "LEFT JOIN recipes ON production_orders.recipe_id = recipes.id", "field_mapping": {"qty": "recipes.output_qty"}, "date_field_table": None, "valid_fields": ["id", "qty"], "valid_groups": ["status", "item_id"], "date_fields": ["started_at", "completed_at", "eta_finish", "eta_ship"]},
            "shipments": {"table": "shipments", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["id"], "valid_groups": ["status"], "date_fields": ["planned_departure", "planned_arrival"]},
            "shipment_lines": {"table": "shipment_lines", "join": "LEFT JOIN shipments ON shipment_lines.shipment_id = shipments.id", "field_mapping": {}, "date_field_table": "shipments", "valid_fields": ["qty"], "valid_groups": ["shipment_id", "item_id"], "date_fields": ["planned_departure", "planned_arrival"]},
            "purchase_orders": {"table": "purchase_orders", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["qty"], "valid_groups": ["status", "item_id", "supplier_id"], "date_fields": ["ordered_at", "expected_delivery", "received_at"]},
            "invoices": {"table": "invoices", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["total", "subtotal"], "valid_groups": ["status", "customer_id"], "date_fields": ["invoice_date", "due_date", "issued_at", "paid_at", "created_at"]},
            "payments": {"table": "payments", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["amount"], "valid_groups": ["invoice_id", "payment_method"], "date_fields": ["payment_date", "created_at"]},
        }
        if entity not in entity_config:
            return {"error": f"Invalid entity: {entity}. Valid options: {', '.join(entity_config.keys())}"}
        
        config = entity_config[entity]
        table = config["table"]
        join_clause = config["join"] or ""
        field_mapping = config["field_mapping"]
        
        if metric == "count":
            select_clause = "COUNT(*) as value"
        elif metric in ["sum", "avg", "min", "max"]:
            if not field:
                return {"error": f"Field is required for {metric} operation"}
            if field not in config["valid_fields"]:
                # Provide helpful guidance for common mistakes
                if field == "qty" and entity == "sales_orders":
                    return {
                        "error": f"sales_orders has no qty field (quantities are in sales_order_lines). "
                                f"For quantity analysis:\n"
                                f"  - Total quantity: entity='sales_order_lines', metric='sum', field='qty'\n"
                                f"  - By item: add group_by='item_id'\n"
                                f"  - By order: add group_by='sales_order_id'"
                    }
                elif field == "qty" and entity == "shipments":
                    return {
                        "error": f"shipments has no qty field (quantities are in shipment_lines). "
                                f"For quantity analysis:\n"
                                f"  - Total quantity: entity='shipment_lines', metric='sum', field='qty'\n"
                                f"  - By item: add group_by='item_id'\n"
                                f"  - By shipment: add group_by='shipment_id'"
                    }
                else:
                    return {"error": f"Invalid field '{field}' for entity '{entity}'. Valid: {config['valid_fields']}"}
            actual_field = field_mapping.get(field, field)
            select_clause = f"{metric.upper()}({actual_field}) as value"
        else:
            return {"error": f"Invalid metric: {metric}. Valid options: count, sum, avg, min, max"}
        filters = []
        params: List[Any] = []
        if status:
            filters.append(f"{table}.status = ?")
            params.append(status)
        if item_type:
            filters.append(f"{table}.type = ?")
            params.append(item_type)
        if warehouse:
            filters.append(f"{table}.warehouse = ?")
            params.append(warehouse)
        if city:
            filters.append(f"{table}.city = ?")
            params.append(city)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        with db_conn() as conn:
            if group_by:
                # Handle multi-dimensional grouping (list of fields)
                if isinstance(group_by, list):
                    # Validate all fields
                    for gb_field in group_by:
                        if gb_field not in config["valid_groups"]:
                            return {"error": f"Invalid group_by field '{gb_field}' for entity '{entity}'. Valid: {config['valid_groups']}"}
                    
                    # Build multi-dimensional GROUP BY
                    select_fields = ", ".join([f"{table}.{gb_field}" for gb_field in group_by])
                    group_fields = ", ".join([f"{table}.{gb_field}" for gb_field in group_by])
                    sql = f"SELECT {select_fields}, {select_clause} FROM {table} {join_clause} {where_clause} GROUP BY {group_fields} ORDER BY value DESC LIMIT ?"
                    params.append(limit)
                    rows = dict_rows(conn.execute(sql, params))
                    
                    result = {"entity": entity, "metric": metric, "group_by": group_by, "results": rows}
                    
                    # If chart requested, generate it
                    if return_chart:
                        chart_result = StatsService._generate_chart_from_results(
                            return_chart, rows, group_by, chart_title, entity, metric
                        )
                        if "error" in chart_result:
                            return chart_result
                        result["chart_url"] = chart_result["chart_url"]
                        result["chart_filename"] = chart_result["chart_filename"]
                    
                    return result
                
                # Single group_by field (string)
                # Check for date grouping syntax: "date:field_name" or "month:field_name"
                if ":" in group_by:
                    period, field_name = group_by.split(":", 1)
                    if field_name not in config["date_fields"]:
                        # Special guidance for stock table
                        if entity == "stock":
                            return {
                                "error": f"stock table has no date fields (it's a current snapshot, not historical data). "
                                        f"For inventory changes over time, use transaction tables:\n"
                                        f"  - Production: entity='production_orders', metric='sum', field='qty', group_by='date:completed_at'\n"
                                        f"  - Shipments: entity='shipment_lines', metric='sum', field='qty', group_by='date:planned_departure'\n"
                                        f"  - Purchases: entity='purchase_orders', metric='sum', field='qty', group_by='date:received_at'"
                            }
                        return {"error": f"Invalid date field '{field_name}' for entity '{entity}'. Valid: {config['date_fields']}"}
                    
                    # Use date_field_table if specified (for joined tables), otherwise use main table
                    date_table = config.get("date_field_table") or table
                    
                    if period == "date":
                        group_expr = f"DATE({date_table}.{field_name})"
                        group_label = "date"
                    elif period == "month":
                        group_expr = f"strftime('%Y-%m', {date_table}.{field_name})"
                        group_label = "month"
                    elif period == "year":
                        group_expr = f"strftime('%Y', {date_table}.{field_name})"
                        group_label = "year"
                    else:
                        return {"error": f"Invalid time period '{period}'. Valid: date, month, year"}
                    
                    sql = f"SELECT {group_expr} as {group_label}, {select_clause} FROM {table} {join_clause} {where_clause} GROUP BY {group_expr} ORDER BY {group_label} LIMIT ?"
                    params.append(limit)
                    rows = dict_rows(conn.execute(sql, params))
                    
                    result = {"entity": entity, "metric": metric, "group_by": group_by, "results": rows}
                    
                    # If chart requested, generate it
                    if return_chart:
                        chart_result = StatsService._generate_chart_from_results(
                            return_chart, rows, group_by, chart_title, entity, metric
                        )
                        if "error" in chart_result:
                            return chart_result
                        result["chart_url"] = chart_result["chart_url"]
                        result["chart_filename"] = chart_result["chart_filename"]
                    
                    return result
                else:
                    # Regular field grouping
                    if group_by not in config["valid_groups"]:
                        return {"error": f"Invalid group_by '{group_by}' for entity '{entity}'. Valid: {config['valid_groups']}"}
                    sql = f"SELECT {table}.{group_by}, {select_clause} FROM {table} {join_clause} {where_clause} GROUP BY {table}.{group_by} ORDER BY value DESC LIMIT ?"
                    params.append(limit)
                    rows = dict_rows(conn.execute(sql, params))
                    
                    result = {"entity": entity, "metric": metric, "group_by": group_by, "results": rows}
                    
                    # If chart requested, generate it
                    if return_chart:
                        chart_result = StatsService._generate_chart_from_results(
                            return_chart, rows, group_by, chart_title, entity, metric
                        )
                        if "error" in chart_result:
                            return chart_result
                        result["chart_url"] = chart_result["chart_url"]
                        result["chart_filename"] = chart_result["chart_filename"]
                    
                    return result
            else:
                sql = f"SELECT {select_clause} FROM {table} {join_clause} {where_clause}"
                result = conn.execute(sql, params).fetchone()
                return {"entity": entity, "metric": metric, "value": result["value"] if result["value"] is not None else 0}
    
    @staticmethod
    def _generate_chart_from_results(
        chart_type: str,
        rows: List[Dict[str, Any]],
        group_by: Union[str, List[str]],
        chart_title: Optional[str],
        entity: str,
        metric: str
    ) -> Dict[str, Any]:
        """Generate chart from query results."""
        if not rows:
            return {"error": "No data to chart"}
        
        # Multi-dimensional grouping (for stacked charts)
        if isinstance(group_by, list):
            if len(group_by) != 2:
                return {"error": "Multi-dimensional charting requires exactly 2 group_by fields"}
            
            # Pivot data: first field becomes labels, second becomes series
            label_field = group_by[0]
            series_field = group_by[1]
            
            # Extract unique values for labels and series
            labels_set = set()
            series_set = set()
            for row in rows:
                labels_set.add(str(row[label_field]))
                series_set.add(str(row[series_field]))
            
            labels = sorted(list(labels_set))
            series_names = sorted(list(series_set))
            
            # Build series data
            series_data = []
            for series_name in series_names:
                values = []
                for label in labels:
                    # Find matching row
                    value = 0
                    for row in rows:
                        if str(row[label_field]) == label and str(row[series_field]) == series_name:
                            value = row.get("value", 0)
                            break
                    values.append(value)
                series_data.append({"name": series_name, "values": values})
            
            # Generate chart
            title = chart_title or f"{entity.replace('_', ' ').title()} by {label_field} and {series_field}"
            chart_result = chart_service.generate_chart(
                chart_type=chart_type,
                labels=labels,
                series=series_data,
                title=title
            )
            return {
                "chart_url": chart_result["url"],
                "chart_filename": chart_result["filename"]
            }
        
        # Single-dimensional grouping
        else:
            # Extract label field name
            if ":" in group_by:
                # Date grouping: "date:field_name" -> label is "date", "month", or "year"
                period = group_by.split(":", 1)[0]
                label_field = period
            else:
                label_field = group_by
            
            labels = [str(row[label_field]) for row in rows]
            values = [row.get("value", 0) for row in rows]
            
            title = chart_title or f"{entity.replace('_', ' ').title()} by {label_field}"
            chart_result = chart_service.generate_chart(
                chart_type=chart_type,
                labels=labels,
                values=values,
                title=title
            )
            return {
                "chart_url": chart_result["url"],
                "chart_filename": chart_result["filename"]
            }


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


class ChartService:
    """Service for generating chart images."""
    
    @staticmethod
    def generate_chart(
        chart_type: str,
        labels: List[str],
        values: Optional[List[float]] = None,
        series: Optional[List[Dict[str, Any]]] = None,
        title: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate a chart image and return the filename.
        
        Args:
            chart_type: Type of chart - pie, bar, bar_horizontal, line, scatter, area, stacked_area, stacked_bar, waterfall, treemap
            labels: List of labels for x-axis or pie slices
            values: List of numeric values (for backward compatibility, single series)
            series: List of series dicts: [{"name": "Q1", "values": [10, 20, 30]}, ...]
            title: Optional chart title
            
        Returns:
            Dictionary with filename and full_path
        """
        valid_types = ["pie", "bar", "bar_horizontal", "line", "scatter", "area", "stacked_area", "stacked_bar", "waterfall", "treemap"]
        if chart_type not in valid_types:
            raise ValueError(f"Unsupported chart type: {chart_type}. Valid: {', '.join(valid_types)}")
        
        # Convert single values to series format for uniform handling
        if values is not None:
            series = [{"name": "", "values": values}]
        elif series is None:
            raise ValueError("Must provide either 'values' or 'series'")
        
        # Validate data
        for s in series:
            if len(s["values"]) != len(labels):
                raise ValueError(f"Series '{s.get('name', '')}' values length must match labels length")
        
        # Generate filename: {YYYYMMDD_HHMMSS}_{uuid}.png
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_uuid = str(uuid.uuid4())
        filename = f"{timestamp}_{file_uuid}.png"
        
        # Ensure tmp/charts directory exists
        charts_dir = os.path.join(os.path.dirname(__file__), "tmp", "charts")
        os.makedirs(charts_dir, exist_ok=True)
        
        full_path = os.path.join(charts_dir, filename)
        
        # Create chart based on type
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if chart_type == "pie":
            # Pie charts only support single series
            values_list = series[0]["values"]
            
            def make_autopct(values):
                def autopct(pct):
                    total = sum(values)
                    val = int(round(pct * total / 100.0))
                    return f'{val}\n({pct:.1f}%)'
                return autopct
            
            ax.pie(values_list, labels=labels, autopct=make_autopct(values_list), startangle=90)
            ax.axis('equal')
        
        elif chart_type == "bar":
            x = range(len(labels))
            width = 0.8 / len(series) if len(series) > 1 else 0.6
            
            for idx, s in enumerate(series):
                offset = (idx - len(series) / 2 + 0.5) * width
                bars = ax.bar([i + offset for i in x], s["values"], width, label=s["name"])
                # Add value labels on bars
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{int(height)}', ha='center', va='bottom', fontsize=8)
            
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            if len(series) > 1 or series[0]["name"]:
                ax.legend()
        
        elif chart_type == "bar_horizontal":
            y = range(len(labels))
            height = 0.8 / len(series) if len(series) > 1 else 0.6
            
            for idx, s in enumerate(series):
                offset = (idx - len(series) / 2 + 0.5) * height
                bars = ax.barh([i + offset for i in y], s["values"], height, label=s["name"])
                # Add value labels on bars
                for bar in bars:
                    width = bar.get_width()
                    ax.text(width, bar.get_y() + bar.get_height()/2.,
                           f'{int(width)}', ha='left', va='center', fontsize=8)
            
            ax.set_yticks(y)
            ax.set_yticklabels(labels)
            if len(series) > 1 or series[0]["name"]:
                ax.legend()
        
        elif chart_type == "line":
            x = range(len(labels))
            
            for s in series:
                ax.plot(x, s["values"], marker='o', label=s["name"], linewidth=2)
                # Add value labels on points
                for i, val in enumerate(s["values"]):
                    ax.text(i, val, f'{int(val)}', ha='center', va='bottom', fontsize=8)
            
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
            if len(series) > 1 or series[0]["name"]:
                ax.legend()
        
        elif chart_type == "scatter":
            for s in series:
                ax.scatter(range(len(labels)), s["values"], label=s["name"], s=100, alpha=0.6)
            
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
            if len(series) > 1 or series[0]["name"]:
                ax.legend()
        
        elif chart_type == "area":
            x = range(len(labels))
            
            for s in series:
                ax.fill_between(x, s["values"], alpha=0.4, label=s["name"])
                ax.plot(x, s["values"], linewidth=2)
            
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
            if len(series) > 1 or series[0]["name"]:
                ax.legend()
        
        elif chart_type == "stacked_area":
            x = range(len(labels))
            
            # Stack the areas
            cumulative = [0] * len(labels)
            for s in series:
                new_cumulative = [cumulative[i] + s["values"][i] for i in range(len(labels))]
                ax.fill_between(x, cumulative, new_cumulative, alpha=0.6, label=s["name"])
                cumulative = new_cumulative
            
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
            ax.legend()
        
        elif chart_type == "stacked_bar":
            x = range(len(labels))
            width = 0.6
            
            # Stack the bars
            cumulative = [0] * len(labels)
            for s in series:
                ax.bar(x, s["values"], width, bottom=cumulative, label=s["name"])
                cumulative = [cumulative[i] + s["values"][i] for i in range(len(labels))]
            
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.legend()
        
        elif chart_type == "waterfall":
            # Waterfall chart shows cumulative effect of sequential values
            values_list = series[0]["values"]
            cumulative = 0
            cumulative_values = []
            colors = []
            
            for val in values_list:
                cumulative_values.append(cumulative)
                cumulative += val
                colors.append('green' if val >= 0 else 'red')
            
            # Draw bars from cumulative base
            bars = ax.bar(range(len(labels)), values_list, bottom=cumulative_values, color=colors, alpha=0.7)
            
            # Add value labels
            for i, (bar, val) in enumerate(zip(bars, values_list)):
                height = cumulative_values[i] + val
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(val):+d}', ha='center', va='bottom' if val >= 0 else 'top', fontsize=8)
            
            # Draw connecting lines
            for i in range(len(labels) - 1):
                ax.plot([i + 0.4, i + 0.6], 
                       [cumulative_values[i] + values_list[i], cumulative_values[i] + values_list[i]], 
                       'k--', linewidth=0.5, alpha=0.5)
            
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.axhline(y=0, color='black', linewidth=0.8)
        
        elif chart_type == "treemap":
            import squarify
            
            # Treemaps only support single series
            values_list = series[0]["values"]
            
            # Filter out zero and negative values (squarify can't handle them)
            filtered_data = [(label, val) for label, val in zip(labels, values_list) if val > 0]
            
            if not filtered_data:
                raise ValueError("Treemap requires at least one positive value")
            
            filtered_labels, filtered_values = zip(*filtered_data)
            
            # Generate colors
            colors = plt.cm.Set3(range(len(filtered_labels)))
            
            # Create labels with values
            labels_with_values = [f"{label}\n{int(val)}" for label, val in zip(filtered_labels, filtered_values)]
            
            # Create treemap
            squarify.plot(sizes=filtered_values, label=labels_with_values, alpha=0.8, color=colors, text_kwargs={'fontsize': 9})
            ax.axis('off')
        
        if title:
            ax.set_title(title)
        
        plt.tight_layout()
        plt.savefig(full_path, dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        return {
            "filename": filename,
            "full_path": full_path,
            "url": f"{config.API_BASE}/api/charts/{filename}"
        }


class PendingActionService:
    """Human-in-the-loop confirmation gate for all mutations.
    
    Every mutating MCP tool creates a pending action instead of executing directly.
    The action stores the intent (type + params + human-readable summary).
    Execution only happens when the user explicitly confirms via action_confirm.
    
    Compound actions (e.g. accept_quote which creates a sales order)
    are handled by typed executors that know the internal dependency recipe.
    """
    
    # Map action_type -> executor function.
    # Each executor receives params dict + a shared db connection (for transaction safety)
    # and returns the result dict that would normally come from the service.
    _executors: Dict[str, Any] = {}

    @staticmethod
    def _register_executors():
        """Wire up the dispatch table. Called once at module load."""
        
        def _exec_create_customer(params, conn):
            return CustomerService.create_customer(**params)
        
        def _exec_update_customer(params, conn):
            return CustomerService.update_customer(**params)
        
        def _exec_link_shipment(params, conn):
            return SalesService.link_shipment(params["sales_order_id"], params["shipment_id"])
        
        def _exec_create_shipment(params, conn):
            return LogisticsService.create_shipment(
                params.get("ship_from"), params.get("ship_to"),
                params.get("planned_departure"), params.get("planned_arrival"),
                params.get("packages"), params.get("reference"),
            )
        
        def _exec_create_production_order(params, conn):
            return ProductionService.create_order(params["recipe_id"], params.get("notes"))
        
        def _exec_start_production(params, conn):
            return ProductionService.start_order(params["production_order_id"])
        
        def _exec_complete_production(params, conn):
            return ProductionService.complete_order(
                params["production_order_id"], params["qty_produced"],
                params.get("warehouse", "MAIN"), params.get("location", "FG-A"),
            )
        
        def _exec_create_purchase_order(params, conn):
            return PurchaseService.create_order(
                params["item_sku"], params["qty"], params.get("supplier_name"),
            )
        
        def _exec_restock_materials(params, conn):
            return PurchaseService.restock_materials()
        
        def _exec_receive_purchase_order(params, conn):
            return PurchaseService.receive(
                params["purchase_order_id"],
                params.get("warehouse", "MAIN"), params.get("location", "RM-A"),
            )
        
        def _exec_create_quote(params, conn):
            return QuoteService.create_quote(
                params["customer_id"], params.get("requested_delivery_date"),
                params.get("ship_to"), params["lines"], params.get("note"),
                params.get("valid_days", 30)
            )
        
        def _exec_send_quote(params, conn):
            return QuoteService.send_quote(params["quote_id"])
        
        def _exec_accept_quote(params, conn):
            return QuoteService.accept_quote(params["quote_id"])
        
        def _exec_reject_quote(params, conn):
            return QuoteService.reject_quote(params["quote_id"], params.get("reason"))
        
        def _exec_revise_quote(params, conn):
            return QuoteService.revise_quote(params["quote_id"], params.get("changes"))
        
        def _exec_create_invoice(params, conn):
            return InvoiceService.create_invoice(params["sales_order_id"])
        
        def _exec_issue_invoice(params, conn):
            return InvoiceService.issue_invoice(params["invoice_id"])
        
        def _exec_record_payment(params, conn):
            return InvoiceService.record_payment(
                params["invoice_id"], params["amount"],
                params.get("payment_method", "bank_transfer"),
                params.get("reference"), params.get("notes"),
            )
        
        PendingActionService._executors = {
            "create_customer": _exec_create_customer,
            "update_customer": _exec_update_customer,
            "link_shipment": _exec_link_shipment,
            "create_shipment": _exec_create_shipment,
            "create_production_order": _exec_create_production_order,
            "start_production": _exec_start_production,
            "complete_production": _exec_complete_production,
            "create_purchase_order": _exec_create_purchase_order,
            "restock_materials": _exec_restock_materials,
            "receive_purchase_order": _exec_receive_purchase_order,
            "create_quote": _exec_create_quote,
            "send_quote": _exec_send_quote,
            "accept_quote": _exec_accept_quote,
            "reject_quote": _exec_reject_quote,
            "revise_quote": _exec_revise_quote,
            "create_invoice": _exec_create_invoice,
            "issue_invoice": _exec_issue_invoice,
            "record_payment": _exec_record_payment,
        }
    
    @staticmethod
    def create(action_type: str, params: Dict[str, Any], summary: str) -> Dict[str, Any]:
        """Create a pending action and return it for the LLM to present."""
        import json as _json
        if action_type not in PendingActionService._executors:
            raise ValueError(f"Unknown action type: {action_type}")
        with db_conn() as conn:
            action_id = generate_id(conn, "ACT", "pending_actions")
            sim_time = SimulationService.get_current_time()
            conn.execute(
                "INSERT INTO pending_actions (id, action_type, params, summary, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                (action_id, action_type, _json.dumps(params, default=str), summary, sim_time),
            )
            conn.commit()
            return {
                "action_id": action_id,
                "action_type": action_type,
                "summary": summary,
                "params": params,
                "status": "pending",
                "message": f"⏳ Pending action {action_id}: {summary}. Waiting for user confirmation.",
            }
    
    @staticmethod
    def confirm(action_id: str) -> Dict[str, Any]:
        """Execute a pending action inside a transaction. Returns the real service result."""
        import json as _json
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM pending_actions WHERE id = ?", (action_id,)).fetchone()
            if not row:
                raise ValueError(f"Action {action_id} not found")
            if row["status"] != "pending":
                raise ValueError(f"Action {action_id} is already {row['status']}")
            
            action_type = row["action_type"]
            params = _json.loads(row["params"])
            executor = PendingActionService._executors.get(action_type)
            if not executor:
                raise ValueError(f"No executor for action type: {action_type}")
            
            # Execute — the service methods manage their own db connections,
            # so we just call them and record the outcome.
            try:
                result = executor(params, conn)
                sim_time = SimulationService.get_current_time()
                conn.execute(
                    "UPDATE pending_actions SET status = 'confirmed', result = ?, resolved_at = ? WHERE id = ?",
                    (_json.dumps(result, default=str), sim_time, action_id),
                )
                conn.commit()
                result["action_id"] = action_id
                result["action_status"] = "confirmed"
                return result
            except Exception as exc:
                conn.execute(
                    "UPDATE pending_actions SET status = 'rejected', result = ?, resolved_at = ? WHERE id = ?",
                    (_json.dumps({"error": str(exc)}, default=str), SimulationService.get_current_time(), action_id),
                )
                conn.commit()
                raise
    
    @staticmethod
    def reject(action_id: str) -> Dict[str, Any]:
        """Reject (cancel) a pending action."""
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM pending_actions WHERE id = ?", (action_id,)).fetchone()
            if not row:
                raise ValueError(f"Action {action_id} not found")
            if row["status"] != "pending":
                raise ValueError(f"Action {action_id} is already {row['status']}")
            sim_time = SimulationService.get_current_time()
            conn.execute(
                "UPDATE pending_actions SET status = 'rejected', resolved_at = ? WHERE id = ?",
                (sim_time, action_id),
            )
            conn.commit()
            return {
                "action_id": action_id,
                "status": "rejected",
                "message": f"❌ Action {action_id} rejected and will not be executed.",
            }
    
    @staticmethod
    def list_pending() -> Dict[str, Any]:
        """List all pending actions."""
        import json as _json
        with db_conn() as conn:
            rows = dict_rows(
                conn.execute(
                    "SELECT id, action_type, summary, status, created_at, resolved_at FROM pending_actions ORDER BY created_at DESC"
                )
            )
            return {"actions": rows}
    
    @staticmethod
    def get(action_id: str) -> Dict[str, Any]:
        """Get full details of a pending action."""
        import json as _json
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM pending_actions WHERE id = ?", (action_id,)).fetchone()
            if not row:
                raise ValueError(f"Action {action_id} not found")
            result = dict(row)
            result["params"] = _json.loads(result["params"]) if result["params"] else {}
            result["result"] = _json.loads(result["result"]) if result["result"] else None
            return result


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
quote_service = QuoteService()
invoice_service = InvoiceService()
document_service = DocumentService()
stats_service = StatsService()
admin_service = AdminService()
chart_service = ChartService()
pending_action_service = PendingActionService()
PendingActionService._register_executors()
