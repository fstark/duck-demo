"""Tests – QC domain state constants."""

from services.qc import (
    DISPOSITION_ACTIONS,
    HOLD_BATCH_STATUS_VALUES,
    INFERENCE_DECISIONS,
)


def test_batch_status_values_defined():
    assert "pending" in HOLD_BATCH_STATUS_VALUES
    assert "inspected" in HOLD_BATCH_STATUS_VALUES
    assert "closed" in HOLD_BATCH_STATUS_VALUES


def test_disposition_actions_defined():
    assert "pass_release" in DISPOSITION_ACTIONS
    assert "partial_scrap" in DISPOSITION_ACTIONS
    assert "full_scrap" in DISPOSITION_ACTIONS


def test_inference_decisions_defined():
    assert "pass" in INFERENCE_DECISIONS
    assert "partial_scrap" in INFERENCE_DECISIONS
    assert "full_scrap" in INFERENCE_DECISIONS
