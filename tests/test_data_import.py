"""Data import contract tests."""
import json
import os
import tempfile
from unittest.mock import patch

import pytest

import db
from services.data_import import data_import_service, DataImportService

pytestmark = pytest.mark.rest


# ---------------------------------------------------------------------------
# Fake LLM response helpers (same pattern as test_mcp_tariff.py)
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content): self.content = content

class _FakeChoice:
    def __init__(self, content): self.message = _FakeMessage(content)

class _FakeResponse:
    def __init__(self, content): self.choices = [_FakeChoice(content)]


_DETECT_RESPONSE = _FakeResponse(
    '{"entity_type": "customer", "confidence": 0.95, "reason": "has company, name, email columns"}'
)

_MAP_RESPONSE = _FakeResponse(json.dumps([
    {"source": "Name", "target": "name", "transform": "none", "confidence": 0.95},
    {"source": "City", "target": "city", "transform": "none", "confidence": 0.97},
    {"source": "Country", "target": "country", "transform": "ISO 3166-1 alpha-2", "confidence": 0.88},
]))

_MAP_RESPONSE_FULL = _FakeResponse(json.dumps([
    {"source": "Kd-Nr", "target": "external_ref", "transform": "none", "confidence": 0.72},
    {"source": "Firma", "target": "company", "transform": "none", "confidence": 0.95},
    {"source": "Ansprechpartner", "target": "name", "transform": "none", "confidence": 0.91},
    {"source": "E-Mail", "target": "email", "transform": "lowercase", "confidence": 0.98},
    {"source": "Straße", "target": "address_line1", "transform": "none", "confidence": 0.94},
    {"source": "PLZ", "target": "postal_code", "transform": "none", "confidence": 0.96},
    {"source": "Ort", "target": "city", "transform": "none", "confidence": 0.97},
    {"source": "Land", "target": "country", "transform": "ISO 3166-1 alpha-2", "confidence": 0.88},
    {"source": "Telefon", "target": "phone", "transform": "none", "confidence": 0.85},
    {"source": "Zahlungsziel", "target": "payment_terms", "transform": "parse integer from text", "confidence": 0.79},
]))

_TRANSFORM_RESPONSE = _FakeResponse(json.dumps([
    {"row": 1, "source_column": "Zahlungsziel", "value": 30, "notes": "30 Tage → 30"},
    {"row": 4, "source_column": "Zahlungsziel", "value": 45, "notes": "45 jours → 45"},
]))


# ---------------------------------------------------------------------------
# Step 1: Schema tests
# ---------------------------------------------------------------------------

def test_import_tables_exist():
    """Schema creates import_jobs and import_rows tables."""
    with db.get_connection() as conn:
        for table in ("import_jobs", "import_rows"):
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            assert row is not None, f"Table {table} not found"


# ---------------------------------------------------------------------------
# Step 2: CSV parsing (no LLM)
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_upload_csv_parses_rows(_mock, tmp_path):
    """upload() parses a CSV file and stores rows in staging tables."""
    csv_content = "Name;City;Country\nAlice;Paris;FR\nBob;London;GB\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    result = data_import_service.upload(source=f"file://{csv_file}")
    assert result["row_count"] == 2
    assert result["status"] in ("staging", "validated")
    assert len(result["rows"]) == 2
    assert result["rows"][0]["raw_data"]["Name"] == "Alice"


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_upload_csv_detects_semicolon_delimiter(_mock, tmp_path):
    """Semicolon-separated CSV is parsed correctly."""
    csv_content = "A;B;C\n1;2;3\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    result = data_import_service.upload(source=f"file://{csv_file}")
    assert result["row_count"] == 1
    assert "A" in result["rows"][0]["raw_data"]


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_get_state_returns_same_as_upload(_mock, tmp_path):
    """get_state() returns the same shape as upload()."""
    csv_content = "Name;City;Country\n1;2;FR\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    state_result = data_import_service.get_state(upload_result["job_id"])
    assert state_result["job_id"] == upload_result["job_id"]
    assert state_result["row_count"] == upload_result["row_count"]


# ---------------------------------------------------------------------------
# Step 3: LLM detect + map + transform (mocked)
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_upload_with_llm_detect_and_map(_mock, tmp_path):
    """upload() calls LLM for entity detection and column mapping."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City;Country\nAlice;Paris;FR\nBob;London;GB\n")

    result = data_import_service.upload(source=f"file://{csv_file}")
    assert result["entity_type"] == "customer"
    assert result["mapping"] is not None
    assert len(result["mapping"]) == 3
    assert _mock.call_count >= 2  # at least detect + map


def test_python_transforms_country_code():
    """Python transforms normalise 'france' to 'FR' without LLM."""
    svc = DataImportService()
    assert svc._python_transform("ISO 3166-1 alpha-2", "france") == "FR"
    assert svc._python_transform("ISO 3166-1 alpha-2", "FR") == "FR"
    assert svc._python_transform("ISO 3166-1 alpha-2", "gb") == "GB"


def test_python_transforms_email_lowercase():
    """Python transforms lowercase emails."""
    svc = DataImportService()
    assert svc._python_transform("lowercase", "Alice@Test.COM") == "alice@test.com"


# ---------------------------------------------------------------------------
# Step 9: Demo CSV full pipeline test
# ---------------------------------------------------------------------------

DEMO_CSV = (
    "Kd-Nr;Firma;Ansprechpartner;E-Mail;Straße;PLZ;Ort;Land;Telefon;Zahlungsziel\n"
    "101;DuckFan Paris SARL;Jean Dupont;jean@duckfan-paris.example;12 Rue du Canard;75001;Paris;france;+33 1 23 45 67 89;30 Tage\n"
    "102;QuackShop London;;orders@quackshop.co.uk;42 Mallard Lane;SW1A 1AA;London;GB;+44 20 1234 5678;\n"
    "103;Enten-Welt GmbH;Hans Müller;hans@entenwelt.example;Entenstraße 7;10115;Berlin;DE;+49 30 9876543;60 Tage\n"
    "104;DuckFan Paris SARL;J. Dupont;j.dupont@duckfan-paris.example;12 Rue du Canard;75001;Paris;FR;;45 jours\n"
)


@patch("services.data_import.chat_completion", side_effect=[
    _DETECT_RESPONSE, _MAP_RESPONSE_FULL, _TRANSFORM_RESPONSE,
])
def test_demo_csv_full_pipeline(_mock, tmp_path):
    """The demo German CSV goes through the full upload pipeline."""
    csv_file = tmp_path / "Kundenstammdaten.csv"
    csv_file.write_text(DEMO_CSV, encoding="utf-8")

    result = data_import_service.upload(source=f"file://{csv_file}")
    assert result["entity_type"] == "customer"
    assert result["row_count"] == 4
    # Should detect the internal duplicate (rows 1 and 4, same company + city)
    batch_questions = result.get("batch_questions", [])
    dup_questions = [q for q in batch_questions if q.get("issue_type") == "possible_duplicate"]
    assert len(dup_questions) >= 1


# ---------------------------------------------------------------------------
# Step 5/6: Fix + Execute tests
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[
    _DETECT_RESPONSE, _MAP_RESPONSE,  # upload
    _FakeResponse(json.dumps({  # fix
        "actions": [{"type": "merge", "rows": [1, 2], "merged_values": {"name": "Alice", "city": "Paris"}}],
        "reasoning": "merged as requested",
    })),
])
def test_fix_merges_duplicate_rows(_mock, tmp_path):
    """fix() merges rows when instructed."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City;Country\nAlice;Paris;FR\nAlice;Paris;FR\n")

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]

    fix_result = data_import_service.fix(job_id=job_id, instruction="merge the duplicates")
    active_rows = [r for r in fix_result["rows"] if r["status"] != "merged"]
    assert len(active_rows) == 1


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_fix_keep_all(_mock, tmp_path):
    """fix() with 'keep all' sets needs_review rows to ready."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City;Country\nAlice;Paris;FR\n")

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]

    fix_result = data_import_service.fix(job_id=job_id, instruction="keep all")
    for row in fix_result["rows"]:
        assert row["status"] in ("ready", "merged", "imported")


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_execute_creates_customers(_mock, tmp_path):
    """execute() creates customer records in the customers table."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City;Country\nTestImport;Paris;FR\n")

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]

    # Ensure rows are ready
    data_import_service.fix(job_id=job_id, instruction="keep all")

    exec_result = data_import_service.execute(job_id=job_id)
    assert exec_result["status"] == "executed"
    assert len(exec_result.get("created", [])) == 1
    entity_id = exec_result["created"][0]["entity_id"]

    # Verify customer exists
    with db.get_connection() as conn:
        cust = conn.execute("SELECT * FROM customers WHERE id = ?", (entity_id,)).fetchone()
        assert cust is not None
        assert dict(cust)["name"] == "TestImport"


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_rollback_deletes_created_customers(_mock, tmp_path):
    """rollback() removes customers created by execute()."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City;Country\nRollbackTest;London;GB\n")

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]
    data_import_service.fix(job_id=job_id, instruction="keep all")
    exec_result = data_import_service.execute(job_id=job_id)
    entity_id = exec_result["created"][0]["entity_id"]

    # Verify customer exists before rollback
    with db.get_connection() as conn:
        assert conn.execute("SELECT id FROM customers WHERE id = ?", (entity_id,)).fetchone() is not None

    rb_result = data_import_service.rollback(job_id=job_id)
    assert rb_result["status"] == "rolled_back"

    with db.get_connection() as conn:
        assert conn.execute("SELECT id FROM customers WHERE id = ?", (entity_id,)).fetchone() is None

