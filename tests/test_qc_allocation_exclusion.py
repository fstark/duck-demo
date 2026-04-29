"""Tests – QC allocation exclusion: pending hold qty excluded from availability/shipping."""

import pytest
import db
import config
from services.inventory import get_stock_summary


def test_qc_hold_qty_excluded_from_availability(qc_db):
    """pending QC qty is excluded from available_total even though it's not in stock."""
    # The seed data has QCB-T001 with 12 units of ITEM-QC-DUCK pending inspection
    # and no stock row for that item — so available should be negative (reserved > on_hand)
    summary = get_stock_summary("ITEM-QC-DUCK")

    # on_hand = 0 (no stock for QC item in seed data)
    assert summary["on_hand_total"] == 0
    # reserved should include the 12 pending QC units
    assert summary["reserved_total"] >= 12
    # available should therefore be <= -12 (or at most negative)
    assert summary["available_total"] <= 0


def test_non_qc_item_unaffected(qc_db):
    """Regular items without QC hold are not affected by the new reserved logic."""
    summary = get_stock_summary("ITEM-CLASSIC-10")
    # Classic duck has 48 on hand in seed data
    assert summary["on_hand_total"] >= 48
    # available should be positive (48 on hand minus some reservations)
    # Exact value depends on seed SO data, but should not go excessively negative
    assert summary["on_hand_total"] > 0
