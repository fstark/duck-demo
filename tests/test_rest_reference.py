"""REST contract tests — recipes, suppliers, purchase orders."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ANY

pytestmark = pytest.mark.rest


# ── Recipes ────────────────────────────────────────────────────────────────

def test_list_recipes(rest_client):
    resp = rest_client.get("/api/recipes", params={"limit": 10})
    assert resp.status_code == 200
    recipes = resp.json()["recipes"]
    assert isinstance(recipes, list)
    assert len(recipes) >= 1


def test_get_recipe_detail(rest_client):
    resp = rest_client.get("/api/recipes/RCP-CLASSIC-10")
    assert resp.status_code == 200
    data = resp.json()
    assert_shape(data, {"id": str, "output_item_id": str})


def test_list_recipes_by_sku(rest_client):
    resp = rest_client.get("/api/recipes", params={"output_item_sku": "CLASSIC-DUCK-10CM"})
    assert resp.status_code == 200
    recipes = resp.json()["recipes"]
    assert isinstance(recipes, list)
    assert len(recipes) >= 1


# ── Suppliers ──────────────────────────────────────────────────────────────

def test_list_suppliers(rest_client):
    resp = rest_client.get("/api/suppliers", params={"limit": 10})
    assert resp.status_code == 200
    suppliers = resp.json()["suppliers"]
    assert isinstance(suppliers, list)
    assert len(suppliers) >= 1
    assert_shape(suppliers[0], {"id": str, "name": str})


def test_get_supplier_detail(rest_client):
    resp = rest_client.get("/api/suppliers/SUP-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "SUP-001"


# ── Purchase orders ────────────────────────────────────────────────────────

def test_list_purchase_orders(rest_client):
    resp = rest_client.get("/api/purchase-orders", params={"limit": 10})
    assert resp.status_code == 200
    pos = resp.json()["purchase_orders"]
    assert isinstance(pos, list)
    assert len(pos) >= 1


def test_get_purchase_order_detail(rest_client):
    resp = rest_client.get("/api/purchase-orders/PO-T001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "PO-T001"
