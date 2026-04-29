"""Scenario contract tests – QC fixtures injected by s01.

These tests verify that after running scenario s01, exactly 3 QC hold batches
with 'pending_images' status exist, bound to the expected SKUs.

We run the scenario against a fresh in-memory DB rather than the session DB
to avoid polluting other tests.
"""

import pytest

from scenarios.s01_steady_state import run as run_s01
import db


@pytest.fixture()
def scenario_db(tmp_path, monkeypatch):
    """Fresh DB seeded by s01 scenario."""
    db_file = tmp_path / "scenario_test.db"
    monkeypatch.setattr(db, "DB_PATH", db_file)
    db.init_db()

    from scenarios.base_setup import populate as base_setup
    # Initialize simulation_state before base_setup uses simulation_service
    import db as _db
    conn = _db.get_connection()
    conn.execute("INSERT OR IGNORE INTO simulation_state (id, sim_time) VALUES (1, '2025-07-01 00:00:00')")
    conn.commit()
    conn.close()
    base_result = base_setup()
    ctx = {"customer_ids": base_result["customer_ids"], "base_result": base_result}
    run_s01(ctx)

    yield db_file


def test_s01_creates_three_pending_qc_batches(scenario_db):
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT id FROM qc_hold_batches WHERE status = 'pending_images'"
    ).fetchall()
    conn.close()
    assert len(rows) == 3


def test_s01_qc_batches_have_correct_skus(scenario_db):
    conn = db.get_connection()
    rows = conn.execute(
        """
        SELECT DISTINCT i.sku
        FROM qc_hold_batches qhb
        JOIN qc_hold_batch_lines qhbl ON qhbl.qc_hold_batch_id = qhb.id
        JOIN items i ON i.id = qhbl.item_id
        WHERE qhb.status = 'pending_images'
        """
    ).fetchall()
    conn.close()

    skus = {r["sku"] for r in rows}
    assert "ELVIS-DUCK-20CM" in skus
    assert "MARILYN-DUCK-20CM" in skus
    assert "ZOMBIE-DUCK-15CM" in skus


def test_s01_qc_batches_not_consumed_by_shipments(scenario_db):
    """QC hold stock should not appear consumed in shipment allocations."""
    conn = db.get_connection()
    # The QC hold lines must be in pending_inspection status
    rows = conn.execute(
        """
        SELECT qhbl.line_status FROM qc_hold_batch_lines qhbl
        WHERE qhbl.qc_hold_batch_id IN (
            SELECT id FROM qc_hold_batches WHERE status = 'pending_images'
        )
        """
    ).fetchall()
    conn.close()
    for row in rows:
        assert row["line_status"] == "pending_inspection"
