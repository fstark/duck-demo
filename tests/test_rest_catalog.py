"""REST contract tests — catalog & item endpoints."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ListOf, ANY

pytestmark = pytest.mark.rest

ITEM_SHAPE = {
    "id": str,
    "sku": str,
    "name": str,
    "type": str,
}


def test_list_items(rest_client):
    resp = rest_client.get("/api/items", params={"limit": 50})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert isinstance(items, list)
    assert len(items) >= 1  # at least one item in catalog


def test_list_items_in_stock_only(rest_client):
    resp = rest_client.get("/api/items", params={"in_stock_only": "true", "limit": 50})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert isinstance(items, list)
    assert len(items) >= 1


def test_get_item_by_sku(rest_client):
    resp = rest_client.get("/api/items/CLASSIC-DUCK-10CM")
    assert resp.status_code == 200
    data = resp.json()
    assert_shape(data, {"sku": str, "name": str, "type": str})
    assert data["sku"] == "CLASSIC-DUCK-10CM"


def test_get_item_stock(rest_client):
    resp = rest_client.get("/api/items/CLASSIC-DUCK-10CM/stock")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_get_item_not_found(rest_client):
    resp = rest_client.get("/api/items/NONEXISTENT-SKU")
    assert resp.status_code == 404
