"""MCP tool contract tests — sales tools (CRM, orders, pricing, quotes, invoices, messaging, logistics)."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ListOf, ANY

pytestmark = pytest.mark.mcp


def _call(mcp_app, tool_name, **kwargs):
    """Call an MCP tool function directly by name and return the result."""
    tool = mcp_app._tool_manager._tools[tool_name]
    return tool.fn(**kwargs)


# ── CRM ────────────────────────────────────────────────────────────────────

def test_crm_search_customers(mcp_app):
    result = _call(mcp_app, "crm_search_customers", limit=10)
    assert isinstance(result, dict)
    assert "customers" in result
    assert len(result["customers"]) >= 1


def test_crm_search_customers_by_name(mcp_app):
    result = _call(mcp_app, "crm_search_customers", name="Alice")
    assert isinstance(result, dict)
    assert len(result["customers"]) >= 1


def test_crm_get_customer(mcp_app):
    result = _call(mcp_app, "crm_get_customer", customer_id="CUST-0101")
    assert isinstance(result, dict)
    assert "customer" in result
    assert_shape(result["customer"], {"id": str, "name": str})


# ── Sales orders ───────────────────────────────────────────────────────────

def test_sales_search_orders(mcp_app):
    result = _call(mcp_app, "sales_search_orders", limit=10)
    assert isinstance(result, dict)
    assert "sales_orders" in result
    assert len(result["sales_orders"]) >= 1


def test_sales_search_orders_by_customer(mcp_app):
    result = _call(mcp_app, "sales_search_orders", customer_ids=["CUST-0101"])
    assert isinstance(result, dict)
    assert len(result["sales_orders"]) >= 1


def test_sales_get_order(mcp_app):
    result = _call(mcp_app, "sales_get_order", sales_order_id="SO-T001")
    assert isinstance(result, dict)
    assert "sales_order" in result
    so = result["sales_order"]
    assert_shape(so, {
        "id": str,
        "customer_id": str,
        "status": str,
        "total": AnyOf(int, float),
    })


def test_sales_get_order_not_found(mcp_app):
    with pytest.raises(ValueError):
        _call(mcp_app, "sales_get_order", sales_order_id="SO-NOPE")


def test_sales_get_quote_options(mcp_app):
    result = _call(mcp_app, "sales_get_quote_options", sku="CLASSIC-DUCK-10CM", qty=12)
    assert isinstance(result, dict)


def test_sales_price_order(mcp_app):
    result = _call(mcp_app, "sales_price_order", sales_order_id="SO-T001")
    assert isinstance(result, dict)


# ── Quotes ─────────────────────────────────────────────────────────────────

def test_quote_list(mcp_app):
    result = _call(mcp_app, "quote_list", limit=10)
    assert isinstance(result, dict)
    quotes = result["quotes"]
    assert isinstance(quotes, list)
    assert len(quotes) >= 1


def test_quote_get(mcp_app):
    result = _call(mcp_app, "quote_get", quote_id="QUO-T001")
    assert isinstance(result, dict)
    assert "quote" in result
    assert_shape(result["quote"], {"id": str, "status": str})


# ── Invoices ───────────────────────────────────────────────────────────────

def test_invoice_list(mcp_app):
    result = _call(mcp_app, "invoice_list", limit=10)
    assert isinstance(result, dict)
    invoices = result["invoices"]
    assert isinstance(invoices, list)
    assert len(invoices) >= 1


def test_invoice_get(mcp_app):
    result = _call(mcp_app, "invoice_get", invoice_id="INV-T001")
    assert isinstance(result, dict)
    assert "invoice" in result
    assert_shape(result["invoice"], {"id": str, "status": str})


# ── Messaging ──────────────────────────────────────────────────────────────

def test_messaging_list_emails(mcp_app):
    result = _call(mcp_app, "messaging_list_emails", limit=10)
    assert isinstance(result, dict)
    emails = result["emails"]
    assert isinstance(emails, list)
    assert len(emails) >= 1


def test_messaging_get_email(mcp_app):
    result = _call(mcp_app, "messaging_get_email", email_id="EMAIL-T001")
    assert isinstance(result, dict)
    assert "email" in result
    assert_shape(result["email"], {"id": str, "subject": str, "status": str})


# ── Logistics ──────────────────────────────────────────────────────────────

def test_logistics_get_shipment(mcp_app):
    result = _call(mcp_app, "logistics_get_shipment", shipment_id="SHIP-T001")
    assert isinstance(result, dict)
    assert_shape(result, {"id": str, "status": str})
