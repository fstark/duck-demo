"""REST contract tests — shipments."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ANY

pytestmark = pytest.mark.rest


def test_list_shipments(rest_client):
    resp = rest_client.get("/api/shipments")
    assert resp.status_code == 200
    shipments = resp.json()["shipments"]
    assert isinstance(shipments, list)
    assert len(shipments) >= 1


def test_get_shipment_detail(rest_client):
    resp = rest_client.get("/api/shipments/SHIP-T001")
    assert resp.status_code == 200
    data = resp.json()
    assert_shape(data, {
        "id": str,
        "status": str,
    })


def test_shipment_supply_chain(rest_client):
    resp = rest_client.get("/api/shipments/SHIP-T001/supply-chain")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
