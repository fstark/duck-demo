"""REST contract tests — emails, quotes, invoices."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ListOf, ANY

pytestmark = pytest.mark.rest


# ── Emails ─────────────────────────────────────────────────────────────────

def test_list_emails(rest_client):
    resp = rest_client.get("/api/emails", params={"limit": 10})
    assert resp.status_code == 200
    emails = resp.json()["emails"]
    assert isinstance(emails, list)
    assert len(emails) >= 1
    assert_shape(emails[0], {"id": str, "subject": str, "status": str})


def test_list_emails_by_customer(rest_client):
    resp = rest_client.get("/api/emails", params={"customer_id": "CUST-0101"})
    assert resp.status_code == 200
    emails = resp.json()["emails"]
    assert isinstance(emails, list)
    assert len(emails) >= 1


def test_get_email_detail(rest_client):
    resp = rest_client.get("/api/emails/EMAIL-T001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"]["id"] == "EMAIL-T001"
    assert "body" in data["email"]


# ── Quotes ─────────────────────────────────────────────────────────────────

def test_list_quotes(rest_client):
    resp = rest_client.get("/api/quotes", params={"limit": 10})
    assert resp.status_code == 200
    quotes = resp.json()["quotes"]
    assert isinstance(quotes, list)
    assert len(quotes) >= 1
    assert_shape(quotes[0], {"id": str, "status": str, "total": AnyOf(int, float)})


def test_list_quotes_by_customer(rest_client):
    resp = rest_client.get("/api/quotes", params={"customer_id": "CUST-0101"})
    assert resp.status_code == 200
    quotes = resp.json()["quotes"]
    assert isinstance(quotes, list)
    assert len(quotes) >= 1


def test_get_quote_detail(rest_client):
    resp = rest_client.get("/api/quotes/QUO-T001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["quote"]["id"] == "QUO-T001"
    assert "lines" in data


# ── Invoices ───────────────────────────────────────────────────────────────

def test_list_invoices(rest_client):
    resp = rest_client.get("/api/invoices", params={"limit": 10})
    assert resp.status_code == 200
    invoices = resp.json()["invoices"]
    assert isinstance(invoices, list)
    assert len(invoices) >= 1
    assert_shape(invoices[0], {"id": str, "status": str, "total": AnyOf(int, float)})


def test_list_invoices_by_customer(rest_client):
    resp = rest_client.get("/api/invoices", params={"customer_id": "CUST-0101"})
    assert resp.status_code == 200
    invoices = resp.json()["invoices"]
    assert isinstance(invoices, list)
    assert len(invoices) >= 1


def test_get_invoice_detail(rest_client):
    resp = rest_client.get("/api/invoices/INV-T001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["invoice"]["id"] == "INV-T001"
    assert "lines" in data or "balance_due" in data
