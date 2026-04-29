"""End-to-end QC lifecycle tests.

Covers the full flow: MO completion → hold batch → inspection → disposition.
Uses function-scoped qc_db to isolate each test.
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image
import io

from services import production_service, qc_service
from services.inventory import get_stock_summary
import config
import db


def _make_mock_response(payload: dict):
    mock_msg = MagicMock()
    mock_msg.content = json.dumps(payload)
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


def _make_tiny_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color="yellow").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _use_qc_db(qc_db, monkeypatch):
    monkeypatch.setattr(config, "QC_INFERENCE_PROVIDER", "myforterro")
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO qc_hold_images (id, qc_hold_batch_id, image_data, created_at) "
        "VALUES ('QCIMG-E001', 'QCB-T001', ?, '2025-08-01T08:00:00')",
        (_make_tiny_png(),),
    )
    conn.commit()
    conn.close()


def test_e2e_pass_release(qc_db):
    """Inspection passes → stock is released, batch closed."""
    mock_resp = _make_mock_response({
        "decision": "pass",
        "decision_reason": "Perfect",
        "ducks": [
            {"bbox": [0.05, 0.05, 0.45, 0.95], "severity": "none", "defects": []},
            {"bbox": [0.55, 0.05, 0.95, 0.95], "severity": "none", "defects": []},
        ],
    })

    with patch("services.myforterro.chat_completion", return_value=mock_resp):
        insp = qc_service._run_inspection(batch_id="QCB-T001")

    result = qc_service.apply_disposition(
        qc_inspection_id=insp["id"],
        action="pass_release",
    )
    assert result["status"] == "completed"

    batch = qc_service.get_batch(batch_id="QCB-T001")
    assert batch["status"] == "closed"
    assert batch["qty_released"] == 12

    summary = get_stock_summary("ITEM-QC-DUCK")
    assert summary["on_hand_total"] > 0


def test_e2e_full_scrap_flow(qc_db):
    """Full scrap → all qty scrapped, batch closed."""
    mock_resp = _make_mock_response({
        "decision": "full_scrap",
        "decision_reason": "All items damaged",
        "ducks": [
            {"bbox": [0.05, 0.05, 0.95, 0.95], "severity": "major", "defects": ["Melted"]},
        ],
    })

    with patch("services.myforterro.chat_completion", return_value=mock_resp):
        insp = qc_service._run_inspection(batch_id="QCB-T001")

    qc_service.apply_disposition(
        qc_inspection_id=insp["id"],
        action="full_scrap",
    )

    batch = qc_service.get_batch(batch_id="QCB-T001")
    assert batch["status"] == "closed"
    assert batch["qty_scrapped"] == 12
    assert batch["qty_released"] == 0


def test_e2e_non_qc_mo_routes_to_stock(qc_db):
    """An MO without inspection_required=1 completes normally to stock."""
    from services.production import complete_order
    result = complete_order(
        production_order_id="MO-T001",
        qty_produced=24,
        warehouse="WH-LYON",
        location="FG",
    )
    assert result.get("qc_hold") is not True
    assert "stock_id" in result
