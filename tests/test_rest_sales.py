"""REST contract tests — sales orders."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ListOf, ANY

pytestmark = pytest.mark.rest


def test_list_sales_orders(rest_client):
    resp = rest_client.get("/api/sales-orders", params={"limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "sales_orders" in data
    orders = data["sales_orders"]
    assert isinstance(orders, list)
    assert len(orders) >= 1


def test_list_sales_orders_by_customer(rest_client):
    resp = rest_client.get("/api/sales-orders", params={"customer_id": "CUST-0101"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["sales_orders"], list)
    assert len(data["sales_orders"]) >= 1


def test_get_sales_order_detail(rest_client):
    resp = rest_client.get("/api/sales-orders/SO-T001")
    assert resp.status_code == 200
    data = resp.json()
    # Detail is a nested envelope
    assert "sales_order" in data
    so = data["sales_order"]
    assert_shape(so, {
        "id": str,
        "customer_id": str,
        "status": str,
        "total": AnyOf(int, float),
        "currency": str,
    })


def test_get_sales_order_not_found(rest_client):
    resp = rest_client.get("/api/sales-orders/SO-NOPE")
    assert resp.status_code == 404


def test_sales_order_timeline(rest_client):
    resp = rest_client.get("/api/sales-orders/SO-T001/timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))


def test_sales_order_fulfillment(rest_client):
    resp = rest_client.get("/api/sales-orders/SO-T001/fulfillment")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))


def test_sales_order_supply_chain(rest_client):
    resp = rest_client.get("/api/sales-orders/SO-T001/supply-chain")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_quote_options(rest_client):
    resp = rest_client.get("/api/quote-options", params={"sku": "CLASSIC-DUCK-10CM", "qty": "12"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
