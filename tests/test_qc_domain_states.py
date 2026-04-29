"""Tests – QC domain state/transition validation and quantity invariant."""

import pytest

from services.qc import (
    _assert_invariant,
    _validate_transition,
    DISPOSITION_ACTIONS,
    HOLD_BATCH_STATUS_VALUES,
    HOLD_LINE_STATUS_VALUES,
    INSPECTION_STATUS_VALUES,
    INFERENCE_DECISIONS,
)


# ---------------------------------------------------------------------------
# Invariant tests
# ---------------------------------------------------------------------------

def test_invariant_passes_when_correct():
    line = {"id": "L1", "qty_on_hold": 10, "qty_pending": 3, "qty_released": 5, "qty_scrapped": 2}
    _assert_invariant(line)  # should not raise


def test_invariant_fails_when_broken():
    line = {"id": "L1", "qty_on_hold": 10, "qty_pending": 5, "qty_released": 5, "qty_scrapped": 2}
    with pytest.raises(AssertionError, match="invariant violated"):
        _assert_invariant(line)


def test_invariant_all_pending():
    line = {"id": "L1", "qty_on_hold": 12, "qty_pending": 12, "qty_released": 0, "qty_scrapped": 0}
    _assert_invariant(line)


def test_invariant_all_released():
    line = {"id": "L1", "qty_on_hold": 12, "qty_pending": 0, "qty_released": 12, "qty_scrapped": 0}
    _assert_invariant(line)


def test_invariant_all_scrapped():
    line = {"id": "L1", "qty_on_hold": 12, "qty_pending": 0, "qty_released": 0, "qty_scrapped": 12}
    _assert_invariant(line)


# ---------------------------------------------------------------------------
# State constant tests
# ---------------------------------------------------------------------------

def test_inspection_status_values_defined():
    assert "none" in INSPECTION_STATUS_VALUES
    assert "pending_inspection" in INSPECTION_STATUS_VALUES
    assert "inspected" in INSPECTION_STATUS_VALUES
    assert "partially_released" in INSPECTION_STATUS_VALUES
    assert "released" in INSPECTION_STATUS_VALUES


def test_disposition_actions_defined():
    assert "pass_release" in DISPOSITION_ACTIONS
    assert "partial_scrap" in DISPOSITION_ACTIONS
    assert "full_scrap" in DISPOSITION_ACTIONS


def test_inference_decisions_defined():
    assert "pass" in INFERENCE_DECISIONS
    assert "partial_scrap" in INFERENCE_DECISIONS
    assert "full_scrap" in INFERENCE_DECISIONS


# ---------------------------------------------------------------------------
# Transition validation tests
# ---------------------------------------------------------------------------

def test_transition_complete_with_hold_valid():
    # Only valid from 'none'
    _validate_transition(current_status="none", event="complete_with_hold")


def test_transition_complete_with_hold_invalid():
    with pytest.raises(ValueError):
        _validate_transition(current_status="pending_inspection", event="complete_with_hold")


def test_transition_run_inspection_valid():
    _validate_transition(current_status="pending_inspection", event="run_inspection")


def test_transition_run_inspection_invalid():
    with pytest.raises(ValueError):
        _validate_transition(current_status="none", event="run_inspection")


def test_transition_disposition_pass_valid():
    _validate_transition(current_status="inspected", event="apply_disposition_pass")


def test_transition_disposition_pass_invalid():
    with pytest.raises(ValueError):
        _validate_transition(current_status="pending_inspection", event="apply_disposition_pass")


def test_invalid_disposition_action_raises():
    from services.qc import QcService
    svc = QcService()
    with pytest.raises(ValueError, match="Invalid disposition action"):
        # Should validate before hitting the DB
        svc.apply_disposition(
            qc_inspection_id="QCI-9999",
            action="invalid_action",
        )
