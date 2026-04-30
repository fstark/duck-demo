"""Data import contract tests."""
import json
import os
import tempfile
from unittest.mock import patch, call

import pytest

import db
from services.data_import import data_import_service, DataImportService

pytestmark = pytest.mark.rest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _confirm_and_process(job_id, mapping, global_instructions=""):
    """Test helper: confirm mapping then run pipeline synchronously (no thread)."""
    data_import_service.confirm_mapping(
        job_id=job_id, mapping=mapping, global_instructions=global_instructions,
    )
    # Run the pipeline synchronously for deterministic tests
    with db.get_connection() as conn:
        conn.execute("UPDATE import_jobs SET status = 'processing' WHERE id = ?", (job_id,))
        conn.commit()
    data_import_service._run_processing_pipeline(job_id, mapping)
    return data_import_service.get_state(job_id)


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

_SAMPLE_SELECT_RESPONSE = _FakeResponse(json.dumps([0, 1, 2]))

_SAMPLE_SELECT_RESPONSE_FULL = _FakeResponse(json.dumps([0, 1, 2, 3]))

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

_SAMPLE_TRANSFORM_RESPONSE = _FakeResponse(json.dumps([
    {"idx": 0, "source_column": "Zahlungsziel", "value": 30, "notes": "30 Tage → 30"},
    {"idx": 3, "source_column": "Zahlungsziel", "value": 45, "notes": "45 jours → 45"},
]))

_TRANSFORM_RESPONSE = _FakeResponse(json.dumps([
    {"row": 1, "source_column": "Zahlungsziel", "value": 30, "notes": "30 Tage → 30"},
    {"row": 4, "source_column": "Zahlungsziel", "value": 45, "notes": "45 jours → 45"},
]))

_SAMPLE_TRANSFORM_RESPONSE = _FakeResponse(json.dumps([
    {"idx": 0, "source_column": "Zahlungsziel", "value": 30, "notes": "30 Tage → 30"},
    {"idx": 3, "source_column": "Zahlungsziel", "value": 45, "notes": "45 jours → 45"},
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


def test_import_jobs_has_new_columns():
    """import_jobs table has global_instructions and sample_indices columns."""
    with db.get_connection() as conn:
        info = conn.execute("PRAGMA table_info(import_jobs)").fetchall()
        col_names = [row[1] for row in info]
        assert "global_instructions" in col_names
        assert "sample_indices" in col_names


# ---------------------------------------------------------------------------
# Step 2: Upload returns mapping state (Phase 1)
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_upload_returns_mapping_state(_mock, tmp_path):
    """upload() returns mapping state with sample rows, not full staging state."""
    csv_content = "Name;City;Country\nAlice;Paris;FR\nBob;London;GB\nCharlie;Berlin;DE\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    result = data_import_service.upload(source=f"file://{csv_file}")
    assert result["status"] == "mapping_review"
    assert result["entity_type"] == "customer"
    assert result["mapping"] is not None
    assert len(result["mapping"]) == 3
    assert "sample_rows" in result
    assert len(result["sample_rows"]) <= 5
    assert "target_fields" in result
    # Should NOT have full rows or batch_questions
    assert "rows" not in result
    assert "batch_questions" not in result


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_upload_csv_parses_rows(_mock, tmp_path):
    """upload() parses a CSV file and stores rows in staging tables."""
    csv_content = "Name;City;Country\nAlice;Paris;FR\nBob;London;GB\nCharlie;Berlin;DE\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    result = data_import_service.upload(source=f"file://{csv_file}")
    assert result["row_count"] == 3
    assert result["status"] == "mapping_review"
    assert "sample_rows" in result


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_upload_csv_detects_semicolon_delimiter(_mock, tmp_path):
    """Semicolon-separated CSV is parsed correctly."""
    csv_content = "A;B;C\n1;2;3\n4;5;6\n7;8;9\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    result = data_import_service.upload(source=f"file://{csv_file}")
    assert result["row_count"] == 3
    assert "A" in result["columns_detected"]


# ---------------------------------------------------------------------------
# Step 3: Preview sample
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_preview_sample(_mock, tmp_path):
    """preview_sample() re-transforms sample rows with updated mapping."""
    csv_content = "Name;City;Country\nAlice;Paris;france\nBob;London;GB\nCharlie;Berlin;DE\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]

    # Modify the mapping (swap target for City)
    modified_mapping = [
        {"source": "Name", "target": "company", "transform": "none", "confidence": 0.95},
        {"source": "City", "target": "city", "transform": "none", "confidence": 0.97},
        {"source": "Country", "target": "country", "transform": "ISO 3166-1 alpha-2", "confidence": 0.88},
    ]
    preview = data_import_service.preview_sample(job_id=job_id, mapping=modified_mapping)
    assert preview["job_id"] == job_id
    assert "sample_rows" in preview
    # The first row should have "company" key mapped with "Alice"
    assert preview["sample_rows"][0]["mapped_data"]["company"] == "Alice"


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_preview_sample_with_excluded_column(_mock, tmp_path):
    """preview_sample() excludes columns with target=null."""
    csv_content = "Name;City;Country\nAlice;Paris;FR\nBob;London;GB\nCharlie;Berlin;DE\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]

    # Exclude City column
    modified_mapping = [
        {"source": "Name", "target": "name", "transform": "none", "confidence": 0.95},
        {"source": "City", "target": None, "transform": "none", "confidence": 0.97},
        {"source": "Country", "target": "country", "transform": "ISO 3166-1 alpha-2", "confidence": 0.88},
    ]
    preview = data_import_service.preview_sample(job_id=job_id, mapping=modified_mapping)
    # city should not be in mapped_data
    assert "city" not in preview["sample_rows"][0]["mapped_data"]


# ---------------------------------------------------------------------------
# Step 4: Confirm mapping
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_confirm_mapping(_mock, tmp_path):
    """confirm_mapping() persists mapping, start_processing transitions to validated."""
    csv_content = "Name;City;Country\nAlice;Paris;FR\nBob;London;GB\nCharlie;Berlin;DE\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]

    mapping = upload_result["mapping"]
    # Phase 1: confirm just persists
    confirm_result = data_import_service.confirm_mapping(
        job_id=job_id, mapping=mapping, global_instructions="All dates DD/MM/YYYY",
    )
    assert confirm_result["status"] == "mapped"

    # Phase 2: processing runs pipeline
    result = _confirm_and_process(job_id, mapping, global_instructions="All dates DD/MM/YYYY")
    assert result["status"] == "validated"
    assert "rows" in result
    assert len(result["rows"]) == 3
    assert result["global_instructions"] == "All dates DD/MM/YYYY"

    # Verify DB has global_instructions persisted
    with db.get_connection() as conn:
        job = conn.execute("SELECT global_instructions FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
        assert job[0] == "All dates DD/MM/YYYY"


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_confirm_mapping_with_edited_mapping(_mock, tmp_path):
    """Processing uses the user's edited mapping, not the LLM proposal."""
    csv_content = "Name;City;Country\nAlice;Paris;france\nBob;London;GB\nCharlie;Berlin;DE\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]

    # Change: map "Name" to "company" instead of "name"
    edited_mapping = [
        {"source": "Name", "target": "company", "transform": "none", "confidence": 0.95},
        {"source": "City", "target": "city", "transform": "none", "confidence": 0.97},
        {"source": "Country", "target": "country", "transform": "ISO 3166-1 alpha-2", "confidence": 0.88},
    ]
    result = _confirm_and_process(job_id, edited_mapping)
    # Row 1 should have "company": "Alice"
    row1 = result["rows"][0]
    assert row1["mapped_data"]["company"] == "Alice"
    # Country should be normalized
    assert row1["mapped_data"]["country"] == "FR"


# ---------------------------------------------------------------------------
# Step 5: Fix uses global_instructions
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[
    _DETECT_RESPONSE, _MAP_RESPONSE,  # upload (no sample select: ≤5 rows)
    _FakeResponse(json.dumps({  # fix
        "actions": [{"type": "set_value", "row": 1, "field": "name", "value": "FixedAlice"}],
        "reasoning": "applied fix",
    })),
])
def test_fix_uses_global_instructions(_mock, tmp_path):
    """fix() includes global_instructions in the LLM prompt."""
    csv_content = "Name;City;Country\nAlice;Paris;FR\nBob;London;GB\nCharlie;Berlin;DE\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]
    mapping = upload_result["mapping"]

    # Confirm with global instructions + run pipeline
    _confirm_and_process(job_id, mapping, global_instructions="All dates DD/MM/YYYY")

    # Now call fix
    data_import_service.fix(job_id=job_id, instruction="fix the names")

    # Verify the LLM prompt for fix included global_instructions
    fix_call = _mock.call_args_list[-1]
    prompt_text = fix_call.kwargs["messages"][0]["content"] if "messages" in fix_call.kwargs else fix_call[1]["messages"][0]["content"]
    assert "All dates DD/MM/YYYY" in prompt_text


# ---------------------------------------------------------------------------
# Step 6: Sample selection fallback
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_sample_selection_fallback_small_dataset(_mock, tmp_path):
    """Dataset <= 5 rows uses fallback indices (no LLM call for selection)."""
    csv_content = "Name;City;Country\nAlice;Paris;FR\nBob;London;GB\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    result = data_import_service.upload(source=f"file://{csv_file}")
    # Only 2 LLM calls (detect + map), no sample selection call
    assert _mock.call_count == 2
    assert len(result["sample_rows"]) == 2


# ---------------------------------------------------------------------------
# Step 7: Full pipeline (upload → confirm → fix → execute)
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_fix_keep_all(_mock, tmp_path):
    """fix() with 'keep all' sets needs_review rows to ready."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City;Country\nAlice;Paris;FR\nBob;London;GB\nCharlie;Berlin;DE\n")

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]
    mapping = upload_result["mapping"]

    # Confirm + process (transitions to Phase 2)
    _confirm_and_process(job_id, mapping)

    fix_result = data_import_service.fix(job_id=job_id, instruction="keep all")
    for row in fix_result["rows"]:
        assert row["status"] in ("ready", "merged", "imported")


@patch("services.data_import.chat_completion", side_effect=[_DETECT_RESPONSE, _MAP_RESPONSE])
def test_execute_creates_customers(_mock, tmp_path):
    """execute() creates customer records in the customers table."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City;Country\nTestImport;Paris;FR\nBob;London;GB\nCharlie;Berlin;DE\n")

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]
    mapping = upload_result["mapping"]

    # Confirm + process
    _confirm_and_process(job_id, mapping)

    # Ensure rows are ready
    data_import_service.fix(job_id=job_id, instruction="keep all")

    exec_result = data_import_service.execute(job_id=job_id)
    assert exec_result["status"] == "executed"
    assert len(exec_result.get("created", [])) >= 1
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
    csv_file.write_text("Name;City;Country\nRollbackTest;London;GB\nBob;Paris;FR\nCharlie;Berlin;DE\n")

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]
    mapping = upload_result["mapping"]

    _confirm_and_process(job_id, mapping)
    data_import_service.fix(job_id=job_id, instruction="keep all")
    exec_result = data_import_service.execute(job_id=job_id)
    entity_id = exec_result["created"][0]["entity_id"]

    with db.get_connection() as conn:
        assert conn.execute("SELECT id FROM customers WHERE id = ?", (entity_id,)).fetchone() is not None

    rb_result = data_import_service.rollback(job_id=job_id)
    assert rb_result["status"] == "rolled_back"

    with db.get_connection() as conn:
        assert conn.execute("SELECT id FROM customers WHERE id = ?", (entity_id,)).fetchone() is None


# ---------------------------------------------------------------------------
# Python transforms
# ---------------------------------------------------------------------------

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
# Demo CSV full pipeline test
# ---------------------------------------------------------------------------

DEMO_CSV = (
    "Kd-Nr;Firma;Ansprechpartner;E-Mail;Straße;PLZ;Ort;Land;Telefon;Zahlungsziel\n"
    "101;DuckFan Paris SARL;Jean Dupont;jean@duckfan-paris.example;12 Rue du Canard;75001;Paris;france;+33 1 23 45 67 89;30 Tage\n"
    "102;QuackShop London;;orders@quackshop.co.uk;42 Mallard Lane;SW1A 1AA;London;GB;+44 20 1234 5678;\n"
    "103;Enten-Welt GmbH;Hans Müller;hans@entenwelt.example;Entenstraße 7;10115;Berlin;DE;+49 30 9876543;60 Tage\n"
    "104;DuckFan Paris SARL;J. Dupont;j.dupont@duckfan-paris.example;12 Rue du Canard;75001;Paris;FR;;45 jours\n"
)


@patch("services.data_import.chat_completion", side_effect=[
    _DETECT_RESPONSE, _MAP_RESPONSE_FULL, _SAMPLE_SELECT_RESPONSE_FULL,  # upload (Phase 1)
    _SAMPLE_TRANSFORM_RESPONSE,  # sample transform in upload
    _TRANSFORM_RESPONSE,  # start_processing full transform
])
def test_demo_csv_full_pipeline(_mock, tmp_path):
    """The demo German CSV goes through the full two-step pipeline."""
    csv_file = tmp_path / "Kundenstammdaten.csv"
    csv_file.write_text(DEMO_CSV, encoding="utf-8")

    # Phase 1: upload returns mapping state
    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    assert upload_result["entity_type"] == "customer"
    assert upload_result["row_count"] == 4
    assert upload_result["status"] == "mapping_review"
    assert "sample_rows" in upload_result

    # Phase 2: confirm + process
    mapping = upload_result["mapping"]
    confirm_result = data_import_service.confirm_mapping(job_id=upload_result["job_id"], mapping=mapping)
    assert confirm_result["status"] == "mapped"

    result = _confirm_and_process(upload_result["job_id"], mapping)
    assert result["status"] == "validated"
    assert "rows" in result
    # Should detect the internal duplicate (rows 1 and 4, same company + city)
    batch_questions = result.get("batch_questions", [])
    dup_questions = [q for q in batch_questions if q.get("issue_type") == "possible_duplicate"]
    assert len(dup_questions) >= 1


# ---------------------------------------------------------------------------
# Fix merges test
# ---------------------------------------------------------------------------

@patch("services.data_import.chat_completion", side_effect=[
    _DETECT_RESPONSE, _MAP_RESPONSE,  # upload (no sample select: ≤5 rows)
    _FakeResponse(json.dumps({  # fix
        "actions": [{"type": "merge", "rows": [1, 2], "merged_values": {"name": "Alice", "city": "Paris"}}],
        "reasoning": "merged as requested",
    })),
])
def test_fix_merges_duplicate_rows(_mock, tmp_path):
    """fix() merges rows when instructed."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name;City;Country\nAlice;Paris;FR\nAlice;Paris;FR\nBob;Berlin;DE\n")

    upload_result = data_import_service.upload(source=f"file://{csv_file}")
    job_id = upload_result["job_id"]
    mapping = upload_result["mapping"]

    # Confirm + process
    _confirm_and_process(job_id, mapping)

    fix_result = data_import_service.fix(job_id=job_id, instruction="merge the duplicates")
    active_rows = [r for r in fix_result["rows"] if r["status"] != "merged"]
    assert len(active_rows) == 2  # one merged + Bob remains

