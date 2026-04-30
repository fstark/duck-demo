"""Service for data import operations.

Manages the import lifecycle:
  file upload → entity detection → column mapping → transforms →
  validation → entity resolution → fix instructions → execute/rollback.
"""

import csv
import difflib
import io
import json
import logging
import os
import re
import threading
import urllib.parse

import chardet

import config
from db import dict_rows, generate_id
from services._base import db_conn
from services.myforterro import chat_completion

logger = logging.getLogger("duck-demo")

# ---------------------------------------------------------------------------
# Entity type registry
# ---------------------------------------------------------------------------

ENTITY_SCHEMAS = {
    "customer": {
        "table": "customers",
        "fields": {
            "gender":        {"required": False, "type": "text"},
            "name":          {"required": True,  "type": "text"},
            "company":       {"required": False, "type": "text"},
            "email":         {"required": False, "type": "email"},
            "phone":         {"required": False, "type": "phone"},
            "address_line1": {"required": False, "type": "text"},
            "address_line2": {"required": False, "type": "text"},
            "city":          {"required": False, "type": "text"},
            "postal_code":   {"required": False, "type": "text"},
            "country":       {"required": False, "type": "country_code"},
            "tax_id":        {"required": False, "type": "text"},
            "payment_terms": {"required": False, "type": "integer"},
            "currency":      {"required": False, "type": "currency_code"},
            "notes":         {"required": False, "type": "text"},
        },
        "dedup_keys": ["email", "tax_id"],
        "fuzzy_keys": ["name", "company", "city"],
        "service_create": "customer_service.create_customer",
    },
}

# Country name → ISO 3166-1 alpha-2 lookup
_COUNTRY_MAP = {
    "france": "FR", "germany": "DE", "deutschland": "DE",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB",
    "united states": "US", "usa": "US", "us": "US",
    "italy": "IT", "italia": "IT", "spain": "ES", "españa": "ES",
    "netherlands": "NL", "belgium": "BE", "belgique": "BE",
    "austria": "AT", "österreich": "AT", "switzerland": "CH",
    "schweiz": "CH", "suisse": "CH", "portugal": "PT",
    "poland": "PL", "czech republic": "CZ", "sweden": "SE",
    "norway": "NO", "denmark": "DK", "finland": "FI",
    "ireland": "IE", "japan": "JP", "canada": "CA",
    "australia": "AU", "china": "CN", "brazil": "BR",
    "mexico": "MX", "india": "IN", "south korea": "KR",
    "luxembourg": "LU",
}


def _sim_now(conn):
    """Get current simulation time."""
    row = conn.execute("SELECT sim_time FROM simulation_state WHERE id = 1").fetchone()
    return row[0] if row else ""


class DataImportService:
    """Data import domain service — parse, map, validate, execute."""

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    def _read_source(self, source: str) -> tuple[bytes, str]:
        """Read file content from source URL. Returns (content_bytes, filename)."""
        if source.startswith("file://"):
            path = urllib.parse.unquote(urllib.parse.urlparse(source).path)
            with open(path, "rb") as f:
                return f.read(), os.path.basename(path)
        raise ValueError(f"Unsupported source scheme: {source}")

    # ------------------------------------------------------------------
    # File parsing
    # ------------------------------------------------------------------

    def _parse_file(self, content: bytes, filename: str) -> tuple[list[dict], str]:
        """Parse file into rows. Returns (rows, format_info)."""
        ext = os.path.splitext(filename)[1].lower()

        if ext in (".csv", ".tsv", ".txt"):
            detected = chardet.detect(content)
            encoding = detected.get("encoding") or "utf-8"
            text = content.decode(encoding)

            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(text[:4096])
            reader = csv.DictReader(io.StringIO(text), dialect=dialect)
            rows = [dict(row) for row in reader]
            format_info = f"csv ({dialect.delimiter!r}-separated, {encoding})"
            return rows, format_info

        if ext == ".json":
            data = json.loads(content)
            if isinstance(data, list):
                return data, "json (array of objects)"
            raise ValueError("JSON must be an array of objects")

        raise ValueError(f"Unsupported file extension: {ext}")

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    def _detect_entity(self, columns: list[str], sample_rows: list[dict]) -> dict:
        """LLM Prompt 1: detect entity type from columns + sample data."""
        prompt = (
            "You are a data classification expert for an ERP system.\n"
            "Given these column headers and sample data, determine which ERP entity this represents.\n\n"
            "Possible entities: customer, item, supplier, sales_order\n\n"
            f"Column headers: {columns}\n"
            f"Sample rows: {json.dumps(sample_rows[:3], default=str)}\n\n"
            'Respond with ONLY a JSON object: {"entity_type": "...", "confidence": 0.95, "reason": "..."}'
        )
        resp = chat_completion(
            model=config.DATA_IMPORT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("LLM entity detection returned unparseable JSON, defaulting to customer")
            return {"entity_type": "customer", "confidence": 0.0, "reason": "fallback"}

    def _generate_mapping(self, columns: list[str], sample_rows: list[dict], entity_type: str) -> list[dict]:
        """LLM Prompt 2: map source columns to target fields."""
        schema = ENTITY_SCHEMAS[entity_type]
        fields_desc = json.dumps(schema["fields"], indent=2)
        columns_with_samples = {}
        for col in columns:
            columns_with_samples[col] = [row.get(col, "") for row in sample_rows[:3]]

        prompt = (
            "You are a data mapping expert for an ERP system.\n"
            "Map each source column to the most appropriate target field.\n\n"
            f"Source columns with sample values:\n{json.dumps(columns_with_samples, indent=2)}\n\n"
            f"Target entity: {entity_type}\n"
            f"Available target fields:\n{fields_desc}\n\n"
            "For each source column, respond with a JSON array:\n"
            '[{"source": "...", "target": "...", "transform": "...", "confidence": 0.0-1.0}]\n\n'
            "Rules:\n"
            '- "transform" describes what conversion is needed (e.g. "ISO 3166-1 alpha-2", "parse integer from text", "none")\n'
            '- "confidence" reflects how certain you are about the mapping\n'
            "- If a column has no good match, set target to null"
        )
        resp = chat_completion(
            model=config.DATA_IMPORT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("LLM column mapping returned unparseable JSON, returning empty mapping")
            return []

    # ------------------------------------------------------------------
    # Python transforms (no LLM)
    # ------------------------------------------------------------------

    def _python_transform(self, transform_type: str, value: str) -> str | int | None:
        """Apply a deterministic Python transform. Returns transformed value or None if not handled."""
        if value is None or value == "":
            return value

        if transform_type in ("ISO 3166-1 alpha-2", "country_code"):
            upper = str(value).strip().upper()
            if len(upper) == 2 and upper.isalpha():
                return upper
            lower = str(value).strip().lower()
            if lower in _COUNTRY_MAP:
                return _COUNTRY_MAP[lower]
            return None  # needs LLM

        if transform_type == "lowercase":
            return str(value).lower()

        if transform_type == "none":
            return value

        return None  # not handled by Python — needs LLM

    # ------------------------------------------------------------------
    # Apply transforms
    # ------------------------------------------------------------------

    def _apply_transforms(self, *, job_id: str, mapping: list[dict]) -> None:
        """Apply mapping + transforms to all rows, writing mapped_data."""
        with db_conn() as conn:
            rows = dict_rows(conn.execute(
                "SELECT id, source_row, raw_data FROM import_rows WHERE job_id = ? ORDER BY source_row",
                (job_id,),
            ).fetchall())

            # Collect values needing LLM transforms
            llm_batch = []
            for row in rows:
                raw = json.loads(row["raw_data"])
                mapped = {}
                for m in mapping:
                    if m.get("target") is None:
                        continue
                    source_val = raw.get(m["source"], "")
                    transform = m.get("transform", "none")
                    py_result = self._python_transform(transform, source_val)
                    if py_result is not None:
                        mapped[m["target"]] = py_result
                    else:
                        llm_batch.append({
                            "row": row["source_row"],
                            "row_id": row["id"],
                            "source_column": m["source"],
                            "target_field": m["target"],
                            "target_type": ENTITY_SCHEMAS.get(
                                conn.execute("SELECT entity_type FROM import_jobs WHERE id=?", (job_id,)).fetchone()[0],
                                {},
                            ).get("fields", {}).get(m["target"], {}).get("type", "text")
                            if False else "text",  # simplified
                            "transform": transform,
                            "raw_value": source_val,
                        })
                        mapped[m["target"]] = source_val  # placeholder

                conn.execute(
                    "UPDATE import_rows SET mapped_data = ? WHERE id = ?",
                    (json.dumps(mapped, default=str), row["id"]),
                )

            # LLM transform batch (if needed)
            if llm_batch:
                try:
                    self._apply_llm_transforms(conn=conn, job_id=job_id, batch=llm_batch)
                except Exception:
                    logger.warning("LLM transform failed, using raw values as fallback", exc_info=True)

            conn.commit()

    def _apply_llm_transforms(self, *, conn, job_id: str, batch: list[dict]) -> None:
        """LLM Prompt 3: batch-transform values that Python couldn't handle."""
        prompt = (
            "You are a data transformation expert. Transform the following raw values "
            "for import into an ERP system.\n\n"
            "For each entry, apply the specified transform and return the cleaned value.\n\n"
            f"Transforms to apply:\n{json.dumps(batch, indent=2)}\n\n"
            "Respond with ONLY a JSON array, one object per input entry:\n"
            '[{"row": 1, "source_column": "...", "value": ..., "notes": "..."}]'
        )
        resp = chat_completion(
            model=config.DATA_IMPORT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        results = json.loads(text)

        # Build lookup: (row, source_column) → value
        lookup = {}
        for r in results:
            lookup[(r["row"], r["source_column"])] = r["value"]

        # Update mapped_data for affected rows
        for item in batch:
            key = (item["row"], item["source_column"])
            if key in lookup:
                row_data = conn.execute(
                    "SELECT mapped_data FROM import_rows WHERE id = ?", (item["row_id"],)
                ).fetchone()
                mapped = json.loads(row_data[0])
                mapped[item["target_field"]] = lookup[key]
                conn.execute(
                    "UPDATE import_rows SET mapped_data = ? WHERE id = ?",
                    (json.dumps(mapped, default=str), item["row_id"]),
                )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_rows(self, *, job_id: str) -> None:
        """Check required fields, type constraints. Write issues + status."""
        with db_conn() as conn:
            job = conn.execute("SELECT entity_type FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
            entity_type = job[0]
            schema = ENTITY_SCHEMAS.get(entity_type)
            if not schema:
                return

            rows = dict_rows(conn.execute(
                "SELECT id, mapped_data, issues, resolved_refs FROM import_rows WHERE job_id = ? AND status NOT IN ('merged') ORDER BY source_row",
                (job_id,),
            ).fetchall())

            for row in rows:
                # Skip rows explicitly handled by the user
                refs = json.loads(row["resolved_refs"]) if row.get("resolved_refs") else {}
                if refs.get("user_rejected") or refs.get("user_approved"):
                    continue

                issues = []  # re-validate from scratch
                mapped = json.loads(row["mapped_data"]) if row["mapped_data"] else {}

                # Check required fields
                for field_name, field_def in schema["fields"].items():
                    if field_def["required"] and not mapped.get(field_name):
                        issues.append({
                            "severity": "error",
                            "field": field_name,
                            "message": f"Required field '{field_name}' is missing",
                        })

                # Check type constraints
                for field_name, value in mapped.items():
                    if value is None or value == "":
                        continue
                    field_def = schema["fields"].get(field_name)
                    if not field_def:
                        continue
                    ftype = field_def["type"]
                    if ftype == "email" and isinstance(value, str) and "@" not in value:
                        issues.append({
                            "severity": "warning",
                            "field": field_name,
                            "message": f"'{value}' does not look like an email address",
                        })
                    elif ftype == "country_code" and isinstance(value, str) and (len(value) != 2 or not value.isalpha()):
                        issues.append({
                            "severity": "warning",
                            "field": field_name,
                            "message": f"'{value}' is not a valid 2-letter country code",
                        })
                    elif ftype == "integer":
                        try:
                            mapped[field_name] = int(value)
                        except (ValueError, TypeError):
                            issues.append({
                                "severity": "warning",
                                "field": field_name,
                                "message": f"'{value}' is not an integer",
                            })

                has_errors = any(i["severity"] == "error" for i in issues)
                has_warnings = any(i["severity"] == "warning" for i in issues)
                status = "rejected" if has_errors else ("needs_review" if has_warnings else "ready")

                conn.execute(
                    "UPDATE import_rows SET issues = ?, status = ?, mapped_data = ? WHERE id = ?",
                    (json.dumps(issues), status, json.dumps(mapped, default=str), row["id"]),
                )

            conn.commit()

    # ------------------------------------------------------------------
    # Entity resolution
    # ------------------------------------------------------------------

    def _resolve_entities(self, *, job_id: str) -> None:
        """Match imported rows against existing records for deduplication."""
        with db_conn() as conn:
            job = conn.execute("SELECT entity_type FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
            entity_type = job[0]
            schema = ENTITY_SCHEMAS.get(entity_type)
            if not schema:
                return

            # Load existing records
            existing = dict_rows(conn.execute(
                f"SELECT * FROM {schema['table']}"
            ).fetchall())

            rows = dict_rows(conn.execute(
                "SELECT id, source_row, mapped_data, issues, status, resolved_refs FROM import_rows WHERE job_id = ? AND status NOT IN ('merged', 'rejected') ORDER BY source_row",
                (job_id,),
            ).fetchall())

            for row in rows:
                # Skip rows the user explicitly approved
                existing_refs = json.loads(row["resolved_refs"]) if row["resolved_refs"] else {}
                if existing_refs.get("user_approved"):
                    continue

                mapped = json.loads(row["mapped_data"]) if row["mapped_data"] else {}
                issues = json.loads(row["issues"]) if row["issues"] else []
                # Remove prior entity-detection issues before re-running
                issues = [i for i in issues if i.get("field") not in ("_entity", "_internal")]
                resolved_refs = {}

                best_match = None
                best_confidence = 0.0

                for rec in existing:
                    confidence = 0.0

                    # Exact key match
                    for key in schema["dedup_keys"]:
                        if mapped.get(key) and rec.get(key):
                            if str(mapped[key]).lower().strip() == str(rec[key]).lower().strip():
                                confidence = 1.0
                                break

                    # Fuzzy match
                    if confidence < 1.0:
                        scores = []
                        for key in schema["fuzzy_keys"]:
                            a = str(mapped.get(key, "")).lower().strip()
                            b = str(rec.get(key, "")).lower().strip()
                            if a and b:
                                scores.append(difflib.SequenceMatcher(None, a, b).ratio())
                        if scores:
                            confidence = max(confidence, sum(scores) / len(scores))

                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = rec

                if best_match and best_confidence >= 0.6:
                    resolved_refs = {
                        "match_id": best_match.get("id", ""),
                        "match_name": best_match.get("name", "") or best_match.get("company", ""),
                        "confidence": round(best_confidence, 2),
                    }
                    if best_confidence >= 0.9:
                        issues.append({
                            "severity": "warning",
                            "field": "_entity",
                            "message": f"Already exists as {best_match.get('id', '')} ({best_match.get('name', '') or best_match.get('company', '')})",
                            "issue_type": "existing_duplicate",
                        })
                        if row["status"] == "ready":
                            conn.execute("UPDATE import_rows SET status = 'needs_review' WHERE id = ?", (row["id"],))
                    else:
                        issues.append({
                            "severity": "warning",
                            "field": "_entity",
                            "message": f"Possible duplicate of {best_match.get('id', '')} ({best_match.get('name', '')}) — confidence {best_confidence:.0%}",
                            "issue_type": "possible_duplicate",
                        })
                        if row["status"] == "ready":
                            conn.execute("UPDATE import_rows SET status = 'needs_review' WHERE id = ?", (row["id"],))

                conn.execute(
                    "UPDATE import_rows SET resolved_refs = ?, issues = ? WHERE id = ?",
                    (json.dumps(resolved_refs) if resolved_refs else None, json.dumps(issues), row["id"]),
                )

            # Also check for duplicates within the import itself (exclude user-approved rows)
            active_rows = [r for r in rows if not (json.loads(r["resolved_refs"]) if r["resolved_refs"] else {}).get("user_approved")]
            self._resolve_internal_duplicates(conn=conn, job_id=job_id, schema=schema, rows=active_rows)

            conn.commit()

    def _resolve_internal_duplicates(self, *, conn, job_id: str, schema: dict, rows: list[dict]) -> None:
        """Check for duplicates among the imported rows themselves."""
        for i, row_a in enumerate(rows):
            mapped_a = json.loads(row_a["mapped_data"]) if row_a["mapped_data"] else {}
            for row_b in rows[i + 1:]:
                mapped_b = json.loads(row_b["mapped_data"]) if row_b["mapped_data"] else {}

                confidence = 0.0
                for key in schema["dedup_keys"]:
                    if mapped_a.get(key) and mapped_b.get(key):
                        if str(mapped_a[key]).lower().strip() == str(mapped_b[key]).lower().strip():
                            confidence = 1.0
                            break

                if confidence < 1.0:
                    scores = []
                    for key in schema["fuzzy_keys"]:
                        a = str(mapped_a.get(key, "")).lower().strip()
                        b = str(mapped_b.get(key, "")).lower().strip()
                        if a and b:
                            scores.append(difflib.SequenceMatcher(None, a, b).ratio())
                    if scores:
                        confidence = max(confidence, sum(scores) / len(scores))

                if confidence >= 0.6:
                    # Flag the later row
                    issues_b = json.loads(row_b.get("issues") or "[]")
                    # Avoid adding duplicate issues
                    already_flagged = any(
                        iss.get("issue_type") == "possible_duplicate" and iss.get("field") == "_internal"
                        for iss in issues_b
                    )
                    if not already_flagged:
                        issues_b.append({
                            "severity": "warning",
                            "field": "_internal",
                            "message": f"Possible duplicate of row {row_a.get('source_row', '?')} ({mapped_a.get('name', '') or mapped_a.get('company', '')}) — confidence {confidence:.0%}",
                            "issue_type": "possible_duplicate",
                            "duplicate_row": row_a.get("source_row"),
                        })
                        conn.execute(
                            "UPDATE import_rows SET issues = ?, status = 'needs_review' WHERE id = ?",
                            (json.dumps(issues_b), row_b["id"]),
                        )

    # ------------------------------------------------------------------
    # Group issues into batch questions
    # ------------------------------------------------------------------

    def _group_issues(self, *, job_id: str) -> list[dict]:
        """Group similar issues across rows into batch questions."""
        with db_conn() as conn:
            rows = dict_rows(conn.execute(
                "SELECT source_row, issues, status FROM import_rows WHERE job_id = ? AND status NOT IN ('merged', 'rejected', 'imported') ORDER BY source_row",
                (job_id,),
            ).fetchall())

        groups: dict[str, dict] = {}
        for row in rows:
            issues = json.loads(row["issues"]) if row["issues"] else []
            for iss in issues:
                if iss.get("auto_fixed"):
                    continue
                if iss["severity"] not in ("error", "warning"):
                    continue
                issue_type = iss.get("issue_type", iss.get("field", "unknown"))
                key = f"{issue_type}:{iss.get('message', '')[:50]}"
                if key not in groups:
                    groups[key] = {
                        "issue_type": issue_type,
                        "message": iss["message"],
                        "rows": [],
                        "severity": iss["severity"],
                    }
                groups[key]["rows"].append(row["source_row"])

        batch_questions = []
        for group in groups.values():
            row_list = ", ".join(str(r) for r in group["rows"])
            issue_type = group["issue_type"]
            msg = group["message"]
            severity = group["severity"]

            if issue_type == "existing_duplicate":
                n = len(group["rows"])
                question = f"{n} row{'s' if n > 1 else ''} (rows {row_list}) already exist{'s' if n == 1 else ''} in the database. {msg}"
                suggestion = "skip"
            elif issue_type == "possible_duplicate":
                question = f"Rows {row_list} may be duplicates ({msg}). Merge or keep both?"
                suggestion = "merge"
            elif severity == "error" and "required field" in msg.lower():
                # Extract the field name from message like "Required field 'name' is missing"
                field = msg.split("'")[1] if "'" in msg else "field"
                n = len(group["rows"])
                question = f"{n} row{'s' if n > 1 else ''} (rows {row_list}) {'are' if n > 1 else 'is'} missing required field '{field}'."
                suggestion = f"set {field} from another column, or type a value"
            elif "not a valid" in msg.lower() or "does not look like" in msg.lower():
                n = len(group["rows"])
                question = f"{n} row{'s' if n > 1 else ''} (rows {row_list}): {msg}"
                suggestion = "fix the value, or leave blank to skip validation"
            elif "not an integer" in msg.lower():
                n = len(group["rows"])
                question = f"{n} row{'s' if n > 1 else ''} (rows {row_list}): {msg}"
                suggestion = "extract the number, or set to 0"
            else:
                question = f"Rows {row_list}: {msg}"
                suggestion = "review"

            batch_questions.append({
                "description": question,
                "issue_type": issue_type,
                "affected_rows": group["rows"],
                "suggestion": suggestion,
            })

        return batch_questions

    # ------------------------------------------------------------------
    # Sample selection
    # ------------------------------------------------------------------

    def _select_sample_indices(self, rows: list[dict], columns: list[str]) -> list[int]:
        """Pick up to 5 sample row indices (always the first 5)."""
        return list(range(min(5, len(rows))))

    # ------------------------------------------------------------------
    # Transform sample rows only (for preview)
    # ------------------------------------------------------------------

    def _transform_sample_rows(self, *, rows: list[dict], mapping: list[dict], entity_type: str, global_instructions: str = "") -> list[dict]:
        """Apply mapping + transforms to a list of raw row dicts (in memory, no DB writes).
        Returns list of {raw_data, mapped_data} dicts."""
        results = []
        llm_batch = []

        for idx, raw in enumerate(rows):
            mapped = {}
            for m in mapping:
                if m.get("target") is None:
                    continue
                source_val = raw.get(m["source"], "")
                transform = m.get("transform", "none")
                py_result = self._python_transform(transform, source_val)
                if py_result is not None:
                    mapped[m["target"]] = py_result
                else:
                    llm_batch.append({
                        "idx": idx,
                        "source_column": m["source"],
                        "target_field": m["target"],
                        "transform": transform,
                        "raw_value": source_val,
                    })
                    mapped[m["target"]] = source_val  # placeholder
            results.append({"raw_data": raw, "mapped_data": mapped})

        # LLM batch for sample transforms
        if llm_batch:
            try:
                prompt = (
                    "You are a data transformation expert. Transform the following raw values "
                    "for import into an ERP system.\n\n"
                )
                if global_instructions:
                    prompt += f"Global instructions from user: {global_instructions}\n\n"
                prompt += (
                    f"Transforms to apply:\n{json.dumps(llm_batch, indent=2)}\n\n"
                    "Respond with ONLY a JSON array, one object per input entry:\n"
                    '[{"idx": 0, "source_column": "...", "value": ..., "notes": "..."}]'
                )
                resp = chat_completion(
                    model=config.DATA_IMPORT_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = resp.choices[0].message.content.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                llm_results = json.loads(text)
                for r in llm_results:
                    idx = r["idx"]
                    target_field = next(
                        (b["target_field"] for b in llm_batch
                         if b["idx"] == idx and b["source_column"] == r["source_column"]),
                        None,
                    )
                    if target_field and idx < len(results):
                        results[idx]["mapped_data"][target_field] = r["value"]
            except Exception:
                logger.warning("LLM sample transform failed, using raw values", exc_info=True)

        return results

    # ------------------------------------------------------------------
    # Build mapping state (Phase 1)
    # ------------------------------------------------------------------

    def _build_mapping_state(self, job_id: str) -> dict:
        """Assemble the Phase 1 JSON state (mapping review)."""
        with db_conn() as conn:
            job = conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
            if not job:
                raise ValueError(f"Import job not found: {job_id}")
            job = dict(job)

            # Get sample rows
            sample_indices = json.loads(job["sample_indices"]) if job.get("sample_indices") else []
            rows = dict_rows(conn.execute(
                "SELECT source_row, raw_data FROM import_rows WHERE job_id = ? ORDER BY source_row",
                (job_id,),
            ).fetchall())

        mapping = json.loads(job["mapping_plan"]) if job.get("mapping_plan") else []
        columns = json.loads(job["columns_detected"]) if job.get("columns_detected") else []
        entity_type = job.get("entity_type", "customer")

        # Get sample raw data based on indices (indices are 0-based into the row list)
        sample_raw = []
        for i in sample_indices:
            if i < len(rows):
                sample_raw.append(json.loads(rows[i]["raw_data"]) if isinstance(rows[i]["raw_data"], str) else rows[i]["raw_data"])

        # Transform sample rows
        sample_rows = self._transform_sample_rows(rows=sample_raw, mapping=mapping, entity_type=entity_type)

        # Build target_fields from entity schema
        schema = ENTITY_SCHEMAS.get(entity_type, {})
        target_fields = [
            {"name": name, **defn}
            for name, defn in schema.get("fields", {}).items()
        ]

        # Extract entity_confidence from issues_summary (where upload stores it)
        entity_confidence = 0.0
        if job.get("issues_summary"):
            try:
                summary_data = json.loads(job["issues_summary"])
                entity_confidence = summary_data.get("entity_confidence", 0.0)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "job_id": job_id,
            "entity_type": entity_type,
            "entity_confidence": entity_confidence,
            "source_filename": job.get("source_filename"),
            "row_count": job.get("row_count", 0),
            "columns_detected": columns,
            "mapping": mapping,
            "sample_rows": sample_rows,
            "target_fields": target_fields,
            "global_instructions": job.get("global_instructions") or "",
            "status": job["status"],
        }

    # ------------------------------------------------------------------
    # Build staging state (Phase 2)
    # ------------------------------------------------------------------

    def _build_staging_state(self, job_id: str) -> dict:
        """Assemble the full JSON state the MCP app renders from."""
        with db_conn() as conn:
            job = conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
            if not job:
                raise ValueError(f"Import job not found: {job_id}")
            job = dict(job)

            rows = dict_rows(conn.execute(
                "SELECT * FROM import_rows WHERE job_id = ? ORDER BY source_row",
                (job_id,),
            ).fetchall())

        # Parse JSON fields
        for row in rows:
            row["raw_data"] = json.loads(row["raw_data"]) if row["raw_data"] else {}
            row["mapped_data"] = json.loads(row["mapped_data"]) if row["mapped_data"] else {}
            row["resolved_refs"] = json.loads(row["resolved_refs"]) if row["resolved_refs"] else {}
            row["issues"] = json.loads(row["issues"]) if row["issues"] else []

        mapping = json.loads(job["mapping_plan"]) if job.get("mapping_plan") else None
        columns = json.loads(job["columns_detected"]) if job.get("columns_detected") else []

        # Compute issues_summary live from current row statuses
        issues_summary: dict[str, int] = {}
        for row in rows:
            s = row.get("status", "unknown")
            issues_summary[s] = issues_summary.get(s, 0) + 1

        batch_questions = self._group_issues(job_id=job_id) if job["status"] == "validated" else []

        # Build target_fields from entity schema
        entity_type = job.get("entity_type") or ""
        schema = ENTITY_SCHEMAS.get(entity_type, {})
        target_fields = [
            {"name": name, **defn}
            for name, defn in schema.get("fields", {}).items()
        ]

        return {
            "job_id": job_id,
            "entity_type": entity_type or None,
            "source_filename": job.get("source_filename"),
            "source_format": job.get("source_format"),
            "status": job["status"],
            "row_count": job.get("row_count", 0),
            "columns_detected": columns,
            "mapping": mapping,
            "global_instructions": job.get("global_instructions") or "",
            "issues_summary": issues_summary,
            "batch_questions": batch_questions,
            "target_fields": target_fields,
            "rows": rows,
        }

    # ------------------------------------------------------------------
    # Core: upload (Phase 1 — returns mapping state)
    # ------------------------------------------------------------------

    def upload(self, *, source: str, hint: str | None = None) -> dict:
        """Parse file, detect entity, map columns, select samples, transform sample rows.

        Returns mapping state for Phase 1 review (not full staging state).
        """
        try:
            content, filename = self._read_source(source)
        except (FileNotFoundError, ValueError) as exc:
            return {"error": str(exc)}

        try:
            rows, format_info = self._parse_file(content, filename)
        except (ValueError, csv.Error) as exc:
            return {"error": f"Failed to parse file: {exc}"}

        with db_conn() as conn:
            job_id = generate_id(conn, "IMP", "import_jobs")
            now = _sim_now(conn)

            columns = list(rows[0].keys()) if rows else []

            conn.execute(
                "INSERT INTO import_jobs (id, source_filename, source_format, source_content, hint, status, row_count, columns_detected, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, filename, format_info, content.decode("utf-8", errors="replace"),
                 hint, "mapping_review", len(rows), json.dumps(columns), now),
            )

            for i, row in enumerate(rows, 1):
                row_id = f"{job_id}-R{i:02d}"
                conn.execute(
                    "INSERT INTO import_rows (id, job_id, source_row, raw_data, status) VALUES (?, ?, ?, ?, ?)",
                    (row_id, job_id, i, json.dumps(row, default=str), "pending"),
                )

            conn.commit()

        # Skip LLM for empty files
        if not rows:
            with db_conn() as conn:
                conn.execute("UPDATE import_jobs SET status = 'validated', sample_indices = '[]' WHERE id = ?", (job_id,))
                conn.commit()
            return self._build_staging_state(job_id)

        # LLM: detect entity type
        sample_rows = rows[:3]
        detection = self._detect_entity(columns, sample_rows)
        entity_type = detection.get("entity_type", "customer")
        entity_confidence = detection.get("confidence", 0.0)

        with db_conn() as conn:
            conn.execute("UPDATE import_jobs SET entity_type = ? WHERE id = ?", (entity_type, job_id))
            conn.commit()

        # LLM: generate column mapping
        mapping = self._generate_mapping(columns, sample_rows, entity_type)

        # Select sample indices
        sample_indices = self._select_sample_indices(rows, columns)

        with db_conn() as conn:
            conn.execute(
                "UPDATE import_jobs SET mapping_plan = ?, sample_indices = ? WHERE id = ?",
                (json.dumps(mapping), json.dumps(sample_indices), job_id),
            )
            conn.commit()

        # Store entity_confidence for mapping state
        with db_conn() as conn:
            # Store confidence in the entity_type detection for the mapping state
            # (We piggyback on the job record — _build_mapping_state reads it)
            conn.execute(
                "UPDATE import_jobs SET issues_summary = ? WHERE id = ?",
                (json.dumps({"entity_confidence": entity_confidence}), job_id),
            )
            conn.commit()

        return self._build_mapping_state(job_id)

    # ------------------------------------------------------------------
    # Core: preview_sample
    # ------------------------------------------------------------------

    def preview_sample(self, *, job_id: str, mapping: list[dict], global_instructions: str = "") -> dict:
        """Re-transform sample rows with an updated mapping. Returns sample preview."""
        with db_conn() as conn:
            job = conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
            if not job:
                raise ValueError(f"Import job not found: {job_id}")
            job = dict(job)

            sample_indices = json.loads(job["sample_indices"]) if job.get("sample_indices") else []
            entity_type = job.get("entity_type", "customer")

            rows = dict_rows(conn.execute(
                "SELECT source_row, raw_data FROM import_rows WHERE job_id = ? ORDER BY source_row",
                (job_id,),
            ).fetchall())

        # Get sample raw data
        sample_raw = []
        for i in sample_indices:
            if i < len(rows):
                sample_raw.append(json.loads(rows[i]["raw_data"]) if isinstance(rows[i]["raw_data"], str) else rows[i]["raw_data"])

        # Transform sample rows with the updated mapping
        sample_rows = self._transform_sample_rows(rows=sample_raw, mapping=mapping, entity_type=entity_type, global_instructions=global_instructions)

        return {
            "job_id": job_id,
            "sample_rows": sample_rows,
        }

    # ------------------------------------------------------------------
    # Core: confirm_mapping (end of Phase 1 — persist only)
    # ------------------------------------------------------------------

    def confirm_mapping(self, *, job_id: str, mapping: list[dict], global_instructions: str = "") -> dict:
        """Persist final mapping + instructions. No heavy processing here.

        Sets status to 'mapped'. The Phase 2 app will call start_processing()
        on mount to kick off the full transform/validate/resolve pipeline.
        """
        with db_conn() as conn:
            job = conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
            if not job:
                raise ValueError(f"Import job not found: {job_id}")
            row_count = dict(job).get("row_count", 0)

            conn.execute(
                "UPDATE import_jobs SET mapping_plan = ?, global_instructions = ?, status = 'mapped' WHERE id = ?",
                (json.dumps(mapping), global_instructions, job_id),
            )
            conn.commit()

        return {
            "job_id": job_id,
            "status": "mapped",
            "row_count": row_count,
        }

    # ------------------------------------------------------------------
    # Core: start_processing (beginning of Phase 2 — full pipeline)
    # ------------------------------------------------------------------

    def start_processing(self, *, job_id: str) -> dict:
        """Kick off the heavy pipeline (transforms, validation, resolution).

        Called by the Phase 2 app on mount. Transitions status from 'mapped'
        to 'processing' and runs the pipeline in a background thread.
        The Phase 2 app polls get_state() until status becomes 'validated'.
        """
        with db_conn() as conn:
            job = conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
            if not job:
                raise ValueError(f"Import job not found: {job_id}")
            job = dict(job)

            if job["status"] != "mapped":
                # Already processing or validated — return full state
                return self._build_staging_state(job_id)

            row_count = job.get("row_count", 0)
            mapping = json.loads(job["mapping_plan"]) if job.get("mapping_plan") else []

            conn.execute(
                "UPDATE import_jobs SET status = 'processing' WHERE id = ?",
                (job_id,),
            )
            conn.commit()

        # Run the heavy pipeline in a background thread
        thread = threading.Thread(
            target=self._run_processing_pipeline,
            args=(job_id, mapping),
            daemon=True,
        )
        thread.start()

        return {
            "job_id": job_id,
            "status": "processing",
            "row_count": row_count,
        }

    def _run_processing_pipeline(self, job_id: str, mapping: list[dict]) -> None:
        """Background processing: transforms → validate → resolve → mark validated."""
        try:
            self._apply_transforms(job_id=job_id, mapping=mapping)
            self._validate_rows(job_id=job_id)
            self._resolve_entities(job_id=job_id)

            with db_conn() as conn:
                row_stats = dict_rows(conn.execute(
                    "SELECT status, COUNT(*) as cnt FROM import_rows WHERE job_id = ? GROUP BY status",
                    (job_id,),
                ).fetchall())
                summary = {r["status"]: r["cnt"] for r in row_stats}

                conn.execute(
                    "UPDATE import_jobs SET status = 'validated', issues_summary = ? WHERE id = ?",
                    (json.dumps(summary), job_id),
                )
                conn.commit()
        except Exception:
            logger.error("processing pipeline failed for %s", job_id, exc_info=True)
            with db_conn() as conn:
                conn.execute(
                    "UPDATE import_jobs SET status = 'validated', issues_summary = ? WHERE id = ?",
                    (json.dumps({"error": "processing failed"}), job_id),
                )
                conn.commit()

    # ------------------------------------------------------------------
    # Core: get_state
    # ------------------------------------------------------------------

    def get_state(self, job_id: str) -> dict:
        """Read job + rows from DB, build staging state dict."""
        return self._build_staging_state(job_id)

    def get_active_job_id(self) -> str | None:
        """Return the ID of the most recent import job in 'mapped' or 'processing' state."""
        with db_conn() as conn:
            row = conn.execute(
                "SELECT id FROM import_jobs WHERE status IN ('mapped', 'processing', 'validated') "
                "ORDER BY id DESC LIMIT 1",
            ).fetchone()
        return row[0] if row else None

    # ------------------------------------------------------------------
    # Core: set_cell (direct cell edit — no LLM)
    # ------------------------------------------------------------------

    def set_cell(self, *, job_id: str, source_row: int, field: str, value) -> dict:
        """Directly set a single cell value in a row's mapped_data."""
        with db_conn() as conn:
            row = conn.execute(
                "SELECT id, mapped_data FROM import_rows WHERE job_id = ? AND source_row = ?",
                (job_id, source_row),
            ).fetchone()
            if not row:
                raise ValueError(f"Row {source_row} not found in job {job_id}")
            row = dict(row)
            mapped = json.loads(row["mapped_data"]) if row["mapped_data"] else {}
            mapped[field] = value
            conn.execute(
                "UPDATE import_rows SET mapped_data = ? WHERE id = ?",
                (json.dumps(mapped), row["id"]),
            )
            conn.commit()
        return {"ok": True, "source_row": source_row, "field": field, "value": value}

    # ------------------------------------------------------------------
    # Core: fix
    # ------------------------------------------------------------------

    def fix(self, *, job_id: str, instruction: str) -> dict:
        """Interpret a free-text fix instruction and apply it."""
        # Simple deterministic instructions
        lower = instruction.strip().lower()
        if lower in ("reject", "reject all"):
            with db_conn() as conn:
                conn.execute(
                    "UPDATE import_rows SET status = 'rejected' WHERE job_id = ? AND status NOT IN ('merged', 'imported')",
                    (job_id,),
                )
                conn.commit()
            return self._build_staging_state(job_id)

        if lower in ("keep", "keep all", "keep both"):
            with db_conn() as conn:
                conn.execute(
                    "UPDATE import_rows SET status = 'ready' WHERE job_id = ? AND status = 'needs_review'",
                    (job_id,),
                )
                conn.commit()
            return self._build_staging_state(job_id)

        # LLM interpretation
        state = self._build_staging_state(job_id)
        batch_questions = state.get("batch_questions", [])
        current_question = batch_questions[0] if batch_questions else None
        global_instructions = state.get("global_instructions", "")

        prompt = (
            "You are a data import assistant. The user is reviewing staged import data "
            "and has given an instruction to fix issues.\n\n"
        )
        if global_instructions:
            prompt += f"Global instructions from user: {global_instructions}\n\n"
        prompt += f"Current staging state:\n{json.dumps(state, indent=2, default=str)}\n\n"
        if current_question:
            prompt += f"Current batch question: {json.dumps(current_question)}\n\n"
        prompt += (
            f"User instruction: {instruction}\n\n"
            "Based on the instruction, determine what changes to make to the staging data.\n"
            "Respond with ONLY a JSON object:\n"
            '{\n  "actions": [\n'
            '    {"type": "merge", "rows": [1, 4], "merged_values": {"field": "value", ...}},\n'
            '    {"type": "set_value", "row": 2, "field": "name", "value": "NewName"},\n'
            '    {"type": "reject", "rows": [5]},\n'
            '    {"type": "keep", "rows": [3]}\n'
            '  ],\n  "reasoning": "brief explanation"\n}'
        )

        resp = chat_completion(
            model=config.DATA_IMPORT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("LLM returned unparseable JSON for fix instruction: %s", text)
            return self._build_staging_state(job_id)

        actions = result.get("actions", [])
        self._apply_fix_actions(job_id=job_id, actions=actions)

        # Re-validate and re-detect duplicates
        self._validate_rows(job_id=job_id)
        self._resolve_entities(job_id=job_id)

        return self._build_staging_state(job_id)

    def _apply_fix_actions(self, *, job_id: str, actions: list[dict]) -> None:
        """Apply a list of fix actions to staging data."""
        with db_conn() as conn:
            for action in actions:
                atype = action.get("type")

                if atype == "merge":
                    self._merge_rows(conn=conn, job_id=job_id, action=action)

                elif atype == "set_value":
                    row_num = action["row"]
                    row = conn.execute(
                        "SELECT id, mapped_data FROM import_rows WHERE job_id = ? AND source_row = ?",
                        (job_id, row_num),
                    ).fetchone()
                    if row:
                        mapped = json.loads(row[1]) if row[1] else {}
                        mapped[action["field"]] = action["value"]
                        conn.execute(
                            "UPDATE import_rows SET mapped_data = ? WHERE id = ?",
                            (json.dumps(mapped, default=str), row[0]),
                        )

                elif atype == "reject":
                    for row_num in action.get("rows", []):
                        row = conn.execute(
                            "SELECT id, resolved_refs FROM import_rows WHERE job_id = ? AND source_row = ?",
                            (job_id, row_num),
                        ).fetchone()
                        if row:
                            refs = json.loads(row[1]) if row[1] else {}
                            refs["user_rejected"] = True
                            conn.execute(
                                "UPDATE import_rows SET status = 'rejected', resolved_refs = ?, issues = '[]' WHERE id = ?",
                                (json.dumps(refs), row[0]),
                            )

                elif atype == "keep":
                    for row_num in action.get("rows", []):
                        # Mark as user-approved so entity resolution won't re-flag
                        row = conn.execute(
                            "SELECT id, resolved_refs FROM import_rows WHERE job_id = ? AND source_row = ?",
                            (job_id, row_num),
                        ).fetchone()
                        if row:
                            refs = json.loads(row[1]) if row[1] else {}
                            refs["user_approved"] = True
                            conn.execute(
                                "UPDATE import_rows SET status = 'ready', resolved_refs = ?, issues = '[]' WHERE id = ?",
                                (json.dumps(refs), row[0]),
                            )

            conn.commit()

    def _merge_rows(self, *, conn, job_id: str, action: dict) -> None:
        """Merge multiple rows into one."""
        row_nums = action.get("rows", [])
        merged_values = action.get("merged_values", {})

        rows = dict_rows(conn.execute(
            "SELECT id, source_row, mapped_data FROM import_rows WHERE job_id = ? AND source_row IN ({}) ORDER BY source_row".format(
                ",".join("?" for _ in row_nums)
            ),
            [job_id] + row_nums,
        ).fetchall())

        if len(rows) < 2:
            return

        # Primary row is the first one
        primary = rows[0]
        primary_mapped = json.loads(primary["mapped_data"]) if primary["mapped_data"] else {}
        primary_mapped.update(merged_values)

        conn.execute(
            "UPDATE import_rows SET mapped_data = ?, status = 'ready', issues = '[]' WHERE id = ?",
            (json.dumps(primary_mapped, default=str), primary["id"]),
        )

        # Mark absorbed rows
        for absorbed in rows[1:]:
            conn.execute(
                "UPDATE import_rows SET status = 'merged', merged_into = ? WHERE id = ?",
                (primary["id"], absorbed["id"]),
            )

    # ------------------------------------------------------------------
    # Core: execute
    # ------------------------------------------------------------------

    def execute(self, *, job_id: str, exclude_columns: list[str] | None = None) -> dict:
        """Execute import — create records via service layer."""
        from services.customer import create_customer
        from services.activity import log_activity
        excluded = set(exclude_columns) if exclude_columns else set()

        with db_conn() as conn:
            job = dict(conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone())

            if job["status"] not in ("validated", "ready_to_execute"):
                raise ValueError(f"Cannot execute job in status '{job['status']}'")

            entity_type = job["entity_type"]
            rows = dict_rows(conn.execute(
                "SELECT * FROM import_rows WHERE job_id = ? AND status IN ('ready', 'needs_review', 'auto_fixed') ORDER BY source_row",
                (job_id,),
            ).fetchall())

        created = []
        for row in rows:
            mapped = json.loads(row["mapped_data"]) if row["mapped_data"] else {}

            if entity_type == "customer":
                # Filter to valid create_customer kwargs
                valid_keys = {
                    "name", "gender", "company", "email", "phone", "address_line1",
                    "address_line2", "city", "postal_code", "country",
                    "tax_id", "payment_terms", "currency", "notes",
                }
                kwargs = {k: v for k, v in mapped.items() if k in valid_keys and k not in excluded and v is not None and v != ""}
                if "name" not in kwargs:
                    kwargs["name"] = mapped.get("company", "Unknown")

                result = create_customer(**kwargs)
                entity_id = result["customer_id"]

                with db_conn() as conn:
                    conn.execute(
                        "UPDATE import_rows SET status = 'imported', created_entity_type = ?, created_entity_id = ? WHERE id = ?",
                        ("customer", entity_id, row["id"]),
                    )
                    conn.commit()

                created.append({"row": row["source_row"], "entity_type": "customer", "entity_id": entity_id})

        # Update job
        with db_conn() as conn:
            now = _sim_now(conn)
            conn.execute(
                "UPDATE import_jobs SET status = 'executed', executed_at = ? WHERE id = ?",
                (now, job_id),
            )
            conn.commit()

        log_activity(
            actor="mcp:data_import",
            category="data_import",
            action="import.executed",
            entity_type="import_job",
            entity_id=job_id,
            details={"created_count": len(created), "entity_type": entity_type},
        )

        state = self._build_staging_state(job_id)
        state["created"] = created
        return state

    # ------------------------------------------------------------------
    # Core: rollback
    # ------------------------------------------------------------------

    def rollback(self, *, job_id: str) -> dict:
        """Undo an executed import by deleting created records."""
        from services.activity import log_activity

        with db_conn() as conn:
            job = dict(conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone())

            if job["status"] != "executed":
                raise ValueError(f"Cannot rollback job in status '{job['status']}'")

            entity_type = job["entity_type"]
            schema = ENTITY_SCHEMAS.get(entity_type)

            rows = dict_rows(conn.execute(
                "SELECT * FROM import_rows WHERE job_id = ? AND status = 'imported' AND created_entity_id IS NOT NULL",
                (job_id,),
            ).fetchall())

            for row in rows:
                if schema:
                    conn.execute(
                        f"DELETE FROM {schema['table']} WHERE id = ?",
                        (row["created_entity_id"],),
                    )
                conn.execute(
                    "UPDATE import_rows SET status = 'ready', created_entity_id = NULL, created_entity_type = NULL WHERE id = ?",
                    (row["id"],),
                )

            conn.execute("UPDATE import_jobs SET status = 'rolled_back' WHERE id = ?", (job_id,))
            conn.commit()

        log_activity(
            actor="mcp:data_import",
            category="data_import",
            action="import.rolled_back",
            entity_type="import_job",
            entity_id=job_id,
        )

        return self._build_staging_state(job_id)


data_import_service = DataImportService()
