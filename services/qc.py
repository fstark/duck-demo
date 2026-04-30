"""Service for Quality Control operations.

Manages the QC lifecycle:
  hold batch creation → image submission → AI inspection → disposition.
"""

import base64
import io
import json
import logging
import math
import os
from typing import Any

from PIL import Image

import config
from db import dict_rows, generate_id
from services._base import db_conn

logger = logging.getLogger("duck-demo")

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

HOLD_BATCH_STATUS_VALUES = frozenset({
    "pending",
    "inspected",
    "closed",
})

DISPOSITION_ACTIONS = frozenset({"pass_release", "partial_scrap", "full_scrap"})

FINDING_TYPES = frozenset({
    "wrong_product", "paint_defect", "shape_defect",
    "assembly_defect", "packaging_defect", "missing_part",
})

FINDING_SEVERITIES = frozenset({"critical", "major", "minor"})

INFERENCE_DECISIONS = frozenset({"pass", "partial_scrap", "full_scrap"})

ID_PREFIXES = {
    "qc_hold_batches": "QCB",
    "qc_hold_images": "QCIMG",
    "qc_inspections": "QCI",
    "qc_inspection_findings": "QCIF",
}


def _to_data_uri(blob: bytes) -> str:
    """Convert a raw image BLOB to a base64 data URI."""
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif blob[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(blob).decode('ascii')}"


def _mock_ducks(n: int, img_w: int = 1024, img_h: int = 1024) -> list[dict]:
    """Generate *n* evenly-laid-out mock duck results (pixel coords)."""
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    ducks: list[dict] = []
    severities = ["none", "major", "minor"]
    defect_texts = [
        [], ["[MOCK] Uneven paint on beak."], ["[MOCK] Slight smear."],
    ]
    for i in range(n):
        r, c = divmod(i, cols)
        x1 = round(c / cols * img_w + 10)
        y1 = round(r / rows * img_h + 10)
        x2 = round((c + 1) / cols * img_w - 10)
        y2 = round((r + 1) / rows * img_h - 10)
        sev = severities[i % len(severities)]
        ducks.append({
            "bbox": [x1, y1, x2, y2],
            "severity": sev,
            "defects": defect_texts[i % len(defect_texts)],
        })
    return ducks


class QcService:
    """QC domain service — hold, inspect, dispose."""

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
        """Create a QC hold batch for an inspection-required MO.

        Must be called within an existing db_conn() block (conn is provided).
        Does NOT commit; the caller's transaction owns the commit.
        """
        batch_id = generate_id(conn, ID_PREFIXES["qc_hold_batches"], "qc_hold_batches")
        conn.execute(
            "INSERT INTO qc_hold_batches "
            "(id, production_order_id, sales_order_id, item_id, status, qty_on_hold, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (batch_id, production_order_id, sales_order_id, item_id, qty_produced, sim_time),
        )
        conn.execute(
            "UPDATE production_orders SET inspection_status = 'pending_inspection' WHERE id = ?",
            (production_order_id,),
        )
        return {"qc_hold_batch_id": batch_id}

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def list_pending_batches(self, *, status: str = "pending") -> list[dict]:
        with db_conn() as conn:
            rows = dict_rows(conn.execute(
                """
                SELECT b.*, i.sku as item_sku, i.name as item_name
                FROM qc_hold_batches b
                JOIN items i ON b.item_id = i.id
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
            image_rows = dict_rows(conn.execute(
                "SELECT id, qc_hold_batch_id, created_at, uploaded_by "
                "FROM qc_hold_images WHERE qc_hold_batch_id = ? ORDER BY created_at",
                (batch_id,),
            ))
            for img in image_rows:
                img["image_url"] = f"/api/qc/images/{img['id']}"
            result["images"] = image_rows
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
        return result

    def get_image_blob(self, *, image_id: str) -> tuple[bytes, str]:
        """Return (raw_bytes, mime_type) for a QC hold image."""
        with db_conn() as conn:
            row = conn.execute(
                "SELECT image_data FROM qc_hold_images WHERE id = ?",
                (image_id,),
            ).fetchone()
            if not row or not row["image_data"]:
                raise ValueError(f"QC image {image_id} not found")
            blob = row["image_data"]
            if blob[:8] == b"\x89PNG\r\n\x1a\n":
                mime = "image/png"
            elif blob[:3] == b"\xff\xd8\xff":
                mime = "image/jpeg"
            elif blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
                mime = "image/webp"
            else:
                mime = "image/jpeg"
            return blob, mime

    def get_inspection_for_mo(self, *, production_order_id: str) -> dict[str, Any]:
        """Return the QC inspection for a production order (there is at most one)."""
        with db_conn() as conn:
            batch = conn.execute(
                "SELECT id FROM qc_hold_batches WHERE production_order_id = ?",
                (production_order_id,),
            ).fetchone()
            if not batch:
                raise ValueError(f"No QC hold batch found for production order {production_order_id}")
            insp = conn.execute(
                "SELECT * FROM qc_inspections WHERE qc_hold_batch_id = ? AND status != 'failed' "
                "ORDER BY created_at DESC LIMIT 1",
                (batch["id"],),
            ).fetchone()
            if not insp:
                raise ValueError(
                    f"No inspection found for production order {production_order_id}. "
                    "Run the inspection first."
                )
        return self._load_inspection(inspection_id=insp["id"])

    def _load_inspection(self, *, inspection_id: str) -> dict[str, Any]:
        """Load a full inspection record with findings and images for the MCP app."""
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
            if result.get("duck_results"):
                try:
                    result["duck_results"] = json.loads(result["duck_results"])
                except (json.JSONDecodeError, TypeError):
                    pass

            # Attach operator image and reference image as data URIs for the MCP app
            batch_row = conn.execute(
                "SELECT b.production_order_id, po.item_id "
                "FROM qc_hold_batches b "
                "JOIN production_orders po ON b.production_order_id = po.id "
                "WHERE b.id = ?",
                (result["qc_hold_batch_id"],),
            ).fetchone()
            if batch_row:
                op_row = conn.execute(
                    "SELECT image_data FROM qc_hold_images "
                    "WHERE qc_hold_batch_id = ? ORDER BY created_at LIMIT 1",
                    (result["qc_hold_batch_id"],),
                ).fetchone()
                if op_row and op_row["image_data"]:
                    result["operator_image_uri"] = _to_data_uri(op_row["image_data"])
                ref_row = conn.execute(
                    "SELECT image FROM items WHERE id = ?",
                    (batch_row["item_id"],),
                ).fetchone()
                if ref_row and ref_row["image"]:
                    result["reference_image_uri"] = _to_data_uri(ref_row["image"])
        return result

    # ------------------------------------------------------------------
    # AI Inspection (internal — called by submit_image)
    # ------------------------------------------------------------------

    def _run_inspection(self, *, batch_id: str) -> dict[str, Any]:
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
                return self._load_inspection(inspection_id=existing["id"])

            # Delete any failed inspection so we can retry
            conn.execute(
                "DELETE FROM qc_inspections WHERE qc_hold_batch_id = ? AND status = 'failed'",
                (batch_id,),
            )
            conn.commit()

            # Validate images exist
            images = dict_rows(conn.execute(
                "SELECT image_data FROM qc_hold_images WHERE qc_hold_batch_id = ? ORDER BY created_at",
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
            reference_image_uri = _to_data_uri(item_row["image"])

            expected_qty = batch["qty_on_hold"]

            sim_time = simulation_service.get_current_time()

            # Phase 1: INSERT with status='pending'
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
        blob = images[0]["image_data"]
        operator_image_uri = _to_data_uri(blob)
        img_w, img_h = Image.open(io.BytesIO(blob)).size
        logger.info("[QC Inspection] batch=%s — operator image %dx%d read from BLOB", batch_id, img_w, img_h)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a quality control inspector for rubber duck manufacturing. "
                            "The first image is the approved reference product. "
                            "The second image is the submitted batch taken by the operator. "
                            f"The batch contains exactly {expected_qty} ducks. "
                            "Locate every individual duck visible in the submitted image and assess each one. "
                            f"Return exactly {expected_qty} entries in the ducks array, one per duck. "
                            "Respond ONLY with a valid JSON object matching this schema exactly:\n"
                            '{"decision": "pass|partial_scrap|full_scrap", '
                            '"decision_reason": "<string>", '
                            '"ducks": [{'
                            '"bbox": [x1, y1, x2, y2], '
                            '"severity": "none|minor|major", '
                            '"defects": ["<description>"]'
                            '}]}\n'
                            "bbox coordinates are in pixels relative to the submitted image "
                            f"(which is {img_w}×{img_h} px). "
                            "x1,y1 = top-left corner, x2,y2 = bottom-right corner. "
                            "severity: none=no defects, minor=cosmetic only, major=reject. "
                            "decision: pass=all ducks acceptable, partial_scrap=some major ducks, "
                            "full_scrap=all ducks major."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": reference_image_uri}},
                    {"type": "image_url", "image_url": {"url": operator_image_uri}},
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
                    "decision_reason": "[MOCK] Most ducks look good but two have visible paint defects.",
                    "ducks": _mock_ducks(expected_qty or 6, img_w, img_h),
                })
            else:
                logger.info(
                    "[QC Inspection] batch=%s model=%s provider=%s — calling inference API...",
                    batch_id, config.QC_INFERENCE_MODEL, config.QC_INFERENCE_PROVIDER,
                )
                if config.QC_INFERENCE_PROVIDER == "openai":
                    response = myforterro.openai_chat_completion(
                        model=config.QC_INFERENCE_MODEL,
                        messages=messages,
                    )
                else:
                    response = myforterro.chat_completion(
                        model=config.QC_INFERENCE_MODEL,
                        messages=messages,
                    )
                raw_content = response.choices[0].message.content

            # Strip markdown code fences if the model wraps JSON in ```json ... ```
            stripped = raw_content.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            parsed = json.loads(stripped)
            if "decision" not in parsed:
                raise ValueError(f"Inspection model response missing 'decision' field. Got: {parsed}")
            if parsed["decision"] not in INFERENCE_DECISIONS:
                raise ValueError(
                    f"Inspection model returned invalid decision '{parsed['decision']}'. "
                    f"Must be one of: {INFERENCE_DECISIONS}"
                )
            if not isinstance(parsed.get("ducks"), list):
                raise ValueError("Inspection model response 'ducks' must be a list.")

            # Normalise pixel bbox → [0, 1] floats for storage and UI
            for duck in parsed["ducks"]:
                if "bbox" in duck and len(duck["bbox"]) == 4:
                    x1, y1, x2, y2 = duck["bbox"]
                    duck["bbox"] = [
                        round(x1 / img_w, 4),
                        round(y1 / img_h, 4),
                        round(x2 / img_w, 4),
                        round(y2 / img_h, 4),
                    ]

            duck_results_json = json.dumps(parsed["ducks"])

            # Derive findings from duck results
            findings: list[dict] = []
            for duck in parsed["ducks"]:
                sev = duck.get("severity", "none")
                if sev == "none":
                    continue
                for desc in duck.get("defects", []):
                    findings.append({
                        "type": "shape_defect",
                        "severity": "major" if sev == "major" else "minor",
                        "description": desc,
                    })

            with db_conn() as conn:
                sim_time = simulation_service.get_current_time()
                conn.execute(
                    "UPDATE qc_inspections SET status='completed', decision=?, "
                    "decision_reason=?, duck_results=?, completed_at=? WHERE id=?",
                    (
                        parsed["decision"],
                        parsed.get("decision_reason"),
                        duck_results_json,
                        sim_time,
                        inspection_id,
                    ),
                )
                for finding in findings:
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
                            finding.get("type", "shape_defect"),
                            finding.get("severity", ""),
                            None,
                            finding.get("description", ""),
                            None,
                            None,
                            sim_time,
                        ),
                    )
                conn.execute(
                    "UPDATE qc_hold_batches SET status = 'inspected' WHERE id = ?",
                    (batch_id,),
                )
                conn.commit()

            logger.info(
                "[QC Inspection] batch=%s — decision=%s ducks=%d findings=%d",
                batch_id, parsed["decision"], len(parsed.get("ducks", [])), len(findings),
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

        return self._load_inspection(inspection_id=inspection_id)

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
        """Apply a QC disposition.

        pass_release: release all qty into stock.
        partial_scrap: scrap qty_scrapped, release remainder.
        full_scrap: scrap all qty.
        """
        if action not in DISPOSITION_ACTIONS:
            raise ValueError(f"Invalid disposition action '{action}'. Must be one of: {DISPOSITION_ACTIONS}")

        with db_conn() as conn:
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
            if batch["status"] == "closed":
                return self._load_inspection(inspection_id=qc_inspection_id)

            from services.simulation import simulation_service
            sim_time = simulation_service.get_current_time()

            qty_pending = batch["qty_on_hold"] - batch["qty_released"] - batch["qty_scrapped"]

            if action == "partial_scrap":
                if qty_scrapped <= 0:
                    raise ValueError("partial_scrap requires qty_scrapped > 0")
                if qty_scrapped >= qty_pending:
                    raise ValueError(
                        f"qty_scrapped ({qty_scrapped}) must be less than qty_pending ({qty_pending}) "
                        "for partial_scrap. Use full_scrap to scrap all."
                    )

            qty_to_release = 0
            qty_to_scrap = 0

            if action == "pass_release":
                qty_to_release = qty_pending
            elif action == "partial_scrap":
                qty_to_scrap = qty_scrapped
                qty_to_release = qty_pending - qty_scrapped
            else:  # full_scrap
                qty_to_scrap = qty_pending

            # Apply stock movements
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
                    "qc_inspection_id) "
                    "VALUES (?, ?, ?, 'qc_hold_release', ?, ?, 'qc_batch', ?, ?)",
                    (mov_id, sim_time, batch["item_id"], qty_to_release, stock_id,
                     batch_id, qc_inspection_id),
                )

            if qty_to_scrap > 0:
                mov_id = generate_id(conn, "MOV", "stock_movements")
                conn.execute(
                    "INSERT INTO stock_movements "
                    "(id, timestamp, item_id, movement_type, qty, stock_id, reference_type, reference_id, "
                    "qc_inspection_id) "
                    "VALUES (?, ?, ?, 'qc_scrap', ?, NULL, 'qc_batch', ?, ?)",
                    (mov_id, sim_time, batch["item_id"], qty_to_scrap,
                     batch_id, qc_inspection_id),
                )

            # Update hold batch quantities and status
            new_released = batch["qty_released"] + qty_to_release
            new_scrapped = batch["qty_scrapped"] + qty_to_scrap

            conn.execute(
                "UPDATE qc_hold_batches SET qty_released=?, qty_scrapped=?, status='closed', released_at=? WHERE id=?",
                (new_released, new_scrapped, sim_time, batch_id),
            )

            conn.execute(
                "UPDATE production_orders SET inspection_status='released' WHERE id=?",
                (batch["production_order_id"],),
            )

            conn.commit()

        return self._load_inspection(inspection_id=qc_inspection_id)

    # ------------------------------------------------------------------
    # Single-shot image submission (label extraction + inspection)
    # ------------------------------------------------------------------

    def submit_image(
        self,
        *,
        image_input: str,
        uploaded_by: str | None = None,
    ) -> dict[str, Any]:
        """Single demo step: take a picture of a production batch and the system
        extracts the MO label, stores the image, and runs AI inspection.

        Parameters:
            image_input: base64-encoded image string, data URI, or file path URL
            uploaded_by: optional operator identifier

        Returns:
            Inspection record with decision, confidence, reason, and findings.
        """
        from services import myforterro
        from services.simulation import simulation_service

        # Decode input to raw bytes
        if image_input.startswith("data:"):
            _, b64data = image_input.split(",", 1)
            img_bytes = base64.b64decode(b64data)
        elif image_input.startswith("file://"):
            from urllib.parse import urlparse, unquote
            file_path = unquote(urlparse(image_input).path)
            # On Windows, strip leading slash before drive letter (e.g. /C:/...)
            if len(file_path) >= 3 and file_path[0] == '/' and file_path[2] == ':':
                file_path = file_path[1:]
            img_bytes = open(file_path, "rb").read()
        elif os.path.isfile(image_input):
            img_bytes = open(image_input, "rb").read()
        else:
            img_bytes = base64.b64decode(image_input)

        # Detect mime from magic bytes
        if img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif img_bytes[:3] == b"\xff\xd8\xff":
            mime = "image/jpeg"
        elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            mime = "image/jpeg"
        image_data_uri = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"

        # Phase 1: Extract MO label from image
        if config.QC_INFERENCE_MOCK:
            with db_conn() as conn:
                row = conn.execute(
                    "SELECT id FROM production_orders "
                    "WHERE inspection_status = 'pending_inspection' LIMIT 1"
                ).fetchone()
            if not row:
                raise ValueError(
                    "No production orders in pending_inspection status (mock mode). "
                    "Run a scenario to generate data."
                )
            mo_id = row["id"]
            logger.info("[QC Submit] MOCK mode — using first pending MO: %s", mo_id)
        else:
            label_messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Look carefully at this manufacturing batch image. "
                                "Find the Manufacturing Order label printed on it. "
                                "It will be in the format MO-XXXX (e.g., MO-2001, MO-9000). "
                                "Respond ONLY with a JSON object: "
                                "{\"mo_id\": \"MO-XXXX\"} if found, "
                                "or {\"mo_id\": null} if no label is visible."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": image_data_uri}},
                    ],
                }
            ]
            logger.info("[QC Submit] Phase 1 — extracting MO label from image...")
            if config.QC_INFERENCE_PROVIDER == "openai":
                label_response = myforterro.openai_chat_completion(
                    model=config.QC_LABEL_MODEL,
                    messages=label_messages,
                )
            else:
                label_response = myforterro.chat_completion(
                    model=config.QC_LABEL_MODEL,
                    messages=label_messages,
                )
            raw = label_response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            try:
                parsed_label = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Label extraction returned invalid JSON: {exc}. Content: {raw[:200]}"
                ) from exc
            mo_id = parsed_label.get("mo_id")
            if not mo_id:
                raise ValueError(
                    "No Manufacturing Order label found in image. "
                    "Make sure the MO label is clearly visible on the batch."
                )
            logger.info("[QC Submit] Phase 1 — extracted label: %s", mo_id)

        # Phase 2: Validate MO and attach image
        with db_conn() as conn:
            mo = conn.execute(
                "SELECT id, inspection_status FROM production_orders WHERE id = ?",
                (mo_id,),
            ).fetchone()
            if not mo:
                raise ValueError(f"Production order {mo_id} not found.")
            if mo["inspection_status"] != "pending_inspection":
                raise ValueError(
                    f"Production order {mo_id} is not awaiting inspection "
                    f"(inspection_status='{mo['inspection_status']}'). "
                    "Only orders in 'pending_inspection' status can be submitted."
                )
            batch = conn.execute(
                "SELECT id FROM qc_hold_batches WHERE production_order_id = ?",
                (mo_id,),
            ).fetchone()
            if not batch:
                raise ValueError(f"No QC hold batch found for production order {mo_id}.")
            batch_id = batch["id"]

            # Store the image
            sim_time = simulation_service.get_current_time()
            img_id = generate_id(conn, ID_PREFIXES["qc_hold_images"], "qc_hold_images")
            conn.execute(
                "INSERT INTO qc_hold_images (id, qc_hold_batch_id, image_data, created_at, uploaded_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (img_id, batch_id, img_bytes, sim_time, uploaded_by),
            )
            conn.commit()

        # Phase 3: Run inspection
        logger.info(
            "[QC Submit] Phase 2 — attached image to %s (batch %s), running inspection...",
            mo_id, batch_id,
        )
        return self._run_inspection(batch_id=batch_id)


qc_service = QcService()
