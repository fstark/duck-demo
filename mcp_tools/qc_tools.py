"""MCP tools – Quality Control (QC) operations."""

import base64
from typing import Any, Dict, List, Optional

from mcp_tools._common import log_tool, create_confirmation_response
from services import qc_service


def register(mcp):
    """Register QC tools."""

    @mcp.tool(name="qc_submit_image", meta={
        "tags": ["quality"],
        "ui": {
            "resourceUri": "ui://qc-inspection/result",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("qc_submit_image")
    def qc_submit_image(
        image: str,
        uploaded_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit a QC inspection photo. The Manufacturing Order label is read
        automatically from the image — no need to specify an MO ID.

        This is the single demo step: take a picture of a production batch
        and the system does the rest.

        What happens:
          1. The MO label (e.g., MO-9000) is extracted from the image via AI.
          2. If the MO is in 'pending_inspection' status, the image is stored
             and the AI inspection runs immediately.

        Parameters:
            image: Image as a base64 string, data URI ('data:image/png;base64,...'),
                   or file path URL ('file:///path/to/image.png')
            uploaded_by: Optional operator identifier

        Returns:
            Inspection record with decision, confidence, reason, and findings.
        """
        return qc_service.submit_image(image_input=image, uploaded_by=uploaded_by)

    @mcp.tool(name="qc_list_pending_inspections", meta={"tags": ["quality"]})
    @log_tool("qc_list_pending_inspections")
    def qc_list_pending_inspections(status: str = "pending_images") -> List[Dict[str, Any]]:
        """
        List production orders currently under QC hold, filtered by status.

        Parameters:
            status: QC status filter (default: 'pending_images').
                    Values: pending_images, ready_for_inspection, inspected,
                            released, partially_released, closed

        Returns:
            List of QC hold records with production_order_id and item/quantity details.
        """
        return qc_service.list_pending_batches(status=status)

    @mcp.tool(name="qc_get_mo_inspection", meta={"tags": ["quality"]})
    @log_tool("qc_get_mo_inspection")
    def qc_get_mo_inspection(production_order_id: str) -> Dict[str, Any]:
        """
        Get the QC inspection result for a Manufacturing Order.
        There is at most one inspection per MO.

        Parameters:
            production_order_id: The Manufacturing Order ID (e.g., 'MO-9000')

        Returns:
            Inspection record with model decision, confidence, reason, and findings list.
        """
        return qc_service.get_inspection_for_mo(production_order_id=production_order_id)

    @mcp.tool(name="qc_get_batch", meta={"tags": ["quality"]})
    @log_tool("qc_get_batch")
    def qc_get_batch(batch_id: str) -> Dict[str, Any]:
        """
        Get a QC hold batch with its lines, images, inspection summary, and replacements.

        Parameters:
            batch_id: The QC hold batch ID (e.g., 'QCB-0001')

        Returns:
            Full batch detail including lines, images, inspection (if run), replacements.
        """
        return qc_service.get_batch(batch_id=batch_id)

    @mcp.tool(name="qc_get_inspection", meta={"tags": ["quality"]})
    @log_tool("qc_get_inspection")
    def qc_get_inspection(inspection_id: str) -> Dict[str, Any]:
        """
        Get a QC inspection result with all findings.

        Parameters:
            inspection_id: The inspection ID (e.g., 'QCI-0001')

        Returns:
            Inspection record with model decision, confidence, reason, and findings list.
        """
        return qc_service.get_inspection(inspection_id=inspection_id)

    # MUTATING TOOL
    @mcp.tool(name="qc_attach_images", meta={
        "tags": ["quality"],
        "ui": {
            "resourceUri": "ui://qc-inspection/result",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("qc_attach_images")
    def qc_attach_images(
        batch_id: str,
        image_data: List[str],
        uploaded_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Attach evidence images to a QC hold batch and immediately run the AI inspection.
        💡 Prefer qc_submit_image for the demo flow — it reads the MO label automatically.
        Use this tool only when you already have the QCB batch ID.

        Parameters:
            batch_id: The QC hold batch ID (e.g., 'QCB-0001')
            image_data: List of base64-encoded image strings or data URIs
            uploaded_by: Optional identifier of the operator uploading the images

        Returns:
            Inspection record with model decision, confidence, reason, and findings.
        """
        blobs = []
        for img_str in image_data:
            if img_str.startswith("data:"):
                _, b64data = img_str.split(",", 1)
                blobs.append(base64.b64decode(b64data))
            else:
                blobs.append(base64.b64decode(img_str))
        return qc_service.attach_images(
            batch_id=batch_id,
            image_blobs=blobs,
            uploaded_by=uploaded_by,
        )

    # MUTATING TOOL
    @mcp.tool(name="qc_run_inspection", meta={
        "tags": ["quality"],
        "ui": {
            "resourceUri": "ui://qc-inspection/result",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("qc_run_inspection")
    def qc_run_inspection(batch_id: str) -> Dict[str, Any]:
        """
        Run AI image inspection for a QC hold batch.
        Compares operator-submitted images against the reference product image.
        Requires images to be attached first (qc_attach_images).

        Parameters:
            batch_id: The QC hold batch ID (e.g., 'QCB-0001')

        Returns:
            Inspection record with model decision, confidence, and findings.
        """
        return qc_service.run_inspection(batch_id=batch_id)

    # MUTATING TOOL — returns confirmation payload for human approval
    @mcp.tool(name="qc_apply_disposition", meta={
        "tags": ["quality"],
        "ui": {
            "resourceUri": "ui://generic-confirm/dialog",
            "visibility": ["model", "app"]
        }
    }, structured_output=False)
    @log_tool("qc_apply_disposition")
    def qc_apply_disposition(
        qc_inspection_id: str,
        action: str,
        qty_scrapped: int = 0,
        approved_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Apply a QC disposition after inspection. Requires human confirmation.

        Parameters:
            qc_inspection_id: The inspection ID to dispose (e.g., 'QCI-0001')
            action: Disposition action — pass_release, partial_scrap, or full_scrap
            qty_scrapped: Number of units to scrap (required for partial_scrap)
            approved_by: Name or ID of the approving person
            reason: Reason for the disposition decision

        Returns:
            Confirmation metadata for the disposition action.
        """
        # Fetch inspection to show context in confirmation dialog
        try:
            inspection = qc_service.get_inspection(inspection_id=qc_inspection_id)
        except ValueError:
            inspection = {}

        arguments = {
            "qc_inspection_id": qc_inspection_id,
            "action": action,
            "qty_scrapped": qty_scrapped,
            "approved_by": approved_by,
            "reason": reason,
        }

        field_configs = [
            {"name": "qc_inspection_id", "label": "Inspection ID", "type": "text",
             "value": qc_inspection_id, "required": True, "display_order": 1},
            {"name": "batch_id", "label": "Hold Batch ID", "type": "text",
             "value": inspection.get("qc_hold_batch_id"), "display_order": 2},
            {"name": "decision", "label": "Model Decision", "type": "text",
             "value": inspection.get("decision"), "display_order": 3},
            {"name": "action", "label": "Disposition Action", "type": "options",
             "value": action, "required": True, "display_order": 4,
             "options": ["pass_release", "partial_scrap", "full_scrap"]},
            {"name": "qty_scrapped", "label": "Qty to Scrap", "type": "number",
             "value": qty_scrapped, "display_order": 5},
            {"name": "approved_by", "label": "Approved By", "type": "text",
             "value": approved_by, "display_order": 6},
            {"name": "reason", "label": "Reason", "type": "textarea",
             "value": reason, "display_order": 7},
        ]

        return create_confirmation_response(
            tool_name="qc_apply_disposition",
            title=f"Apply QC Disposition: {action}",
            description="This will apply the QC disposition. For scrap actions, a replacement production order will be created automatically.",
            field_configs=field_configs,
            arguments=arguments,
            category="quality",
        )
