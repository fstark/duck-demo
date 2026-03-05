"""REST contract tests — customers."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ListOf, Optional, ANY

pytestmark = pytest.mark.rest

CUSTOMER_SHAPE = {
    "id": str,
    "name": str,
    "email": AnyOf(str, type(None)),
    "city": AnyOf(str, type(None)),
    "country": AnyOf(str, type(None)),
}


def test_list_customers(rest_client):
    resp = rest_client.get("/api/customers", params={"limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    customers = data["customers"]
    assert isinstance(customers, list)
    assert len(customers) >= 1
    assert_shape(customers[0], CUSTOMER_SHAPE)


def test_list_customers_filter_name(rest_client):
    resp = rest_client.get("/api/customers", params={"name": "Alice"})
    assert resp.status_code == 200
    customers = resp.json()["customers"]
    assert len(customers) >= 1
    assert "Alice" in customers[0]["name"]


def test_get_customer_detail(rest_client):
    resp = rest_client.get("/api/customers/CUST-0101")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "CUST-0101"
    assert "name" in data
    # Detail view includes orders
    assert "orders" in data or "sales_orders" in data
