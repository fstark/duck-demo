"""REST contract tests — production orders & work centers."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ANY

pytestmark = pytest.mark.rest


def test_list_production_orders(rest_client):
    resp = rest_client.get("/api/production-orders", params={"limit": 10})
    assert resp.status_code == 200
    orders = resp.json()["production_orders"]
    assert isinstance(orders, list)
    assert len(orders) >= 1


def test_list_production_orders_by_so(rest_client):
    resp = rest_client.get("/api/production-orders", params={"sales_order_id": "SO-T001"})
    assert resp.status_code == 200
    orders = resp.json()["production_orders"]
    assert isinstance(orders, list)
    assert len(orders) >= 1


def test_get_production_order_detail(rest_client):
    resp = rest_client.get("/api/production-orders/MO-T001")
    assert resp.status_code == 200
    data = resp.json()
    assert_shape(data, {
        "id": str,
        "status": str,
    })


def test_production_order_timeline(rest_client):
    resp = rest_client.get("/api/production-orders/MO-T001/timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_list_work_centers(rest_client):
    resp = rest_client.get("/api/work-centers")
    assert resp.status_code == 200
    wcs = resp.json()["work_centers"]
    assert isinstance(wcs, list)
    assert len(wcs) >= 1


def test_get_work_center(rest_client):
    resp = rest_client.get("/api/work-centers/WC-MOLDING")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "name" in data or "id" in data
