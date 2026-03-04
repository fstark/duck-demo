"""Service for sales order operations."""

from typing import Any, Dict, List, Optional
from types import SimpleNamespace

from db import dict_rows, generate_id
from utils import ship_to_columns, ui_href
from services._base import db_conn
from services.catalog import catalog_service
from services.simulation import simulation_service
from services.pricing import pricing_service


def create_order(
    customer_id: str,
    requested_delivery_date: Optional[str],
    ship_to: Optional[Dict[str, Any]],
    lines: Optional[List[Dict[str, Any]]],
    note: Optional[str],
    quote_id: Optional[str] = None,
    pricing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a draft sales order with lines and frozen pricing.

    When created from a quote, *pricing* carries the frozen totals and each
    line dict includes ``unit_price`` and ``line_total``.
    """
    if not lines:
        raise ValueError("lines required")
    if not quote_id:
        raise ValueError("quote_id is required — every sales order must originate from a quote")
    ship_to = ship_to or {}
    with db_conn() as conn:
        so_id = generate_id(conn, "SO", "sales_orders")
        sim_time = simulation_service.get_current_time()

        # Resolve pricing: use frozen quote pricing if provided, else compute
        if pricing:
            p = pricing
        else:
            # Fallback: compute from catalog (should not happen in normal flow)
            subtotal = 0.0
            total_qty = 0
            for line in lines:
                item = catalog_service.load_item(line["sku"])
                if not item:
                    raise ValueError(f"Unknown SKU {line['sku']}")
                qty = int(line["qty"])
                up = pricing_service.get_unit_price(item["id"])
                line["unit_price"] = up
                line["line_total"] = up * qty
                subtotal += line["line_total"]
                total_qty += qty
            import config as _cfg
            discount = _cfg.PRICING_VOLUME_DISCOUNT_PCT * subtotal if total_qty >= _cfg.PRICING_VOLUME_QTY_THRESHOLD else 0.0
            shipping = 0.0 if subtotal >= _cfg.PRICING_FREE_SHIPPING_THRESHOLD else _cfg.PRICING_FLAT_SHIPPING
            p = {"subtotal": subtotal, "discount": discount, "shipping": shipping, "tax": 0.0, "total": subtotal - discount + shipping, "currency": _cfg.PRICING_CURRENCY}

        conn.execute(
            "INSERT INTO sales_orders (id, quote_id, customer_id, requested_delivery_date, "
            "ship_to_line1, ship_to_line2, ship_to_postal_code, ship_to_city, ship_to_country, "
            "note, subtotal, discount, shipping, tax, total, currency, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (so_id, quote_id, customer_id, requested_delivery_date,
             *ship_to_columns(ship_to),
             note, p["subtotal"], p["discount"], p["shipping"], p.get("tax", 0.0),
             p["total"], p["currency"], "draft", sim_time))

        line_results = []
        for idx, line in enumerate(lines, start=1):
            item = catalog_service.load_item(line["sku"])
            if not item:
                raise ValueError(f"Unknown SKU {line['sku']}")
            line_id = f"{so_id}-{idx:02d}"
            unit_price = line.get("unit_price") or pricing_service.get_unit_price(item["id"])
            line_total = line.get("line_total") or (unit_price * int(line["qty"]))
            conn.execute(
                "INSERT INTO sales_order_lines (id, sales_order_id, item_id, qty, unit_price, line_total) VALUES (?, ?, ?, ?, ?, ?)",
                (line_id, so_id, item["id"], int(line["qty"]), unit_price, line_total))
            line_results.append({"line_id": line_id, "sku": line["sku"], "qty": int(line["qty"]), "unit_price": unit_price, "line_total": line_total})
        conn.commit()
        return {"sales_order_id": so_id, "status": "draft", "lines": line_results, "total": p["total"], "currency": p["currency"], "ui_url": ui_href("orders", so_id)}


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
            sales_orders.append({"sales_order_id": row["id"], "quote_id": row["quote_id"], "customer_id": row["customer_id"], "customer_name": customer_name, "customer_company": customer_company, "created_at": row["created_at"], "summary": summary, "fulfillment_state": fulfillment_state, "lines": lines, "total": row["total"], "currency": row["currency"], "ui_url": ui_href("orders", row["id"])})
        return {"sales_orders": sales_orders}


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
        lines = dict_rows(conn.execute("SELECT i.sku, sol.qty, sol.unit_price, sol.line_total FROM sales_order_lines sol JOIN items i ON sol.item_id = i.id WHERE sol.sales_order_id = ?", (sales_order_id,)).fetchall())
        pricing = {
            "currency": order["currency"],
            "subtotal": order["subtotal"],
            "discount": order["discount"],
            "shipping": order["shipping"],
            "tax": order["tax"],
            "total": order["total"],
            "lines": lines,
        }
        shipments = dict_rows(conn.execute("SELECT s.* FROM sales_order_shipments sos JOIN shipments s ON s.id = sos.shipment_id WHERE sos.sales_order_id = ? ORDER BY s.planned_departure", (sales_order_id,)).fetchall())
        order_dict = dict(order)
        order_dict["ui_url"] = ui_href("orders", sales_order_id)
        for shipment in shipments:
            shipment["ui_url"] = ui_href("shipments", shipment["id"])
        return {"sales_order": order_dict, "customer": customer_dict, "lines": lines, "pricing": pricing, "shipments": shipments}


def link_shipment(sales_order_id: str, shipment_id: str) -> Dict[str, Any]:
    """Link an existing shipment to a sales order."""
    with db_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO sales_order_shipments (sales_order_id, shipment_id) VALUES (?, ?)", (sales_order_id, shipment_id))
        conn.commit()
        return {"status": "linked"}


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


def complete_order(sales_order_id: str) -> Dict[str, Any]:
    """Mark a sales order as completed."""
    with db_conn() as conn:
        order = conn.execute("SELECT * FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
        if not order:
            raise ValueError(f"Sales order {sales_order_id} not found")
        if order["status"] == "completed":
            raise ValueError(f"Sales order {sales_order_id} already completed")
        if order["status"] != "confirmed":
            raise ValueError(f"Sales order {sales_order_id} must be confirmed before completing (current status: {order['status']})")
        conn.execute("UPDATE sales_orders SET status = 'completed' WHERE id = ?", (sales_order_id,))
        conn.commit()
        return {
            "sales_order_id": sales_order_id,
            "status": "completed",
            "message": f"Sales order {sales_order_id} completed",
            "ui_url": ui_href("orders", sales_order_id),
        }


def get_order_timeline(sales_order_id: str) -> Optional[Dict[str, Any]]:
    """Load the full lifecycle timeline for a sales order.

    Aggregates: quote revision chain → SO → production orders (with
    operations and wait-log) → shipments → invoices.
    """
    with db_conn() as conn:
        # ---- Sales order ----
        so = conn.execute("SELECT * FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
        if not so:
            return None

        # ---- Quote revision chain ----
        quotes: List[Dict[str, Any]] = []
        if so["quote_id"]:
            # Walk backwards through supersedes_quote_id
            seen: set = set()
            q_id: Optional[str] = so["quote_id"]
            while q_id and q_id not in seen:
                seen.add(q_id)
                q_row = conn.execute(
                    "SELECT id, revision_number, status, created_at, sent_at, "
                    "accepted_at, rejected_at, supersedes_quote_id FROM quotes WHERE id = ?",
                    (q_id,),
                ).fetchone()
                if not q_row:
                    break
                quotes.append(dict(q_row))
                q_id = q_row["supersedes_quote_id"]
            quotes.reverse()  # oldest first

        # ---- Production orders + operations + waits ----
        mo_rows = conn.execute(
            "SELECT po.*, i.sku as item_sku, i.name as item_name "
            "FROM production_orders po "
            "LEFT JOIN items i ON po.item_id = i.id "
            "WHERE po.sales_order_id = ? ORDER BY po.id",
            (sales_order_id,),
        ).fetchall()
        production_orders = []
        for mo in mo_rows:
            mo_dict = dict(mo)
            ops = [dict(r) for r in conn.execute(
                "SELECT id, sequence_order, operation_name, duration_hours, "
                "work_center, status, started_at, completed_at, blocked_reason, blocked_at "
                "FROM production_operations WHERE production_order_id = ? ORDER BY sequence_order",
                (mo["id"],),
            ).fetchall()]
            waits = [dict(r) for r in conn.execute(
                "SELECT id, production_operation_id, reason_type, reason_ref, "
                "started_at, resolved_at FROM production_wait_log "
                "WHERE production_order_id = ? ORDER BY started_at",
                (mo["id"],),
            ).fetchall()]
            mo_dict["operations"] = ops
            mo_dict["waits"] = waits
            production_orders.append(mo_dict)

        # ---- Shipments ----
        shipments = [dict(r) for r in conn.execute(
            "SELECT s.id, s.status, s.planned_departure, s.planned_arrival, "
            "s.dispatched_at, s.delivered_at "
            "FROM sales_order_shipments sos "
            "JOIN shipments s ON s.id = sos.shipment_id "
            "WHERE sos.sales_order_id = ? ORDER BY s.planned_departure",
            (sales_order_id,),
        ).fetchall()]

        # ---- Invoices ----
        invoices = [dict(r) for r in conn.execute(
            "SELECT id, status, created_at, invoice_date, issued_at, "
            "due_date, paid_at, total "
            "FROM invoices WHERE sales_order_id = ? ORDER BY created_at",
            (sales_order_id,),
        ).fetchall()]

        return {
            "sales_order_id": sales_order_id,
            "sales_order": {
                "id": so["id"],
                "status": so["status"],
                "created_at": so["created_at"],
                "requested_delivery_date": so["requested_delivery_date"],
            },
            "quotes": quotes,
            "production_orders": production_orders,
            "shipments": shipments,
            "invoices": invoices,
        }


def get_fulfillment_sources(sales_order_id: str) -> Optional[Dict[str, Any]]:
    """Trace actual stock sources for every dispatched/delivered shipment.

    For each shipment linked to this SO, joins stock_movements to show
    which batches (stock records) were consumed and which production
    orders or purchase orders originally created those batches.

    Returns None if the SO doesn't exist, or a dict with an empty
    ``shipments`` list if nothing has shipped yet.
    """
    with db_conn() as conn:
        so = conn.execute("SELECT id FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
        if not so:
            return None

        # Planned MO ids for this SO (to flag cross-order fulfillment)
        planned_mo_ids = {
            r[0] for r in conn.execute(
                "SELECT id FROM production_orders WHERE sales_order_id = ?",
                (sales_order_id,),
            ).fetchall()
        }

        # Shipments that have actually dispatched
        ship_rows = conn.execute(
            "SELECT s.id, s.status, s.dispatched_at "
            "FROM sales_order_shipments sos "
            "JOIN shipments s ON s.id = sos.shipment_id "
            "WHERE sos.sales_order_id = ? AND s.status IN ('in_transit', 'delivered') "
            "ORDER BY s.dispatched_at",
            (sales_order_id,),
        ).fetchall()

        shipments = []
        for ship in ship_rows:
            # Trace each deduction back to its source batch
            source_rows = conn.execute(
                "SELECT sm_out.item_id, i.sku AS item_sku, i.name AS item_name, "
                "       -sm_out.qty AS qty_taken, sm_out.stock_id, "
                "       sm_in.movement_type AS source_type, "
                "       sm_in.reference_id AS source_id, "
                "       sm_in.timestamp AS source_timestamp "
                "FROM stock_movements sm_out "
                "JOIN items i ON sm_out.item_id = i.id "
                "LEFT JOIN stock_movements sm_in "
                "  ON sm_in.stock_id = sm_out.stock_id "
                "  AND sm_in.movement_type IN ('production_in', 'purchase_in', 'adjustment') "
                "WHERE sm_out.reference_type = 'shipment' "
                "  AND sm_out.reference_id = ? "
                "ORDER BY i.sku, sm_in.timestamp",
                (ship["id"],),
            ).fetchall()

            sources = []
            for r in source_rows:
                is_cross_order = (
                    r["source_type"] == "production_in"
                    and r["source_id"] not in planned_mo_ids
                )
                sources.append({
                    "item_sku": r["item_sku"],
                    "item_name": r["item_name"],
                    "qty_taken": r["qty_taken"],
                    "stock_id": r["stock_id"],
                    "source_type": r["source_type"],
                    "source_id": r["source_id"],
                    "source_timestamp": r["source_timestamp"],
                    "cross_order": is_cross_order,
                })

            shipments.append({
                "shipment_id": ship["id"],
                "status": ship["status"],
                "dispatched_at": ship["dispatched_at"],
                "sources": sources,
            })

        return {
            "sales_order_id": sales_order_id,
            "shipments": shipments,
        }


def get_supply_chain_trace(sales_order_id: str) -> Optional[Dict[str, Any]]:
    """Trace the full supply chain DAG for a fulfilled sales order.

    Walks backwards from shipment(s) through:
      Shipment → FG batches (shipment_out)
              → MOs that produced them (production_in)
              → RM batches consumed by those MOs (production_consume)
              → POs that delivered those RM batches (purchase_in)

    Events before the SO creation date are excluded (pre-existing stock).

    Returns a graph with ``nodes`` and ``edges`` suitable for flow rendering.
    """
    with db_conn() as conn:
        so = conn.execute(
            "SELECT id, created_at FROM sales_orders WHERE id = ?",
            (sales_order_id,),
        ).fetchone()
        if not so:
            return None

        cutoff = so["created_at"]

        # --- Layer 1: shipments → FG batches consumed ----------------------
        fg_rows = conn.execute(
            "SELECT sm.reference_id AS shipment_id, sm.stock_id AS fg_stock_id, "
            "       sm.item_id, i.sku AS fg_sku, i.name AS fg_name, "
            "       -sm.qty AS qty, sm.timestamp "
            "FROM stock_movements sm "
            "JOIN items i ON sm.item_id = i.id "
            "WHERE sm.movement_type = 'shipment_out' "
            "  AND sm.reference_id IN ("
            "    SELECT s.id FROM shipments s "
            "    JOIN sales_order_shipments sos ON sos.shipment_id = s.id "
            "    WHERE sos.sales_order_id = ?"
            "  )",
            (sales_order_id,),
        ).fetchall()

        if not fg_rows:
            return {"sales_order_id": sales_order_id, "nodes": [], "edges": []}

        # Collect unique entities
        nodes = {}   # id -> node dict
        edges = []   # list of {source, target, label}

        # Shipments
        ship_ids = set()
        fg_stock_ids = set()
        for r in fg_rows:
            sid = r["shipment_id"]
            if sid not in nodes:
                ship_row = conn.execute(
                    "SELECT id, status, dispatched_at FROM shipments WHERE id = ?",
                    (sid,),
                ).fetchone()
                nodes[sid] = {
                    "id": sid, "type": "shipment",
                    "label": sid,
                    "timestamp": ship_row["dispatched_at"] if ship_row else r["timestamp"],
                    "status": ship_row["status"] if ship_row else None,
                }
                ship_ids.add(sid)

            # FG batch node (aggregate qty per stock_id per shipment)
            fk = (r["fg_stock_id"], sid)
            batch_node_id = r["fg_stock_id"]
            if batch_node_id not in nodes:
                nodes[batch_node_id] = {
                    "id": batch_node_id, "type": "fg_batch",
                    "label": f'{r["fg_sku"]}',
                    "sku": r["fg_sku"],
                    "item_name": r["fg_name"],
                    "timestamp": None,  # filled from production_in
                }
            fg_stock_ids.add(batch_node_id)
            edges.append({
                "source": batch_node_id,
                "target": sid,
                "label": f'{r["qty"]} {r["fg_sku"]}',
                "qty": r["qty"],
            })

        # --- Layer 2: FG batches → MOs that produced them ------------------
        mo_ids = set()
        for stk_id in fg_stock_ids:
            prod_row = conn.execute(
                "SELECT reference_id AS mo_id, timestamp "
                "FROM stock_movements "
                "WHERE stock_id = ? AND movement_type = 'production_in'",
                (stk_id,),
            ).fetchone()
            if not prod_row:
                continue
            mo_id = prod_row["mo_id"]
            # Update FG batch timestamp
            nodes[stk_id]["timestamp"] = prod_row["timestamp"]

            if mo_id not in nodes:
                mo_row = conn.execute(
                    "SELECT id, status, started_at, completed_at, sales_order_id "
                    "FROM production_orders WHERE id = ?",
                    (mo_id,),
                ).fetchone()
                nodes[mo_id] = {
                    "id": mo_id, "type": "mo",
                    "label": mo_id,
                    "timestamp": mo_row["completed_at"] if mo_row else prod_row["timestamp"],
                    "status": mo_row["status"] if mo_row else None,
                    "sales_order_id": mo_row["sales_order_id"] if mo_row else None,
                }
            mo_ids.add(mo_id)
            edges.append({"source": mo_id, "target": stk_id})

        # --- Layer 3 & 4: MOs → RM consumed → POs -------------------------
        for mo_id in mo_ids:
            rm_rows = conn.execute(
                "SELECT sm.stock_id AS rm_stock_id, sm.item_id, "
                "       i.sku AS rm_sku, i.name AS rm_name, "
                "       -sm.qty AS qty, sm.timestamp "
                "FROM stock_movements sm "
                "JOIN items i ON sm.item_id = i.id "
                "WHERE sm.reference_id = ? AND sm.movement_type = 'production_consume'",
                (mo_id,),
            ).fetchall()

            for rm in rm_rows:
                rm_stk = rm["rm_stock_id"]
                # Find the PO that delivered this RM batch
                po_row = conn.execute(
                    "SELECT reference_id AS po_id, timestamp "
                    "FROM stock_movements "
                    "WHERE stock_id = ? AND movement_type = 'purchase_in'",
                    (rm_stk,),
                ).fetchone()

                # Skip if the RM was acquired before the SO was created
                source_ts = po_row["timestamp"] if po_row else None
                if source_ts and source_ts < cutoff:
                    continue

                # PO node
                if po_row:
                    po_id = po_row["po_id"]
                    if po_id not in nodes:
                        po_db = conn.execute(
                            "SELECT id, status, expected_delivery, ordered_at "
                            "FROM purchase_orders WHERE id = ?",
                            (po_id,),
                        ).fetchone()
                        nodes[po_id] = {
                            "id": po_id, "type": "po",
                            "label": po_id,
                            "timestamp": po_row["timestamp"],
                            "status": po_db["status"] if po_db else None,
                            "ordered_at": po_db["ordered_at"] if po_db else None,
                        }
                    edges.append({
                        "source": po_id, "target": mo_id,
                        "label": f'{rm["qty"]} {rm["rm_sku"]}',
                        "qty": rm["qty"],
                        "sku": rm["rm_sku"],
                    })

        # Deduplicate edges (same source+target+label can appear from shared batches)
        seen_edges = set()
        unique_edges = []
        for e in edges:
            key = (e["source"], e["target"], e.get("label", ""))
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)

        return {
            "sales_order_id": sales_order_id,
            "so_created_at": cutoff,
            "nodes": list(nodes.values()),
            "edges": unique_edges,
        }


sales_service = SimpleNamespace(
    create_order=create_order,
    search_orders=search_orders,
    get_order_details=get_order_details,
    get_order_timeline=get_order_timeline,
    get_fulfillment_sources=get_fulfillment_sources,
    get_supply_chain_trace=get_supply_chain_trace,
    link_shipment=link_shipment,
    confirm_order=confirm_order,
    complete_order=complete_order,
)
SalesService = sales_service
