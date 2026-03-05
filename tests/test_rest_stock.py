"""REST contract tests — stock endpoints."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ANY

pytestmark = pytest.mark.rest


def test_list_stock(rest_client):
    resp = rest_client.get("/api/stock", params={"limit": 50})
    assert resp.status_code == 200
    stock = resp.json()["stock"]
    assert isinstance(stock, list)
    assert len(stock) >= 1
    assert_shape(stock[0], {
        "id": str,
        "item_id": str,
        "warehouse": str,
        "location": str,
        "on_hand": AnyOf(int, float),
    })


def test_get_stock_detail(rest_client):
    resp = rest_client.get("/api/stock/STK-T004")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "STK-T004"
    assert "on_hand" in data
