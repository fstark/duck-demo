"""Service-layer tests – QcService._run_inspection()."""

import io
import json
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from services.qc import qc_service
import db
import config


def _make_tiny_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color="yellow").save(buf, format="PNG")
    return buf.getvalue()


def _make_mock_response(payload: dict):
    """Build a mock ChatCompletion object that looks like the OpenAI SDK response."""
    mock_msg = MagicMock()
    mock_msg.content = json.dumps(payload)
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


_PASS_PAYLOAD = {
    "decision": "pass",
    "decision_reason": "No visible defects",
    "ducks": [
        {"bbox": [0.1, 0.1, 0.4, 0.6], "severity": "none", "defects": []},
        {"bbox": [0.5, 0.1, 0.9, 0.6], "severity": "none", "defects": []},
    ],
}

_FAIL_PAYLOAD = {
    "decision": "full_scrap",
    "decision_reason": "Paintwork damage on beak",
    "ducks": [
        {"bbox": [0.1, 0.1, 0.4, 0.6], "severity": "major", "defects": ["Chipped paint on beak"]},
    ],
}


@pytest.fixture(autouse=True)
def _use_qc_db(qc_db, monkeypatch):
    """Use the function-scoped QC database for every test in this module."""
    monkeypatch.setattr(config, "QC_INFERENCE_PROVIDER", "myforterro")
    # Insert a dummy image BLOB so _run_inspection() doesn't reject the batch
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO qc_hold_images (id, qc_hold_batch_id, image_data, created_at) "
        "VALUES ('QCIMG-T001', 'QCB-T001', ?, '2025-08-01T08:00:00')",
        (_make_tiny_png(),),
    )
    conn.commit()
    conn.close()


def test_run_inspection_pass_persists_inspection(qc_db):
    mock_resp = _make_mock_response(_PASS_PAYLOAD)
    with patch("services.myforterro.chat_completion", return_value=mock_resp):
        result = qc_service._run_inspection(batch_id="QCB-T001")

    assert result["decision"] == "pass"
    assert result["status"] == "completed"

    conn = db.get_connection()
    row = conn.execute(
        "SELECT decision, status FROM qc_inspections WHERE qc_hold_batch_id = 'QCB-T001'"
    ).fetchone()
    conn.close()
    assert row["decision"] == "pass"
    assert row["status"] == "completed"


def test_run_inspection_fail_persists_findings(qc_db):
    mock_resp = _make_mock_response(_FAIL_PAYLOAD)
    with patch("services.myforterro.chat_completion", return_value=mock_resp):
        result = qc_service._run_inspection(batch_id="QCB-T001")

    assert result["decision"] == "full_scrap"
    assert len(result.get("findings", [])) == 1


def test_run_inspection_idempotency(qc_db):
    """A batch with a completed inspection returns the same result on second call."""
    mock_resp = _make_mock_response(_PASS_PAYLOAD)
    with patch("services.myforterro.chat_completion", return_value=mock_resp):
        result1 = qc_service._run_inspection(batch_id="QCB-T001")

    with patch("services.myforterro.chat_completion", return_value=mock_resp):
        result2 = qc_service._run_inspection(batch_id="QCB-T001")

    assert result1["id"] == result2["id"]
    assert result2["status"] == "completed"


def test_run_inspection_invalid_batch_raises(qc_db):
    with pytest.raises((ValueError, Exception)):
        qc_service._run_inspection(batch_id="QCB-DOES-NOT-EXIST")
