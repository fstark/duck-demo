"""Tests – QC production completion routes to hold vs. stock."""

import pytest
import db
from services.qc import qc_service


def test_qc_completion_creates_hold_not_stock(qc_db):
    """inspection_required=1 MO completion creates QC hold, not stock."""
    from services.production import complete_order

    result = complete_order(
        production_order_id="MO-QC002",
        qty_produced=12,
        warehouse="WH-LYON",
        location="FG",
    )

    assert result["qc_hold"] is True
    batch_id = result["qc_hold_batch_id"]
    assert batch_id.startswith("QCB-")

    conn = db.get_connection()
    # Verify batch exists
    batch = conn.execute("SELECT * FROM qc_hold_batches WHERE id = ?", (batch_id,)).fetchone()
    assert batch is not None
    assert batch["status"] == "pending_images"
    assert batch["production_order_id"] == "MO-QC002"

    # Verify hold line exists with correct quantities
    line = conn.execute("SELECT * FROM qc_hold_batch_lines WHERE qc_hold_batch_id = ?", (batch_id,)).fetchone()
    assert line is not None
    assert line["qty_on_hold"] == 12
    assert line["qty_pending"] == 12
    assert line["qty_released"] == 0
    assert line["qty_scrapped"] == 0
    assert line["line_status"] == "pending_inspection"

    # Verify NO stock row was created for the QC item
    stock = conn.execute("SELECT * FROM stock WHERE item_id = 'ITEM-QC-DUCK' AND location = 'FG'").fetchone()
    assert stock is None, "QC-held item should NOT be in regular stock"

    # Verify production order inspection_status updated
    order = conn.execute("SELECT * FROM production_orders WHERE id = 'MO-QC002'").fetchone()
    assert order["inspection_status"] == "pending_inspection"
    assert order["status"] == "completed"

    conn.close()


def test_normal_completion_creates_stock(qc_db):
    """inspection_required=0 MO completion creates stock as before."""
    from services.production import complete_order

    result = complete_order(
        production_order_id="MO-T001",
        qty_produced=24,
        warehouse="WH-LYON",
        location="FG",
    )

    assert result.get("qc_hold") is not True
    assert "stock_id" in result

    conn = db.get_connection()
    stock = conn.execute("SELECT * FROM stock WHERE id = ?", (result["stock_id"],)).fetchone()
    assert stock is not None
    assert stock["on_hand"] == 24

    # Verify a production_in movement was written
    mov = conn.execute(
        "SELECT * FROM stock_movements WHERE reference_type='production_order' AND reference_id='MO-T001' AND movement_type='production_in'"
    ).fetchone()
    assert mov is not None

    conn.close()


def test_completed_order_cannot_be_completed_again(qc_db):
    """Completing an already-completed order raises ValueError."""
    from services.production import complete_order

    # First completion
    complete_order(
        production_order_id="MO-QC002",
        qty_produced=12,
        warehouse="WH-LYON",
        location="FG",
    )

    # Second should raise
    with pytest.raises(ValueError, match="already completed"):
        complete_order(
            production_order_id="MO-QC002",
            qty_produced=12,
            warehouse="WH-LYON",
            location="FG",
        )
