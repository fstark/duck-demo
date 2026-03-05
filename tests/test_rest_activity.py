"""REST contract tests — activity log & dashboard."""

import pytest

from tests.contract_helpers import assert_shape, AnyOf, ANY

pytestmark = pytest.mark.rest


def test_activity_log(rest_client):
    resp = rest_client.get("/api/activity-log", params={"limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    entries = data["entries"]
    assert isinstance(entries, list)
    assert len(entries) >= 1
    assert_shape(entries[0], {
        "id": str,
        "timestamp": str,
        "action": str,
    })


def test_activity_log_filter_category(rest_client):
    resp = rest_client.get("/api/activity-log", params={"category": "sales"})
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert isinstance(entries, list)


def test_activity_summary(rest_client):
    resp = rest_client.get("/api/activity-log/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))


def test_dashboard(rest_client):
    resp = rest_client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
