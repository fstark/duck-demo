"""Tests – QC replacement creation on scrap dispositions."""

import pytest
import db
from services.simulation import simulation_service


def _setup_full_scrap(conn, *, batch_id="QCB-T001", insp_id="QCI-T001"):
    """Insert a completed inspection record ready for full-scrap disposition."""
    sim_time = simulation_service.get_current_time()
    conn.execute(
        "INSERT INTO qc_inspections "
        "(id, qc_hold_batch_id, production_order_id, model_name, status, decision, "
        "prompt_version, created_at, completed_at) "
        "VALUES (?, ?, 'MO-QC001', 'gpt-test', 'completed', 'full_scrap', 'v1', ?, ?)",
        (insp_id, batch_id, sim_time, sim_time),
    )
    conn.execute(
        "UPDATE qc_hold_batches SET status='inspected' WHERE id=?", (batch_id,)
    )
    conn.commit()


def test_full_scrap_creates_replacement(qc_db):
    """Full scrap with sales_order_id creates a replacement MO."""
    conn = db.get_connection()
    _setup_full_scrap(conn)
    conn.close()

    from services.qc import qc_service
    qc_service.apply_disposition(
        qc_inspection_id="QCI-T001",
        action="full_scrap",
        approved_by="test_user",
    )

    conn = db.get_connection()
    # Find the replacement record
    repl = conn.execute(
        "SELECT * FROM qc_replacements WHERE qc_disposition_id IN "
        "(SELECT id FROM qc_dispositions WHERE qc_hold_batch_id='QCB-T001')"
    ).fetchone()
    assert repl is not None, "Replacement row should have been created"
    assert repl["qty_short"] == 12
    assert repl["sales_order_id"] == "SO-QC001"
    assert repl["item_id"] == "ITEM-QC-DUCK"

    # Output qty from QC recipe is 12, ceil(12/12)*12 = 12
    assert repl["qty_replacement"] == 12

    # A replacement MO should have been created
    assert repl["replacement_production_order_id"] != "", "Replacement MO ID should be set"
    mo = conn.execute(
        "SELECT * FROM production_orders WHERE id = ?",
        (repl["replacement_production_order_id"],),
    ).fetchone()
    assert mo is not None
    assert mo["sales_order_id"] == "SO-QC001"

    conn.close()


def test_partial_scrap_creates_replacement(qc_db):
    """Partial scrap creates a replacement for the scrapped portion."""
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO qc_inspections "
        "(id, qc_hold_batch_id, production_order_id, model_name, status, decision, "
        "prompt_version, created_at, completed_at) "
        "VALUES ('QCI-T002', 'QCB-T001', 'MO-QC001', 'gpt-test', 'completed', 'partial_scrap', 'v1', ?, ?)",
        (simulation_service.get_current_time(), simulation_service.get_current_time()),
    )
    conn.execute("UPDATE qc_hold_batches SET status='inspected' WHERE id='QCB-T001'")
    conn.commit()
    conn.close()

    from services.qc import qc_service
    qc_service.apply_disposition(
        qc_inspection_id="QCI-T002",
        action="partial_scrap",
        qty_scrapped=4,
    )

    conn = db.get_connection()
    repl = conn.execute(
        "SELECT * FROM qc_replacements WHERE qc_disposition_id IN "
        "(SELECT id FROM qc_dispositions WHERE qc_hold_batch_id='QCB-T001')"
    ).fetchone()
    assert repl is not None
    assert repl["qty_short"] == 4
    # ceil(4/12)*12 = 12 (round up to batch size)
    assert repl["qty_replacement"] == 12
    conn.close()


def test_pass_release_no_replacement(qc_db):
    """Pass release does NOT create a replacement (nothing was scrapped)."""
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO qc_inspections "
        "(id, qc_hold_batch_id, production_order_id, model_name, status, decision, "
        "prompt_version, created_at, completed_at) "
        "VALUES ('QCI-T003', 'QCB-T001', 'MO-QC001', 'gpt-test', 'completed', 'pass', 'v1', ?, ?)",
        (simulation_service.get_current_time(), simulation_service.get_current_time()),
    )
    conn.execute("UPDATE qc_hold_batches SET status='inspected' WHERE id='QCB-T001'")
    conn.commit()
    conn.close()

    from services.qc import qc_service
    qc_service.apply_disposition(
        qc_inspection_id="QCI-T003",
        action="pass_release",
    )

    conn = db.get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM qc_replacements WHERE qc_disposition_id IN "
        "(SELECT id FROM qc_dispositions WHERE qc_hold_batch_id='QCB-T001')"
    ).fetchone()[0]
    assert count == 0, "No replacement should be created for pass_release"
    conn.close()
