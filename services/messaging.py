"""Service for email/messaging operations."""

from typing import Any, Dict, List, Optional

from db import dict_rows, generate_id
from utils import ui_href
from services._base import db_conn


class MessagingService:
    """Service for email/messaging operations."""

    @staticmethod
    def create_email(customer_id: str, subject: str, body: str, sales_order_id: Optional[str] = None, recipient_email: Optional[str] = None, recipient_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new email draft."""
        from services.simulation import SimulationService

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
    def list_emails(customer_id: Optional[str] = None, sales_order_id: Optional[str] = None, status: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
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
        from services.simulation import SimulationService

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
        from services.simulation import SimulationService

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


messaging_service = MessagingService()
