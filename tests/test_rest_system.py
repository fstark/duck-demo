"""REST contract tests — system & health endpoints."""

import pytest

pytestmark = pytest.mark.rest


def test_health(rest_client):
    resp = rest_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_simulation_time(rest_client):
    resp = rest_client.get("/api/simulation/time")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_time" in data
    assert isinstance(data["current_time"], str)


def test_spotlight(rest_client):
    resp = rest_client.get("/api/stats/spotlight")
    assert resp.status_code == 200
    data = resp.json()
    # Spotlight returns top-level counts
    assert isinstance(data, dict)
    for key in ("customers", "quotes", "sales_orders", "shipments", "invoices"):
        assert key in data, f"Missing spotlight key: {key}"
