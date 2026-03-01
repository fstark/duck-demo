"""Service for pricing and quoting operations."""

from typing import Any, Dict, List, Optional

import config
from services._base import db_conn
from utils import eta_from_days, parse_date


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
        from services.inventory import inventory_service

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
                qty = int(row["qty"])
                total_qty += qty
                unit_price = PricingService.get_unit_price(row["item_id"])
                line_total = qty * unit_price
                subtotal += line_total
                line_totals.append({"sku": row["sku"], "qty": qty, "unit_price": unit_price, "line_total": line_total})

            discount = config.PRICING_VOLUME_DISCOUNT_PCT * subtotal if total_qty >= config.PRICING_VOLUME_QTY_THRESHOLD else 0.0
            shipping = 0.0 if subtotal >= config.PRICING_FREE_SHIPPING_THRESHOLD else config.PRICING_FLAT_SHIPPING
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
                    "shipping": shipping,
                    "shipping_note": "Free shipping threshold" if shipping == 0 else "Flat shipping",
                    "total": total,
                },
            }

    @staticmethod
    def calculate_quote_options(sku: str, qty: int, delivery_date: Optional[str], allowed_subs: List[str]) -> Dict[str, Any]:
        """Generate quote / fulfillment options for a request."""
        from services.catalog import catalog_service
        from services.inventory import inventory_service

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


pricing_service = PricingService()
