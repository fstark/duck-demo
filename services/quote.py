"""Service for quote operations."""

import re
import logging
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, List, Optional

import config
from db import dict_rows, generate_id
from utils import ship_to_columns, ship_to_dict, ui_href, format_qty
from services._base import db_conn

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

logger = logging.getLogger(__name__)


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
        from services.simulation import SimulationService

        with db_conn() as conn:
            customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if not customer:
                raise ValueError(f"Customer {customer_id} not found")

            sim_time = SimulationService.get_current_time()
            quote_id = generate_id(conn, "QUOTE", "quotes")

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

            total_qty = sum(line["qty"] for line in lines)
            discount = config.PRICING_VOLUME_DISCOUNT_PCT * subtotal if total_qty >= config.PRICING_VOLUME_QTY_THRESHOLD else 0.0
            shipping = 0.0 if subtotal >= config.PRICING_FREE_SHIPPING_THRESHOLD else config.PRICING_FLAT_SHIPPING
            tax = 0.0
            total = subtotal - discount + shipping + tax

            valid_until = (datetime.fromisoformat(sim_time) + timedelta(days=valid_days)).strftime("%Y-%m-%d")

            conn.execute(
                "INSERT INTO quotes (id, customer_id, revision_number, requested_delivery_date, "
                "ship_to_line1, ship_to_line2, ship_to_postal_code, ship_to_city, ship_to_country, note, "
                "subtotal, discount, shipping, tax, total, currency, valid_until, status, created_at) "
                "VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                (
                    quote_id, customer_id, requested_delivery_date,
                    *ship_to_columns(ship_to),
                    note,
                    subtotal, discount, shipping, tax, total, config.PRICING_CURRENCY,
                    valid_until, sim_time
                )
            )

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

            customer = conn.execute("SELECT * FROM customers WHERE id = ?", (quote["customer_id"],)).fetchone()
            customer_dict = dict(customer) if customer else None
            if customer_dict:
                customer_dict["ui_url"] = ui_href("customers", customer_dict["id"])

            lines = dict_rows(conn.execute(
                "SELECT ql.*, i.sku, i.name, i.uom FROM quote_lines ql "
                "JOIN items i ON ql.item_id = i.id "
                "WHERE ql.quote_id = ? ORDER BY ql.id",
                (quote_id,)
            ).fetchall())

            superseded_quote = None
            if quote["supersedes_quote_id"]:
                superseded_quote = {"id": quote["supersedes_quote_id"], "ui_url": ui_href("quotes", quote["supersedes_quote_id"])}

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
        from services.simulation import SimulationService
        from services.document import DocumentService

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
                pdf_warning = f"PDF generation failed: {e}"
            else:
                pdf_warning = None

            result = {
                "quote_id": quote_id,
                "status": "sent",
                "sent_at": sim_time,
                "valid_until": quote["valid_until"],
                "ui_url": ui_href("quotes", quote_id),
                "message": f"\U0001f4e8 Quote {quote_id} sent to customer (valid until {quote['valid_until']})"
            }
            if pdf_warning:
                result["warning"] = pdf_warning
            return result

    @staticmethod
    def accept_quote(quote_id: str) -> Dict[str, Any]:
        """Accept a sent quote: creates sales order and updates quote status."""
        from services.simulation import SimulationService
        from services.sales import SalesService

        with db_conn() as conn:
            quote = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            if not quote:
                raise ValueError(f"Quote {quote_id} not found")
            if quote["status"] not in ("sent", "draft"):
                raise ValueError(f"Quote {quote_id} is '{quote['status']}', must be 'sent' or 'draft' to accept")

            sim_time = SimulationService.get_current_time()
            if quote["valid_until"] and quote["valid_until"] < sim_time[:10]:
                raise ValueError(f"Quote {quote_id} expired on {quote['valid_until']}")

            lines = dict_rows(conn.execute(
                "SELECT ql.*, i.sku FROM quote_lines ql JOIN items i ON ql.item_id = i.id WHERE ql.quote_id = ?",
                (quote_id,)
            ).fetchall())

            sales_order_lines = [{"sku": line["sku"], "qty": line["qty"], "unit_price": line["unit_price"], "line_total": line["line_total"]} for line in lines]

            ship_to = None
            if quote["ship_to_line1"]:
                ship_to = ship_to_dict(quote)

            pricing = {
                "subtotal": quote["subtotal"],
                "discount": quote["discount"],
                "shipping": quote["shipping"],
                "tax": quote["tax"],
                "total": quote["total"],
                "currency": quote["currency"],
            }

            sales_result = SalesService.create_order(
                customer_id=quote["customer_id"],
                requested_delivery_date=quote["requested_delivery_date"],
                ship_to=ship_to,
                lines=sales_order_lines,
                note=f"Created from quote {quote_id}",
                quote_id=quote_id,
                pricing=pricing,
            )

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
        from services.simulation import SimulationService

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
        from services.simulation import SimulationService

        with db_conn() as conn:
            original_quote = conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            if not original_quote:
                raise ValueError(f"Quote {quote_id} not found")
            if original_quote["status"] in ("accepted", "superseded"):
                raise ValueError(f"Quote {quote_id} is '{original_quote['status']}', cannot revise")

            original_lines = dict_rows(conn.execute(
                "SELECT ql.*, i.sku FROM quote_lines ql JOIN items i ON ql.item_id = i.id WHERE ql.quote_id = ?",
                (quote_id,)
            ).fetchall())

            match = re.match(r"(QUOTE-\d+)(?:-R\d+)?", quote_id)
            base_id = match.group(1) if match else quote_id.rsplit('-R', 1)[0]

            new_revision_num = original_quote["revision_number"] + 1
            new_quote_id = f"{base_id}-R{new_revision_num}"

            sim_time = SimulationService.get_current_time()

            lines_to_use = changes.get("lines") if changes and "lines" in changes else [{"sku": line["sku"], "qty": line["qty"]} for line in original_lines]
            requested_delivery_date = changes.get("requested_delivery_date", original_quote["requested_delivery_date"]) if changes else original_quote["requested_delivery_date"]
            note = changes.get("note", original_quote["note"]) if changes else original_quote["note"]

            ship_to = None
            if changes and "ship_to" in changes:
                ship_to = changes["ship_to"]
            elif original_quote["ship_to_line1"]:
                ship_to = ship_to_dict(original_quote)

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

            total_qty = sum(line["qty"] for line in lines_to_use)
            discount = config.PRICING_VOLUME_DISCOUNT_PCT * subtotal if total_qty >= config.PRICING_VOLUME_QTY_THRESHOLD else 0.0
            shipping = 0.0 if subtotal >= config.PRICING_FREE_SHIPPING_THRESHOLD else config.PRICING_FLAT_SHIPPING
            tax = 0.0
            total = subtotal - discount + shipping + tax

            valid_days = changes.get("valid_days", 30) if changes else 30
            valid_until = (datetime.fromisoformat(sim_time) + timedelta(days=valid_days)).strftime("%Y-%m-%d")

            conn.execute(
                "INSERT INTO quotes (id, customer_id, revision_number, supersedes_quote_id, requested_delivery_date, "
                "ship_to_line1, ship_to_line2, ship_to_postal_code, ship_to_city, ship_to_country, note, "
                "subtotal, discount, shipping, tax, total, currency, valid_until, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                (
                    new_quote_id, original_quote["customer_id"], new_revision_num, quote_id, requested_delivery_date,
                    *ship_to_columns(ship_to),
                    note,
                    subtotal, discount, shipping, tax, total, config.PRICING_CURRENCY,
                    valid_until, sim_time
                )
            )

            for line in revised_lines:
                conn.execute(
                    "INSERT INTO quote_lines (id, quote_id, item_id, qty, unit_price, line_total) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (line["id"], new_quote_id, line["item_id"], line["qty"], line["unit_price"], line["line_total"])
                )

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
        quote_data = QuoteService.get_quote(quote_id)
        if not quote_data:
            raise ValueError(f"Quote {quote_id} not found")

        quote = quote_data["quote"]
        customer = quote_data["customer"]
        lines = quote_data["lines"]

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                              topMargin=0.5*inch, bottomMargin=0.5*inch)

        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=30,
        )

        title_text = f"<b>QUOTATION {quote['id']}</b>"
        if quote["revision_number"] > 1:
            title_text += f" <font size='18'>(Revision {quote['revision_number']})</font>"
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 0.2*inch))

        story.append(Paragraph("<b>Duck Inc</b>", styles['Normal']))
        story.append(Paragraph("World Leading Manufacturer of Rubber Ducks", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))

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

        line_items_data = [['Item (SKU)', 'Quantity', 'Unit Price', 'Total']]

        for line in lines:
            line_items_data.append([
                f"{line['name']} ({line['sku']})",
                f"{format_qty(line['qty'], line.get('uom', 'ea'))}",
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

        story.append(Spacer(1, 0.3*inch))
        validity_text = f"<b>This quotation is valid until {quote['valid_until']}</b>"
        story.append(Paragraph(validity_text, ParagraphStyle(
            'Validity',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#dc2626'),
            alignment=TA_CENTER,
        )))

        story.append(Spacer(1, 0.3*inch))
        footer_text = "<i>Thank you for considering Duck Inc for your rubber duck needs!</i>"
        story.append(Paragraph(footer_text, ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER,
        )))

        try:
            doc.build(story)
        except Exception as e:
            logger.error(f"Error building PDF: {e}", exc_info=True)
            raise

        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes


quote_service = QuoteService()
