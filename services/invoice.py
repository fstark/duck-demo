"""Service for invoice and payment operations."""

import logging
from datetime import datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import config
from db import dict_rows, generate_id
from utils import ui_href, format_qty
from services._base import db_conn

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

logger = logging.getLogger(__name__)


def create_invoice(sales_order_id: str) -> Dict[str, Any]:
    """Create a draft invoice from a sales order, using stored pricing."""
    from services.simulation import simulation_service

    with db_conn() as conn:
        so = conn.execute("SELECT * FROM sales_orders WHERE id = ?", (sales_order_id,)).fetchone()
        if not so:
            raise ValueError(f"Sales order {sales_order_id} not found")

        customer = conn.execute("SELECT name, tax_id FROM customers WHERE id = ?", (so["customer_id"],)).fetchone()

        # Use frozen pricing from the sales order
        p = {
            "subtotal": so["subtotal"],
            "discount": so["discount"],
            "shipping": so["shipping"],
            "tax": so["tax"],
            "total": so["total"],
            "currency": so["currency"],
        }

        sim_time = simulation_service.get_current_time()
        inv_id = generate_id(conn, "INV", "invoices")

        conn.execute(
            "INSERT INTO invoices (id, sales_order_id, customer_id, invoice_date, due_date, subtotal, discount, shipping, tax, total, currency, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
            (
                inv_id,
                sales_order_id,
                so["customer_id"],
                sim_time[:10],
                None,
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


def issue_invoice(invoice_id: str) -> Dict[str, Any]:
    """Issue a draft invoice: sets due_date, status='issued', and generates PDF."""
    from services.simulation import simulation_service
    from services.document import document_service

    with db_conn() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv["status"] != "draft":
            raise ValueError(f"Invoice {invoice_id} is '{inv['status']}', must be 'draft' to issue")

        sim_time = simulation_service.get_current_time()
        invoice_date = datetime.fromisoformat(inv["invoice_date"])

        # Use customer-specific payment terms if available, else global default
        customer = conn.execute("SELECT payment_terms FROM customers WHERE id = ?", (inv["customer_id"],)).fetchone()
        payment_days = (customer["payment_terms"] if customer and customer["payment_terms"] else config.INVOICE_PAYMENT_TERMS_DAYS)
        due_date = (invoice_date + timedelta(days=payment_days)).strftime("%Y-%m-%d")

        conn.execute(
            "UPDATE invoices SET status = 'issued', due_date = ?, issued_at = ? WHERE id = ?",
            (due_date, sim_time, invoice_id),
        )
        conn.commit()

        try:
            pdf_bytes = generate_invoice_pdf(invoice_id)
            document_service.store_document(
                entity_type="invoice",
                entity_id=invoice_id,
                document_type="invoice_pdf",
                content=pdf_bytes,
                filename=f"invoice_{invoice_id}.pdf",
                notes="Generated when invoice was issued"
            )
        except Exception as e:
            logger.error(f"Failed to generate PDF for {invoice_id}: {e}")
            pdf_warning = f"PDF generation failed: {e}"
        else:
            pdf_warning = None

        result = {
            "invoice_id": invoice_id,
            "status": "issued",
            "due_date": due_date,
            "ui_url": ui_href("invoices", invoice_id),
            "message": f"\U0001f4e8 Invoice {invoice_id} issued — due {due_date}",
        }
        if pdf_warning:
            result["warning"] = pdf_warning
    return result


def get_invoice(invoice_id: str) -> Optional[Dict[str, Any]]:
    """Get full invoice details with customer, sales order lines, and payments."""
    with db_conn() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not inv:
            return None
        inv_dict = dict(inv)
        inv_dict["ui_url"] = ui_href("invoices", invoice_id)

        customer = conn.execute("SELECT * FROM customers WHERE id = ?", (inv["customer_id"],)).fetchone()
        customer_dict = dict(customer) if customer else None
        if customer_dict:
            customer_dict["ui_url"] = ui_href("customers", customer_dict["id"])

        lines = dict_rows(conn.execute(
            "SELECT i.sku, i.uom, sol.qty, sol.unit_price, sol.line_total FROM sales_order_lines sol "
            "JOIN items i ON sol.item_id = i.id "
            "WHERE sol.sales_order_id = ?",
            (inv["sales_order_id"],),
        ).fetchall())

        so = conn.execute("SELECT id, status, created_at FROM sales_orders WHERE id = ?", (inv["sales_order_id"],)).fetchone()
        so_dict = dict(so) if so else None
        if so_dict:
            so_dict["ui_url"] = ui_href("orders", so_dict["id"])

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


def list_invoices(
    customer_id: Optional[str] = None,
    sales_order_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """List invoices with optional filters."""
    filters: List[str] = []
    params: List[Any] = []
    if customer_id:
        filters.append("inv.customer_id = ?")
        params.append(customer_id)
    if sales_order_id:
        filters.append("inv.sales_order_id = ?")
        params.append(sales_order_id)
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


def record_payment(
    invoice_id: str,
    amount: float,
    payment_method: str = "bank_transfer",
    reference: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a payment against an invoice. Auto-marks as 'paid' when fully covered."""
    from services.simulation import simulation_service

    with db_conn() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv["status"] not in ("issued", "overdue"):
            raise ValueError(f"Invoice {invoice_id} is '{inv['status']}', must be 'issued' or 'overdue' to accept payment")

        sim_time = simulation_service.get_current_time()
        pay_id = generate_id(conn, "PAY", "payments")
        conn.execute(
            "INSERT INTO payments (id, invoice_id, amount, payment_method, payment_date, reference, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pay_id, invoice_id, amount, payment_method, sim_time[:10], reference, notes, sim_time),
        )

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

        result = {
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


def generate_invoice_pdf(invoice_id: str) -> bytes:
    """Generate a PDF for an invoice using ReportLab."""
    invoice_data = get_invoice(invoice_id)
    if not invoice_data:
        raise ValueError(f"Invoice {invoice_id} not found")

    inv = invoice_data.get("invoice")
    customer = invoice_data.get("customer")
    lines = invoice_data.get("lines", [])
    payments = invoice_data.get("payments", [])

    if not inv:
        raise ValueError(f"Invoice data missing 'invoice' key")

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

    right_align_style = ParagraphStyle(
        'RightAlign',
        parent=styles['Normal'],
        alignment=TA_RIGHT,
    )

    story.append(Paragraph(f"<b>INVOICE {inv['id']}</b>", title_style))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("<b>Duck Inc</b>", styles['Normal']))
    story.append(Paragraph("World Leading Manufacturer of Rubber Ducks", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

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

    line_items_data = [['Item (SKU)', 'Quantity', 'Unit Price', 'Total']]

    with db_conn() as conn:
        for line in lines:
            unit_price = line.get('unit_price', 0)
            line_total = line.get('line_total', unit_price * line['qty'])
            item = conn.execute("SELECT name FROM items WHERE sku = ?", (line['sku'],)).fetchone()
            item_name = item['name'] if item else line['sku']
            line_items_data.append([
                f"{item_name} ({line['sku']})",
                f"{format_qty(line['qty'], line.get('uom', 'ea'))}",
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

    story.append(Spacer(1, 0.5*inch))
    footer_text = "<i>Thank you for your business!</i>"
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


# Namespace for backward compatibility
invoice_service = SimpleNamespace(
    create_invoice=create_invoice,
    issue_invoice=issue_invoice,
    get_invoice=get_invoice,
    list_invoices=list_invoices,
    record_payment=record_payment,
    mark_overdue=mark_overdue,
    generate_invoice_pdf=generate_invoice_pdf,
)
InvoiceService = invoice_service
