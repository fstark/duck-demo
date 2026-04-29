"""Service for Quality Control operations.

Manages the full QC lifecycle:
  hold batch creation → image attachment → AI inspection → disposition → replacement.
"""

import base64
import json
import logging
import math
from typing import Any

import config
from db import dict_rows, generate_id
from services._base import db_conn

logger = logging.getLogger("duck-demo")

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

INSPECTION_STATUS_VALUES = frozenset({
    "none",
    "pending_inspection",
    "inspected",
    "partially_released",
    "released",
})

HOLD_BATCH_STATUS_VALUES = frozenset({
    "pending_images",
    "ready_for_inspection",
    "inspected",
    "released",
    "partially_released",
    "closed",
})

HOLD_LINE_STATUS_VALUES = frozenset({
    "pending_inspection",
    "released",
    "partially_released",
    "scrapped",
})

DISPOSITION_ACTIONS = frozenset({"pass_release", "partial_scrap", "full_scrap"})

FINDING_TYPES = frozenset({
    "wrong_product", "paint_defect", "shape_defect",
    "assembly_defect", "packaging_defect", "missing_part",
})

FINDING_SEVERITIES = frozenset({"critical", "major", "minor"})

INFERENCE_DECISIONS = frozenset({"pass", "partial_scrap", "full_scrap"})

# Allowed inspection_status transitions keyed by action/event
_INSPECTION_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "complete_with_hold": ["none"],
    "attach_images": ["pending_inspection"],
    "run_inspection": ["pending_inspection"],
    "apply_disposition_pass": ["inspected"],
    "apply_disposition_partial": ["inspected"],
    "apply_disposition_full": ["inspected"],
}

ID_PREFIXES = {
    "qc_hold_batches": "QCB",
    "qc_hold_batch_lines": "QCBL",
    "qc_hold_images": "QCIMG",
    "qc_inspections": "QCI",
    "qc_inspection_findings": "QCIF",
    "qc_dispositions": "QCD",
    "qc_replacements": "QCRPL",
}


def _assert_invariant(line: dict) -> None:
    """Assert qty_released + qty_scrapped + qty_pending == qty_on_hold."""
    total = line["qty_released"] + line["qty_scrapped"] + line["qty_pending"]
    assert total == line["qty_on_hold"], (
        f"QC quantity invariant violated on line {line['id']}: "
        f"released={line['qty_released']} + scrapped={line['qty_scrapped']} "
        f"+ pending={line['qty_pending']} = {total} != on_hold={line['qty_on_hold']}"
    )


def _validate_transition(*, current_status: str, event: str, entity: str = "production order") -> None:
    """Validate an inspection_status transition, raising ValueError on invalid."""
    allowed = _INSPECTION_STATUS_TRANSITIONS.get(event, [])
    if current_status not in allowed:
        raise ValueError(
            f"Cannot apply '{event}' to {entity} with inspection_status='{current_status}'. "
            f"Expected one of: {allowed}"
        )


class QcService:
    """QC domain service — hold, inspect, dispose, replace."""

    # ------------------------------------------------------------------
    # Hold batch creation (called by production service at completion)
    # ------------------------------------------------------------------

    def create_hold_batch(
        self,
        *,
        conn,
        production_order_id: str,
        sales_order_id: str | None,
        item_id: str,
        qty_produced: int,
        sim_time: str,
    ) -> dict[str, Any]:
        """Create a QC hold batch + line for an inspection-required MO.

        Must be called within an existing db_conn() block (conn is provided).
        Does NOT commit; the caller's transaction owns the commit.
        """
        batch_id = generate_id(conn, ID_PREFIXES["qc_hold_batches"], "qc_hold_batches")
        conn.execute(
            "INSERT INTO qc_hold_batches "
            "(id, production_order_id, sales_order_id, item_id, status, created_at, replacement_triggered) "
            "VALUES (?, ?, ?, ?, ?, ?, 0)",
            (batch_id, production_order_id, sales_order_id, item_id, "pending_images", sim_time),
        )
        line_id = generate_id(conn, ID_PREFIXES["qc_hold_batch_lines"], "qc_hold_batch_lines")
        conn.execute(
            "INSERT INTO qc_hold_batch_lines "
            "(id, qc_hold_batch_id, item_id, qty_on_hold, qty_pending, qty_released, qty_scrapped, line_status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 0, 0, 'pending_inspection', ?)",
            (line_id, batch_id, item_id, qty_produced, qty_produced, sim_time),
        )
        conn.execute(
            "UPDATE production_orders SET inspection_status = 'pending_inspection' WHERE id = ?",
            (production_order_id,),
        )
        return {"qc_hold_batch_id": batch_id, "qc_hold_batch_line_id": line_id}

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def list_pending_batches(self, *, status: str = "pending_images") -> list[dict]:
        with db_conn() as conn:
            rows = dict_rows(conn.execute(
                """
                SELECT b.*, i.sku as item_sku, i.name as item_name,
                       COALESCE(l.qty_pending, 0) as qty_pending,
                       COALESCE(l.qty_released, 0) as qty_released,
                       COALESCE(l.qty_scrapped, 0) as qty_scrapped
                FROM qc_hold_batches b
                JOIN items i ON b.item_id = i.id
                LEFT JOIN qc_hold_batch_lines l ON l.qc_hold_batch_id = b.id
                WHERE b.status = ?
                ORDER BY b.created_at ASC
                """,
                (status,),
            ))
        return rows

    def get_batch(self, *, batch_id: str) -> dict[str, Any]:
        with db_conn() as conn:
            batch = conn.execute(
                """
                SELECT b.*, i.sku as item_sku, i.name as item_name
                FROM qc_hold_batches b
                JOIN items i ON b.item_id = i.id
                WHERE b.id = ?
                """,
                (batch_id,),
            ).fetchone()
            if not batch:
                raise ValueError(f"QC hold batch {batch_id} not found")
            result = dict(batch)
            result["lines"] = dict_rows(conn.execute(
                "SELECT * FROM qc_hold_batch_lines WHERE qc_hold_batch_id = ?",
                (batch_id,),
            ))
            result["images"] = dict_rows(conn.execute(
                "SELECT * FROM qc_hold_images WHERE qc_hold_batch_id = ? ORDER BY created_at",
                (batch_id,),
            ))
            inspection = conn.execute(
                "SELECT * FROM qc_inspections WHERE qc_hold_batch_id = ? AND status != 'failed' ORDER BY created_at DESC LIMIT 1",
                (batch_id,),
            ).fetchone()
            if inspection:
                insp_dict = dict(inspection)
                insp_dict["findings"] = dict_rows(conn.execute(
                    "SELECT * FROM qc_inspection_findings WHERE qc_inspection_id = ?",
                    (insp_dict["id"],),
                ))
                result["inspection"] = insp_dict
            else:
                result["inspection"] = None
            replacements = dict_rows(conn.execute(
                "SELECT r.* FROM qc_replacements r "
                "JOIN qc_dispositions d ON r.qc_disposition_id = d.id "
                "WHERE d.qc_hold_batch_id = ?",
                (batch_id,),
            ))
            result["replacements"] = replacements
        return result

    def get_inspection(self, *, inspection_id: str) -> dict[str, Any]:
        with db_conn() as conn:
            insp = conn.execute(
                "SELECT * FROM qc_inspections WHERE id = ?",
                (inspection_id,),
            ).fetchone()
            if not insp:
                raise ValueError(f"QC inspection {inspection_id} not found")
            result = dict(insp)
            result["findings"] = dict_rows(conn.execute(
                "SELECT * FROM qc_inspection_findings WHERE qc_inspection_id = ? ORDER BY created_at",
                (inspection_id,),
            ))
        return result

    # ------------------------------------------------------------------
    # Image attachment
    # ------------------------------------------------------------------

    def attach_images(
        self,
        *,
        batch_id: str,
        image_urls: list[str],
        uploaded_by: str | None = None,
    ) -> dict[str, Any]:
        """Attach evidence image URLs to a hold batch."""
        with db_conn() as conn:
            batch = conn.execute(
                "SELECT * FROM qc_hold_batches WHERE id = ?",
                (batch_id,),
            ).fetchone()
            if not batch:
                raise ValueError(f"QC hold batch {batch_id} not found")
            from services.simulation import simulation_service
            sim_time = simulation_service.get_current_time()
            for url in image_urls:
                img_id = generate_id(conn, ID_PREFIXES["qc_hold_images"], "qc_hold_images")
                conn.execute(
                    "INSERT INTO qc_hold_images (id, qc_hold_batch_id, image_url, created_at, uploaded_by) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (img_id, batch_id, url, sim_time, uploaded_by),
                )
            conn.execute(
                "UPDATE qc_hold_batches SET status = 'ready_for_inspection' WHERE id = ?",
                (batch_id,),
            )
            conn.commit()

        # Auto-run the AI inspection immediately after attaching images
        return self.run_inspection(batch_id=batch_id)

    # ------------------------------------------------------------------
    # AI Inspection
    # ------------------------------------------------------------------

    def run_inspection(self, *, batch_id: str) -> dict[str, Any]:
        """Run AI image inspection for a hold batch.

        Two-phase INSERT: inserts the inspection row first with status='pending',
        then calls the inference API, then updates to 'completed' or 'failed'.
        Idempotent: returns existing completed inspection; deletes failed and retries.
        """
        from services import myforterro
        from services.simulation import simulation_service

        with db_conn() as conn:
            batch = conn.execute(
                "SELECT b.*, po.item_id "
                "FROM qc_hold_batches b "
                "JOIN production_orders po ON b.production_order_id = po.id "
                "WHERE b.id = ?",
                (batch_id,),
            ).fetchone()
            if not batch:
                raise ValueError(f"QC hold batch {batch_id} not found")

            # Idempotency: return existing completed inspection
            existing = conn.execute(
                "SELECT * FROM qc_inspections WHERE qc_hold_batch_id = ? AND status = 'completed'",
                (batch_id,),
            ).fetchone()
            if existing:
                return self.get_inspection(inspection_id=existing["id"])

            # Delete any failed inspection so we can retry
            conn.execute(
                "DELETE FROM qc_inspections WHERE qc_hold_batch_id = ? AND status = 'failed'",
                (batch_id,),
            )
            conn.commit()

            # Validate images exist
            images = dict_rows(conn.execute(
                "SELECT * FROM qc_hold_images WHERE qc_hold_batch_id = ? ORDER BY created_at",
                (batch_id,),
            ))
            if not images:
                raise ValueError(f"No images attached to batch {batch_id}. Attach images first.")

            # Resolve reference image BLOB from item
            item_row = conn.execute(
                "SELECT image FROM items WHERE id = ?",
                (batch["item_id"],),
            ).fetchone()
            if not item_row or item_row["image"] is None:
                raise ValueError(
                    f"Item {batch['item_id']} has no reference image. "
                    "Upload a reference image to the item record first."
                )
            img_bytes = item_row["image"]
            # Detect actual format from magic bytes to avoid Bedrock media-type mismatch
            if img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
                mime = "image/png"
            elif img_bytes[:3] == b"\xff\xd8\xff":
                mime = "image/jpeg"
            elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
                mime = "image/webp"
            else:
                mime = "image/jpeg"  # fallback
            reference_image_b64 = base64.b64encode(img_bytes).decode("ascii")
            reference_image_uri = f"data:{mime};base64,{reference_image_b64}"

            sim_time = simulation_service.get_current_time()

            # Phase 1: INSERT with status='pending' and empty decision placeholder
            inspection_id = generate_id(conn, ID_PREFIXES["qc_inspections"], "qc_inspections")
            conn.execute(
                "INSERT INTO qc_inspections "
                "(id, qc_hold_batch_id, production_order_id, model_name, status, decision, "
                "prompt_version, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', '', 'v1', ?)",
                (inspection_id, batch_id, batch["production_order_id"],
                 config.QC_INFERENCE_MODEL, sim_time),
            )
            conn.commit()

        # Phase 2: Call inference API (outside any long-lived connection block)
        # The remote inference API cannot fetch arbitrary URLs, so all operator images
        # must be inlined as data URIs.
        def _to_data_uri(url: str) -> str:
            if url.startswith("data:"):
                return url
            if url.startswith("file://"):
                img_bytes = open(url[len("file://"):], "rb").read()
            else:
                import urllib.request
                with urllib.request.urlopen(url) as r:  # nosec — internal trusted URLs only
                    img_bytes = r.read()
            if img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
                mime = "image/png"
            elif img_bytes[:3] == b"\xff\xd8\xff":
                mime = "image/jpeg"
            elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
                mime = "image/webp"
            else:
                mime = "image/jpeg"
            return f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"

        operator_image_url = _to_data_uri(images[0]["image_url"])
        logger.info("[QC Inspection] batch=%s — operator image inlined as data URI", batch_id)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a quality control inspector for rubber duck manufacturing. "
                            "Compare the reference product image (first) with the submitted batch image (second). "
                            "Identify any defects or quality issues. "
                            "Respond ONLY with a valid JSON object matching this schema exactly:\n"
                            '{"decision": "pass|partial_scrap|full_scrap", '
                            '"confidence_overall": <float 0-1>, '
                            '"decision_reason": "<string>", '
                            '"findings": [{"type": "<finding_type>", "severity": "<severity>", '
                            '"confidence": <float 0-1>, "description": "<string>", '
                            '"image_ref": null, "location_hint": null}]}\n'
                            "finding_type must be one of: wrong_product, paint_defect, shape_defect, "
                            "assembly_defect, packaging_defect, missing_part. "
                            "severity must be one of: critical, major, minor. "
                            "decision: pass=all good, partial_scrap=some defects, full_scrap=all defective."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": reference_image_uri}},
                    {"type": "image_url", "image_url": {"url": operator_image_url}},
                ],
            }
        ]

        try:
            if config.QC_INFERENCE_MOCK:
                logger.info(
                    "[QC Inspection] batch=%s — MOCK mode, skipping inference API",
                    batch_id,
                )
                raw_content = json.dumps({
                    "decision": "partial_scrap",
                    "confidence_overall": 0.82,
                    "decision_reason": "[MOCK] Paint defects detected on approximately 30% of units. Remaining units meet quality standards.",
                    "findings": [
                        {
                            "type": "paint_defect",
                            "severity": "major",
                            "confidence": 0.88,
                            "description": "[MOCK] Uneven paint coverage on beak area, visible colour bleed.",
                            "image_ref": None,
                            "location_hint": "beak",
                        },
                        {
                            "type": "shape_defect",
                            "severity": "minor",
                            "confidence": 0.65,
                            "description": "[MOCK] Slight deformation on tail section, within acceptable tolerance for most units.",
                            "image_ref": None,
                            "location_hint": "tail",
                        },
                    ],
                })
            else:
                logger.info(
                    "[QC Inspection] batch=%s model=%s images=%d — calling inference API...",
                    batch_id, config.QC_INFERENCE_MODEL, len(images),
                )
                response = myforterro.chat_completion(
                    model=config.QC_INFERENCE_MODEL,
                    messages=messages,
                )
                raw_content = response.choices[0].message.content

            # Strip markdown code fences if the model wraps JSON in ```json ... ```
            stripped = raw_content.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            # Parse and validate the JSON response
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Inspection model returned invalid JSON: {exc}. Content: {stripped[:500]}") from exc

            if "decision" not in parsed:
                raise ValueError(f"Inspection model response missing 'decision' field. Got: {parsed}")
            if parsed["decision"] not in INFERENCE_DECISIONS:
                raise ValueError(
                    f"Inspection model returned invalid decision '{parsed['decision']}'. "
                    f"Must be one of: {INFERENCE_DECISIONS}"
                )
            if not isinstance(parsed.get("findings"), list):
                raise ValueError("Inspection model response 'findings' must be a list.")

            with db_conn() as conn:
                sim_time = simulation_service.get_current_time()
                conn.execute(
                    "UPDATE qc_inspections SET status='completed', decision=?, "
                    "confidence_overall=?, decision_reason=?, completed_at=? WHERE id=?",
                    (
                        parsed["decision"],
                        parsed.get("confidence_overall"),
                        parsed.get("decision_reason"),
                        sim_time,
                        inspection_id,
                    ),
                )
                for finding in parsed["findings"]:
                    finding_id = generate_id(
                        conn, ID_PREFIXES["qc_inspection_findings"], "qc_inspection_findings"
                    )
                    conn.execute(
                        "INSERT INTO qc_inspection_findings "
                        "(id, qc_inspection_id, finding_type, severity, confidence, description, "
                        "image_ref, location_hint, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            finding_id, inspection_id,
                            finding.get("type", finding.get("finding_type", "")),
                            finding.get("severity", ""),
                            finding.get("confidence"),
                            finding.get("description", finding.get("issue", "")),
                            finding.get("image_ref"),
                            finding.get("location_hint", finding.get("location")),
                            sim_time,
                        ),
                    )
                conn.execute(
                    "UPDATE qc_hold_batches SET status = 'inspected' WHERE id = ?",
                    (batch_id,),
                )
                conn.commit()

            logger.info(
                "[QC Inspection] batch=%s — decision=%s confidence=%.2f findings=%d",
                batch_id,
                parsed["decision"],
                parsed.get("confidence_overall") or 0.0,
                len(parsed.get("findings", [])),
            )

        except Exception as exc:
            logger.exception("[QC Inspection] batch=%s — inspection failed: %s", batch_id, exc)
            with db_conn() as conn:
                conn.execute(
                    "UPDATE qc_inspections SET status = 'failed' WHERE id = ?",
                    (inspection_id,),
                )
                conn.commit()
            raise

        return self.get_inspection(inspection_id=inspection_id)

    # ------------------------------------------------------------------
    # Disposition
    # ------------------------------------------------------------------

    def apply_disposition(
        self,
        *,
        qc_inspection_id: str,
        action: str,
        approved_by: str | None = None,
        reason: str | None = None,
        qty_scrapped: int = 0,
    ) -> dict[str, Any]:
        """Apply a QC disposition. Transactional and idempotent.

        pass_release: release all qty into stock.
        partial_scrap: scrap qty_scrapped, release remainder.
        full_scrap: scrap all qty.
        """
        if action not in DISPOSITION_ACTIONS:
            raise ValueError(f"Invalid disposition action '{action}'. Must be one of: {DISPOSITION_ACTIONS}")

        with db_conn() as conn:
            # Idempotency: return existing disposition
            existing = conn.execute(
                "SELECT * FROM qc_dispositions WHERE qc_inspection_id = ?",
                (qc_inspection_id,),
            ).fetchone()
            if existing:
                return dict(existing)

            inspection = conn.execute(
                "SELECT * FROM qc_inspections WHERE id = ?",
                (qc_inspection_id,),
            ).fetchone()
            if not inspection:
                raise ValueError(f"QC inspection {qc_inspection_id} not found")
            if inspection["status"] != "completed":
                raise ValueError(
                    f"Inspection {qc_inspection_id} is not completed (status={inspection['status']}). "
                    "Only completed inspections can be disposed."
                )

            batch_id = inspection["qc_hold_batch_id"]
            batch = conn.execute(
                "SELECT * FROM qc_hold_batches WHERE id = ?",
                (batch_id,),
            ).fetchone()
            if not batch:
                raise ValueError(f"QC hold batch {batch_id} not found")

            line = conn.execute(
                "SELECT * FROM qc_hold_batch_lines WHERE qc_hold_batch_id = ? LIMIT 1",
                (batch_id,),
            ).fetchone()
            if not line:
                raise ValueError(f"No hold lines found for batch {batch_id}")
            line = dict(line)

            from services.simulation import simulation_service
            sim_time = simulation_service.get_current_time()

            if action == "partial_scrap":
                if qty_scrapped <= 0:
                    raise ValueError("partial_scrap requires qty_scrapped > 0")
                if qty_scrapped >= line["qty_pending"]:
                    raise ValueError(
                        f"qty_scrapped ({qty_scrapped}) must be less than qty_pending ({line['qty_pending']}) "
                        "for partial_scrap. Use full_scrap to scrap all."
                    )

            # Create disposition record
            disposition_id = generate_id(conn, ID_PREFIXES["qc_dispositions"], "qc_dispositions")
            conn.execute(
                "INSERT INTO qc_dispositions (id, qc_inspection_id, qc_hold_batch_id, action, approved_by, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (disposition_id, qc_inspection_id, batch_id, action, approved_by, reason, sim_time),
            )

            qty_to_release = 0
            qty_to_scrap = 0

            if action == "pass_release":
                qty_to_release = line["qty_pending"]
            elif action == "partial_scrap":
                qty_to_scrap = qty_scrapped
                qty_to_release = line["qty_pending"] - qty_scrapped
            else:  # full_scrap
                qty_to_scrap = line["qty_pending"]

            # Apply stock movements and update hold line
            if qty_to_release > 0:
                stock_id = generate_id(conn, "STK", "stock")
                conn.execute(
                    "INSERT INTO stock (id, item_id, warehouse, location, on_hand) VALUES (?, ?, ?, ?, ?)",
                    (stock_id, batch["item_id"], config.WAREHOUSE_DEFAULT, config.LOC_FINISHED_GOODS, qty_to_release),
                )
                mov_id = generate_id(conn, "MOV", "stock_movements")
                conn.execute(
                    "INSERT INTO stock_movements "
                    "(id, timestamp, item_id, movement_type, qty, stock_id, reference_type, reference_id, "
                    "qc_hold_batch_line_id, qc_inspection_id) "
                    "VALUES (?, ?, ?, 'qc_hold_release', ?, ?, 'qc_disposition', ?, ?, ?)",
                    (mov_id, sim_time, batch["item_id"], qty_to_release, stock_id,
                     disposition_id, line["id"], qc_inspection_id),
                )

            if qty_to_scrap > 0:
                mov_id = generate_id(conn, "MOV", "stock_movements")
                conn.execute(
                    "INSERT INTO stock_movements "
                    "(id, timestamp, item_id, movement_type, qty, stock_id, reference_type, reference_id, "
                    "qc_hold_batch_line_id, qc_inspection_id) "
                    "VALUES (?, ?, ?, 'qc_scrap', ?, NULL, 'qc_disposition', ?, ?, ?)",
                    (mov_id, sim_time, batch["item_id"], qty_to_scrap,
                     disposition_id, line["id"], qc_inspection_id),
                )

            # Update hold line quantities
            new_released = line["qty_released"] + qty_to_release
            new_scrapped = line["qty_scrapped"] + qty_to_scrap
            new_pending = 0  # always zero after disposition

            if action == "pass_release":
                new_line_status = "released"
            elif action == "partial_scrap":
                new_line_status = "partially_released"
            else:
                new_line_status = "scrapped"

            conn.execute(
                "UPDATE qc_hold_batch_lines SET qty_pending=?, qty_released=?, qty_scrapped=?, "
                "line_status=?, closed_at=? WHERE id=?",
                (new_pending, new_released, new_scrapped, new_line_status, sim_time, line["id"]),
            )

            # Update batch status
            if action == "pass_release":
                new_batch_status = "released"
            elif action == "partial_scrap":
                new_batch_status = "partially_released"
            else:
                new_batch_status = "closed"

            released_at = sim_time if action in ("pass_release", "partial_scrap") else None
            conn.execute(
                "UPDATE qc_hold_batches SET status=?, released_at=? WHERE id=?",
                (new_batch_status, released_at, batch_id),
            )

            # Update production order inspection_status
            if action == "pass_release":
                new_inspection_status = "released"
            elif action == "partial_scrap":
                new_inspection_status = "partially_released"
            else:
                new_inspection_status = "released"  # fully scrapped counts as closed/released

            conn.execute(
                "UPDATE production_orders SET inspection_status=? WHERE id=?",
                (new_inspection_status, batch["production_order_id"]),
            )

            conn.commit()

        # Replacement logic (outside the transaction per plan)
        if qty_to_scrap > 0:
            self._maybe_create_replacement(
                batch_id=batch_id,
                batch=dict(batch),
                line=line,
                qty_to_scrap=qty_to_scrap,
                disposition_id=disposition_id,
                sim_time=sim_time,
            )

        return self.get_inspection(inspection_id=qc_inspection_id)

    def _maybe_create_replacement(
        self,
        *,
        batch_id: str,
        batch: dict,
        line: dict,
        qty_to_scrap: int,
        disposition_id: str,
        sim_time: str,
    ) -> None:
        """Create a replacement production order if scrap creates a shortage."""
        sales_order_id = batch.get("sales_order_id")
        if not sales_order_id:
            logger.debug("Skipping replacement creation: batch %s has no sales_order_id", batch_id)
            return

        # Resolve recipe and output_qty for the item
        with db_conn() as conn:
            recipe_row = conn.execute(
                "SELECT id, output_qty FROM recipes WHERE output_item_id = ? LIMIT 1",
                (batch["item_id"],),
            ).fetchone()
        if not recipe_row:
            logger.warning("No recipe found for item %s; cannot create replacement MO", batch["item_id"])
            return

        output_qty = recipe_row["output_qty"]
        qty_short = qty_to_scrap  # MVP: available_substitute_qty = 0
        qty_replacement = math.ceil(qty_short / output_qty) * output_qty

        # Phase 1: Insert qc_replacements placeholder inside its own transaction
        with db_conn() as conn:
            repl_id = generate_id(conn, ID_PREFIXES["qc_replacements"], "qc_replacements")
            conn.execute(
                "INSERT INTO qc_replacements "
                "(id, qc_disposition_id, sales_order_id, item_id, qty_short, qty_replacement, "
                "replacement_production_order_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, '', ?)",
                (repl_id, disposition_id, sales_order_id, batch["item_id"],
                 qty_short, qty_replacement, sim_time),
            )
            conn.commit()

        # Phase 2: Create the replacement MO (uses its own db_conn block internally)
        from services.production import create_order
        try:
            mo_result = create_order(
                recipe_id=recipe_row["id"],
                sales_order_id=sales_order_id,
                notes=f"QC replacement for {batch_id}",
            )
            new_mo_id = mo_result["production_order_id"]
        except Exception as exc:
            logger.warning(
                "Failed to create replacement MO for batch %s: %s. "
                "qc_replacements row %s has empty replacement_production_order_id.",
                batch_id, exc, repl_id,
            )
            return

        # Phase 3: Update the replacement row with the actual MO ID
        with db_conn() as conn:
            conn.execute(
                "UPDATE qc_replacements SET replacement_production_order_id = ? WHERE id = ?",
                (new_mo_id, repl_id),
            )
            conn.execute(
                "UPDATE qc_hold_batches SET replacement_triggered = 1 WHERE id = ?",
                (batch_id,),
            )
            conn.commit()

        logger.info("Created replacement MO %s for batch %s (scrapped=%d, replacement=%d)",
                    new_mo_id, batch_id, qty_to_scrap, qty_replacement)


qc_service = QcService()
