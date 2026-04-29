"""End-to-end QC lifecycle tests.

Covers the full flow: MO completion → hold batch → inspection → disposition.
Uses function-scoped qc_db to isolate each test.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from services import production_service, qc_service
from services.inventory import get_stock_summary
import db


def _make_mock_response(payload: dict):
    mock_msg = MagicMock()
    mock_msg.content = json.dumps(payload)
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


@pytest.fixture(autouse=True)
def _use_qc_db(qc_db):
    # Insert a dummy image BLOB so run_inspection() doesn't reject the batch
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO qc_hold_images (id, qc_hold_batch_id, image_data, created_at) "
        "VALUES ('QCIMG-E001', 'QCB-T001', ?, '2025-08-01T08:00:00')",
        (b'\x89PNG\r\n\x1a\n',),  # minimal PNG magic bytes
    )
    conn.commit()
    conn.close()


# ── E2E: pass_release flow ───────────────────────────────────────────────────

def test_e2e_pass_release(qc_db):
    """Inspection passes → stock is released, batch status becomes 'released'."""
    mock_resp = _make_mock_response({
        "decision": "pass",
        "confidence_overall": 0.99,
        "decision_reason": "Perfect",
        "findings": [],
    })

    with patch("services.myforterro.chat_completion", return_value=mock_resp):
        insp = qc_service.run_inspection(batch_id="QCB-T001")

    result = qc_service.apply_disposition(
        qc_inspection_id=insp["id"],
        action="pass_release",
    )
    assert result["status"] == "completed"  # returns the inspection dict

    batch = qc_service.get_batch(batch_id="QCB-T001")
    assert batch["status"] == "released"

    summary = get_stock_summary("ITEM-QC-DUCK")
    assert summary["on_hand_total"] > 0  # stock was created; reserved by SO is expected


def test_e2e_full_scrap_flow(qc_db):
    """Full scrap → all qty scrapped, batch closed, replacement MO created."""
    mock_resp = _make_mock_response({
        "decision": "full_scrap",
        "confidence_overall": 0.95,
        "decision_reason": "All items damaged",
        "findings": [
            {"severity": "critical", "location": "body", "description": "Melted", "affected_qty": 12}
        ],
    })

    with patch("services.myforterro.chat_completion", return_value=mock_resp):
        insp = qc_service.run_inspection(batch_id="QCB-T001")

    result = qc_service.apply_disposition(
        qc_inspection_id=insp["id"],
        action="full_scrap",
    )
    assert result["status"] == "completed"  # returns the inspection dict

    batch = qc_service.get_batch(batch_id="QCB-T001")
    assert batch["status"] == "closed" or batch["status"] == "scrapped"

    conn = db.get_connection()
    rpl = conn.execute(
        "SELECT r.* FROM qc_replacements r "
        "JOIN qc_dispositions d ON r.qc_disposition_id = d.id "
        "WHERE d.qc_hold_batch_id = 'QCB-T001'"
    ).fetchone()
    conn.close()
    assert rpl is not None
    assert rpl["replacement_production_order_id"] is not None


def test_e2e_non_qc_mo_routes_to_stock(qc_db):
    """An MO without inspection_required=1 completes normally to stock."""
    # MO-T001 in seed data has inspection_required=0 and is still in_progress
    # so we can complete it and verify stock is created
    from services.production import complete_order
    result = complete_order(
        production_order_id="MO-T001",
        qty_produced=24,
        warehouse="WH-LYON",
        location="FG",
    )
    assert result.get("qc_hold") is not True
    assert "stock_id" in result
