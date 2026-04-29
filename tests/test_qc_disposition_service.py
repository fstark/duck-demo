"""Tests – QC disposition service: quantity math, movement types, idempotency."""

import pytest
import db
import config


def _setup_inspected_batch(conn):
    """Insert a completed inspection into the test DB for the seeded QCB-T001 batch."""
    from services.simulation import simulation_service
    sim_time = simulation_service.get_current_time()

    conn.execute(
        "INSERT INTO qc_inspections "
        "(id, qc_hold_batch_id, production_order_id, model_name, status, decision, "
        "prompt_version, created_at, completed_at, confidence_overall, decision_reason) "
        "VALUES (?, 'QCB-T001', 'MO-QC001', 'gpt-test', 'completed', 'pass', 'v1', ?, ?, 0.9, 'All good')",
        ("QCI-T001", sim_time, sim_time),
    )
    conn.execute(
        "UPDATE qc_hold_batches SET status = 'inspected' WHERE id = 'QCB-T001'"
    )
    conn.commit()
    return "QCI-T001"


def test_pass_release_qty_math(qc_db):
    conn = db.get_connection()
    insp_id = _setup_inspected_batch(conn)
    conn.close()

    from services.qc import qc_service
    result = qc_service.apply_disposition(
        qc_inspection_id=insp_id,
        action="pass_release",
        approved_by="test_user",
    )

    conn = db.get_connection()
    line = conn.execute("SELECT * FROM qc_hold_batch_lines WHERE qc_hold_batch_id = 'QCB-T001'").fetchone()
    assert line["qty_pending"] == 0
    assert line["qty_released"] == 12
    assert line["qty_scrapped"] == 0
    assert line["line_status"] == "released"

    # Verify stock was created
    stock = conn.execute(
        "SELECT * FROM stock WHERE item_id = 'ITEM-QC-DUCK' AND location = ?",
        (config.LOC_FINISHED_GOODS,),
    ).fetchone()
    assert stock is not None
    assert stock["on_hand"] == 12

    # Verify qc_hold_release movement
    mov = conn.execute(
        "SELECT * FROM stock_movements WHERE item_id='ITEM-QC-DUCK' AND movement_type='qc_hold_release'"
    ).fetchone()
    assert mov is not None
    assert mov["qty"] == 12
    assert mov["qc_inspection_id"] == insp_id

    conn.close()


def test_full_scrap_qty_math(qc_db):
    conn = db.get_connection()
    insp_id = _setup_inspected_batch(conn)
    conn.execute("UPDATE qc_inspections SET decision='full_scrap' WHERE id=?", (insp_id,))
    conn.commit()
    conn.close()

    from services.qc import qc_service
    qc_service.apply_disposition(
        qc_inspection_id=insp_id,
        action="full_scrap",
        approved_by="test_user",
    )

    conn = db.get_connection()
    line = conn.execute("SELECT * FROM qc_hold_batch_lines WHERE qc_hold_batch_id = 'QCB-T001'").fetchone()
    assert line["qty_pending"] == 0
    assert line["qty_released"] == 0
    assert line["qty_scrapped"] == 12
    assert line["line_status"] == "scrapped"

    # Verify NO stock was created for scrapped items
    stock = conn.execute("SELECT * FROM stock WHERE item_id='ITEM-QC-DUCK' AND location=?",
                         (config.LOC_FINISHED_GOODS,)).fetchone()
    assert stock is None

    # Verify qc_scrap movement with stock_id=NULL
    mov = conn.execute(
        "SELECT * FROM stock_movements WHERE item_id='ITEM-QC-DUCK' AND movement_type='qc_scrap'"
    ).fetchone()
    assert mov is not None
    assert mov["qty"] == 12
    assert mov["stock_id"] is None

    conn.close()


def test_partial_scrap_qty_math(qc_db):
    conn = db.get_connection()
    insp_id = _setup_inspected_batch(conn)
    conn.execute("UPDATE qc_inspections SET decision='partial_scrap' WHERE id=?", (insp_id,))
    conn.commit()
    conn.close()

    from services.qc import qc_service
    qc_service.apply_disposition(
        qc_inspection_id=insp_id,
        action="partial_scrap",
        qty_scrapped=4,
        approved_by="test_user",
    )

    conn = db.get_connection()
    line = conn.execute("SELECT * FROM qc_hold_batch_lines WHERE qc_hold_batch_id = 'QCB-T001'").fetchone()
    assert line["qty_pending"] == 0
    assert line["qty_released"] == 8
    assert line["qty_scrapped"] == 4
    assert line["line_status"] == "partially_released"

    # Stock should be 8
    stock = conn.execute("SELECT * FROM stock WHERE item_id='ITEM-QC-DUCK' AND location=?",
                         (config.LOC_FINISHED_GOODS,)).fetchone()
    assert stock is not None
    assert stock["on_hand"] == 8

    # Both movements should exist
    release_mov = conn.execute(
        "SELECT * FROM stock_movements WHERE item_id='ITEM-QC-DUCK' AND movement_type='qc_hold_release'"
    ).fetchone()
    assert release_mov is not None
    assert release_mov["qty"] == 8

    scrap_mov = conn.execute(
        "SELECT * FROM stock_movements WHERE item_id='ITEM-QC-DUCK' AND movement_type='qc_scrap'"
    ).fetchone()
    assert scrap_mov is not None
    assert scrap_mov["qty"] == 4

    conn.close()


def test_disposition_idempotent(qc_db):
    """Calling apply_disposition twice does not double-apply the disposition."""
    conn = db.get_connection()
    insp_id = _setup_inspected_batch(conn)
    conn.close()

    from services.qc import qc_service
    result1 = qc_service.apply_disposition(
        qc_inspection_id=insp_id,
        action="pass_release",
    )
    result2 = qc_service.apply_disposition(
        qc_inspection_id=insp_id,
        action="pass_release",
    )

    conn = db.get_connection()
    # There should be exactly one disposition record
    count = conn.execute(
        "SELECT COUNT(*) FROM qc_dispositions WHERE qc_inspection_id = ?", (insp_id,)
    ).fetchone()[0]
    assert count == 1

    # Stock should only have 12 (not 24)
    stock_count = conn.execute(
        "SELECT SUM(on_hand) FROM stock WHERE item_id='ITEM-QC-DUCK' AND location=?",
        (config.LOC_FINISHED_GOODS,),
    ).fetchone()[0]
    assert stock_count == 12

    conn.close()


def test_partial_scrap_requires_positive_qty(qc_db):
    conn = db.get_connection()
    insp_id = _setup_inspected_batch(conn)
    conn.close()

    from services.qc import qc_service
    with pytest.raises(ValueError, match="qty_scrapped > 0"):
        qc_service.apply_disposition(
            qc_inspection_id=insp_id,
            action="partial_scrap",
            qty_scrapped=0,
        )


def test_partial_scrap_cannot_exceed_pending(qc_db):
    conn = db.get_connection()
    insp_id = _setup_inspected_batch(conn)
    conn.close()

    from services.qc import qc_service
    with pytest.raises(ValueError, match="qty_scrapped"):
        qc_service.apply_disposition(
            qc_inspection_id=insp_id,
            action="partial_scrap",
            qty_scrapped=12,  # equal to qty_pending — must use full_scrap
        )
