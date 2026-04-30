"""MCP tools for image-based document import."""

import json
from typing import Optional

from mcp.types import CallToolResult, TextContent
from mcp_tools._common import log_tool
from services.image_import import image_import_service
from services.data_import import data_import_service


def _build_rows_response(result: dict):
    """Build a data-import-rows response for a resolved sales order.

    Creates an import job from the extracted lines so the user can
    manipulate them in the data-import-rows UI before executing.
    """
    resolved = result.get("resolved")
    if not resolved:
        return None

    customer = resolved.get("customer", {})
    lines = resolved.get("resolved_lines", [])
    unresolved = resolved.get("unresolved_lines", [])

    # Need at least some lines
    if not lines and not unresolved:
        return None

    # Build rows for the import job
    import_lines = []
    for ln in lines:
        import_lines.append({
            "sku": ln.get("sku", ""),
            "qty": ln.get("quantity", 1),
            "product_name": ln.get("name", ln.get("original_description", "")),
        })
    for ln in unresolved:
        import_lines.append({
            "sku": "",
            "qty": ln.get("quantity", 1),
            "product_name": ln.get("original_description", ""),
        })

    # Create the import job
    state = data_import_service.create_from_image(
        lines=import_lines,
        customer_id=customer.get("id"),
        customer_name=customer.get("name"),
        delivery_date=resolved.get("date"),
        notes=resolved.get("notes"),
    )

    cust_info = f"customer {customer['name']} ({customer['id']})" if customer.get("id") else f"customer \"{customer.get('name', 'unknown')}\" (not resolved)"
    return CallToolResult(
        content=[TextContent(
            type="text",
            text=(
                f"Sales order imported from image. Job {state['job_id']} created with "
                f"{state['row_count']} lines for {cust_info}. "
                f"The data-import rows UI is now open for the user to review and edit lines before executing."
            ),
        )],
        structuredContent=state,
        isError=False,
    )


def _build_text_result(result: dict) -> str:
    """Build a text result describing what was extracted and what needs to happen."""
    doc_type = result.get("document_type", "unknown")
    confidence = result.get("confidence", 0.0)
    resolved = result.get("resolved")

    if doc_type == "unknown" or not resolved:
        return (
            f"Could not extract structured data from this image "
            f"(detected type: {doc_type}, confidence: {confidence:.0%}).\n"
            "Please provide a clearer image or add a hint about the document content."
        )

    customer = resolved.get("customer", {})
    lines = resolved.get("resolved_lines", [])
    unresolved = resolved.get("unresolved_lines", [])
    date = resolved.get("date")

    parts = [f"📋 **Extracted Sales Order** (confidence: {confidence:.0%})\n"]

    # Customer section
    if customer.get("id"):
        parts.append(f"**Customer:** {customer['name']} ({customer['id']}) ✓")
    else:
        parts.append(f"**Customer:** ⚠️ \"{customer.get('name', '?')}\" — NOT FOUND in system")
        parts.append(f"  → Please create this customer first using `crm_create_customer`")

    if date:
        parts.append(f"**Delivery date:** {date}")

    # Lines section
    if lines:
        parts.append(f"\n**Resolved lines ({len(lines)}):**")
        for ln in lines:
            conf = "✓" if ln.get("confidence", 0) >= 0.8 else f"~{ln.get('confidence', 0):.0%}"
            parts.append(f"  • {ln['quantity']}× {ln['sku']} ({ln['name']}) {conf}")

    if unresolved:
        parts.append(f"\n**Unresolved lines ({len(unresolved)}):**")
        for ln in unresolved:
            parts.append(f"  • {ln['quantity']}× \"{ln['original_description']}\" — no matching SKU found")

    # Next steps
    parts.append("\n**Next steps:**")
    if not customer.get("id"):
        parts.append("1. Create customer using `crm_create_customer`")
        parts.append("2. Then call `image_import_upload` again with the same image.")
    else:
        parts.append("All entities resolved — the data import rows UI should be open for editing.")

    return "\n".join(parts)


def register(mcp):
    """Register image import tools."""

    @mcp.tool(
        name="image_import_upload",
        meta={
            "tags": ["sales", "data_import"],
            "ui": {
                "resourceUri": "ui://data-import/rows",
                "visibility": ["model", "app"],
            },
        },
        structured_output=False,
    )
    @log_tool("image_import_upload")
    def image_import_upload(
        image: str,
        hint: Optional[str] = None,
    ) -> dict:
        """Import a document from a photo or scanned image.

        Takes a picture of an order form, customer list, invoice, or similar
        business document. The system extracts structured data using AI vision,
        resolves entities (customers, products) against the ERP database, and
        opens the data import rows UI for the user to review and edit lines
        before creating the order.

        Parameters:
            image: Image as a base64 string, data URI ('data:image/png;base64,...'),
                   file path URL ('file:///path/to/image.png'), or plain file path
            hint: Optional hint about the document (e.g. 'this is a sales order
                  from Quack Corp')

        Returns:
            Opens the data-import rows UI if entities are resolved,
            or returns a text description of what needs to happen first.
        """
        result = image_import_service.upload_image(image=image, hint=hint)

        # If resolved, create import job and open rows UI
        if result.get("document_type") == "sales_order" and result.get("resolved"):
            rows_response = _build_rows_response(result)
            if rows_response:
                return rows_response

        # Otherwise return text instructions for the agent
        return _build_text_result(result)
