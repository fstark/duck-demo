"""REST contract tests – QC endpoints."""

import pytest

pytestmark = pytest.mark.rest


def test_qc_batches_returns_list(rest_client):
    resp = rest_client.get("/api/qc/batches", params={"status": "pending_images"})
    assert resp.status_code == 200
    data = resp.json()
    assert "batches" in data
    assert isinstance(data["batches"], list)


def test_qc_batches_has_seeded_batch(rest_client):
    resp = rest_client.get("/api/qc/batches", params={"status": "pending_images"})
    assert resp.status_code == 200
    batches = resp.json()["batches"]
    ids = [b["id"] for b in batches]
    assert "QCB-T001" in ids


def test_qc_batch_detail(rest_client):
    resp = rest_client.get("/api/qc/batches/QCB-T001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "QCB-T001"
    assert "lines" in data
    assert "images" in data
    assert isinstance(data["lines"], list)
    assert len(data["lines"]) >= 1


def test_qc_batch_detail_not_found_returns_404(rest_client):
    resp = rest_client.get("/api/qc/batches/QCB-DOES-NOT-EXIST")
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_qc_inspection_not_found_returns_404(rest_client):
    resp = rest_client.get("/api/qc/inspections/QCI-DOES-NOT-EXIST")
    assert resp.status_code == 404
    assert "error" in resp.json()
