"""Tests – QC schema: all tables, columns, indexes exist and defaults work."""

import sqlite3
import pytest

import db


def _get_tables(conn: sqlite3.Connection) -> set:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _get_columns(conn: sqlite3.Connection, table: str) -> dict:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1]: r for r in rows}  # name → row


def _get_indexes(conn: sqlite3.Connection) -> set:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}


def test_qc_tables_exist(qc_db):
    conn = db.get_connection()
    tables = _get_tables(conn)
    conn.close()
    for table in [
        "qc_hold_batches",
        "qc_hold_batch_lines",
        "qc_hold_images",
        "qc_inspections",
        "qc_inspection_findings",
        "qc_dispositions",
        "qc_replacements",
    ]:
        assert table in tables, f"Table {table} missing from schema"


def test_qc_hold_batches_columns(qc_db):
    conn = db.get_connection()
    cols = _get_columns(conn, "qc_hold_batches")
    conn.close()
    for col in ["id", "production_order_id", "sales_order_id", "item_id", "status",
                "created_at", "released_at", "replacement_triggered"]:
        assert col in cols, f"Column {col} missing from qc_hold_batches"


def test_qc_hold_batch_lines_columns(qc_db):
    conn = db.get_connection()
    cols = _get_columns(conn, "qc_hold_batch_lines")
    conn.close()
    for col in ["id", "qc_hold_batch_id", "item_id", "qty_on_hold", "qty_pending",
                "qty_released", "qty_scrapped", "line_status", "created_at"]:
        assert col in cols, f"Column {col} missing from qc_hold_batch_lines"


def test_qc_inspections_columns(qc_db):
    conn = db.get_connection()
    cols = _get_columns(conn, "qc_inspections")
    conn.close()
    for col in ["id", "qc_hold_batch_id", "production_order_id", "model_name", "status",
                "decision", "confidence_overall", "decision_reason", "prompt_version",
                "created_at", "completed_at"]:
        assert col in cols, f"Column {col} missing from qc_inspections"


def test_production_orders_has_qc_columns(qc_db):
    conn = db.get_connection()
    cols = _get_columns(conn, "production_orders")
    conn.close()
    assert "inspection_required" in cols
    assert "inspection_status" in cols


def test_stock_movements_stock_id_nullable(qc_db):
    """stock_movements.stock_id must be nullable for QC scrap movements."""
    conn = db.get_connection()
    cols = _get_columns(conn, "stock_movements")
    conn.close()
    stock_id_col = cols["stock_id"]
    # notnull == 0 means nullable
    assert stock_id_col[3] == 0, "stock_movements.stock_id should be nullable"


def test_stock_movements_has_qc_tracing_columns(qc_db):
    conn = db.get_connection()
    cols = _get_columns(conn, "stock_movements")
    conn.close()
    assert "qc_hold_batch_line_id" in cols
    assert "qc_inspection_id" in cols


def test_qc_indexes_exist(qc_db):
    conn = db.get_connection()
    indexes = _get_indexes(conn)
    conn.close()
    for idx in [
        "idx_po_qc_required",
        "idx_qc_hold_batch_status",
        "idx_qc_hold_line_status",
        "idx_qc_inspection_batch",
        "idx_qc_inspection_batch_unique",
        "idx_qc_replacements_so",
    ]:
        assert idx in indexes, f"Index {idx} missing from schema"


def test_qc_schema_defaults(qc_db):
    """QC defaults: inspection_required=0, inspection_status='none' on creation."""
    conn = db.get_connection()
    # Insert a minimal MO without specifying QC columns
    conn.execute(
        "INSERT INTO production_orders (id, sales_order_id, recipe_id, item_id) "
        "VALUES ('MO-SCHEMA-TEST', 'SO-T001', 'RCP-CLASSIC-10', 'ITEM-CLASSIC-10')"
    )
    row = conn.execute(
        "SELECT inspection_required, inspection_status FROM production_orders WHERE id = 'MO-SCHEMA-TEST'"
    ).fetchone()
    assert row["inspection_required"] == 0
    assert row["inspection_status"] == "none"
    conn.execute("DELETE FROM production_orders WHERE id = 'MO-SCHEMA-TEST'")
    conn.commit()
    conn.close()
