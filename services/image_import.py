"""Service for image-based document import.

Accepts a photo (printed order, handwritten list, business card, etc.),
extracts structured data via a vision LLM, resolves entities against
the existing database, and returns a suggested action the agent can execute.

Supported document types:
  - sales_order: customer + line items → quote_create arguments
  (more types can be added by extending _DOCUMENT_RESOLVERS)
"""

import base64
import json
import logging
import os
import re
import urllib.parse

import config
from services._base import db_conn
from services.myforterro import chat_completion

logger = logging.getLogger("duck-demo")


# ---------------------------------------------------------------------------
# Image input handling (same formats as QC)
# ---------------------------------------------------------------------------

def _read_image(image_input: str) -> tuple[bytes, str]:
    """Decode image input to raw bytes and MIME type.

    Accepts: base64 data URI, file:/// URL, plain file path, raw base64 string.
    """
    if image_input.startswith("data:"):
        _, b64data = image_input.split(",", 1)
        img_bytes = base64.b64decode(b64data)
    elif image_input.startswith("file://"):
        file_path = urllib.parse.unquote(urllib.parse.urlparse(image_input).path)
        # On Windows, strip leading slash before drive letter (e.g. /C:/...)
        if len(file_path) >= 3 and file_path[0] == "/" and file_path[2] == ":":
            file_path = file_path[1:]
        with open(file_path, "rb") as f:
            img_bytes = f.read()
    elif os.path.isfile(image_input):
        with open(image_input, "rb") as f:
            img_bytes = f.read()
    else:
        img_bytes = base64.b64decode(image_input)

    # Detect MIME from magic bytes
    if img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif img_bytes[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        mime = "image/jpeg"

    return img_bytes, mime


def _to_data_uri(img_bytes: bytes, mime: str) -> str:
    """Convert raw image bytes to a base64 data URI."""
    return f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


# ---------------------------------------------------------------------------
# Vision LLM extraction
# ---------------------------------------------------------------------------

def _extract_document_data(*, image_data_uri: str, hint: str | None = None) -> dict:
    """Call vision LLM to extract structured data from an image.

    Returns a dict with:
      - document_type: "sales_order", "customer_list", "unknown"
      - confidence: 0.0-1.0
      - data: extracted fields (structure depends on document_type)
    """
    hint_clause = ""
    if hint:
        hint_clause = f"\nHint from the user: {hint}\n"

    prompt = (
        "You are a data extraction expert for an ERP system.\n"
        "Analyse this image and extract all structured business data you can find.\n"
        f"{hint_clause}\n"
        "First, determine the document type. Possible types:\n"
        '- "sales_order": a customer order, purchase order, or order form with '
        "a customer/company name, optional date, and line items (products + quantities)\n"
        '- "customer_list": a list of customers/contacts with names, addresses, emails, etc.\n'
        '- "unknown": anything else\n\n'
        "Respond with ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "document_type": "sales_order | customer_list | unknown",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "data": { ... }\n'
        "}\n\n"
        'For "sales_order", data must contain:\n'
        "{\n"
        '  "customer_name": "string (company or person name)",\n'
        '  "date": "YYYY-MM-DD or null if not visible",\n'
        '  "lines": [\n'
        '    {"description": "product name/description as written", "quantity": integer}\n'
        "  ],\n"
        '  "notes": "any additional text visible on the document"\n'
        "}\n\n"
        'For "customer_list", data must contain:\n'
        "{\n"
        '  "columns": ["col1", "col2", ...],\n'
        '  "rows": [{"col1": "val1", "col2": "val2"}, ...]\n'
        "}\n"
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_uri}},
            ],
        }
    ]

    resp = chat_completion(
        model=config.IMAGE_IMPORT_MODEL,
        messages=messages,
    )

    text = _strip_code_fences(resp.choices[0].message.content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Vision LLM returned unparseable JSON: %s", text[:200])
        return {"document_type": "unknown", "confidence": 0.0, "data": {}}


# ---------------------------------------------------------------------------
# Entity resolution helpers
# ---------------------------------------------------------------------------

def _resolve_customer(*, name: str) -> dict:
    """Resolve a customer name against the database.

    Returns {id, name, confidence, alternatives}.
    """
    from services.customer import find_customers
    import difflib

    # Try name search first, then company search
    result = find_customers(name=name, limit=5)
    candidates = result.get("customers", [])

    if not candidates:
        result = find_customers(company=name, limit=5)
        candidates = result.get("customers", [])

    if not candidates:
        return {
            "id": None,
            "name": name,
            "confidence": 0.0,
            "alternatives": [],
            "message": f"No customer found matching '{name}'. Create the customer first.",
        }

    # Score candidates by name/company similarity
    scored = []
    for cust in candidates:
        name_score = difflib.SequenceMatcher(
            None, name.lower(), (cust.get("name") or "").lower()
        ).ratio()
        company_score = difflib.SequenceMatcher(
            None, name.lower(), (cust.get("company") or "").lower()
        ).ratio()
        score = max(name_score, company_score)
        scored.append((score, cust))

    scored.sort(key=lambda x: -x[0])
    best_score, best = scored[0]

    display_name = best.get("name") or best.get("company") or best["id"]

    return {
        "id": best["id"],
        "name": display_name,
        "confidence": round(best_score, 2),
        "alternatives": [
            {"id": c["id"], "name": c.get("name") or c.get("company") or c["id"], "confidence": round(s, 2)}
            for s, c in scored[1:4]
        ],
    }


def _resolve_line_item(*, description: str) -> dict:
    """Resolve a product description to a catalog SKU.

    Returns {sku, name, confidence, alternatives}.
    """
    from services.catalog import search_items

    # Tokenize the description for search
    words = re.split(r"[^a-zA-Z0-9]+", description)
    words = [w for w in words if w]

    if not words:
        return {
            "sku": None,
            "name": description,
            "confidence": 0.0,
            "alternatives": [],
            "message": f"Could not parse product description: '{description}'",
        }

    try:
        result = search_items(words=words, limit=5, min_score=1)
    except ValueError:
        return {
            "sku": None,
            "name": description,
            "confidence": 0.0,
            "alternatives": [],
            "message": f"No products found matching '{description}'",
        }

    items = result.get("items", [])
    if not items:
        return {
            "sku": None,
            "name": description,
            "confidence": 0.0,
            "alternatives": [],
            "message": f"No products found matching '{description}'",
        }

    # Use the search score to compute confidence
    best = items[0]
    max_possible = len(words)
    confidence = min(1.0, best["score"] / max(max_possible, 1))

    return {
        "sku": best["item"]["sku"],
        "name": best["item"]["name"],
        "confidence": round(confidence, 2),
        "alternatives": [
            {"sku": it["item"]["sku"], "name": it["item"]["name"], "confidence": round(min(1.0, it["score"] / max(max_possible, 1)), 2)}
            for it in items[1:4]
        ],
    }


# ---------------------------------------------------------------------------
# Document type resolvers
# ---------------------------------------------------------------------------

def _resolve_sales_order(*, data: dict) -> dict:
    """Resolve a sales_order extraction into quote_create arguments."""
    customer_name = data.get("customer_name", "")
    date = data.get("date")
    raw_lines = data.get("lines", [])
    notes = data.get("notes", "")

    # Resolve customer
    customer = _resolve_customer(name=customer_name)

    # Resolve each line item
    resolved_lines = []
    unresolved_lines = []
    for line in raw_lines:
        desc = line.get("description", "")
        qty = line.get("quantity", 1)
        match = _resolve_line_item(description=desc)
        resolved_line = {
            "original_description": desc,
            "quantity": int(qty),
            **match,
        }
        if match["sku"]:
            resolved_lines.append(resolved_line)
        else:
            unresolved_lines.append(resolved_line)

    # Build suggested quote_create arguments (only if customer resolved)
    suggested_action = None
    if customer["id"] and resolved_lines:
        quote_lines = [
            {"sku": ln["sku"], "qty": ln["quantity"]}
            for ln in resolved_lines
        ]
        args = {
            "customer_id": customer["id"],
            "lines": quote_lines,
        }
        if date:
            args["requested_delivery_date"] = date
        if notes:
            args["note"] = notes

        suggested_action = {
            "tool": "quote_create",
            "arguments": args,
        }

    return {
        "customer": customer,
        "date": date,
        "resolved_lines": resolved_lines,
        "unresolved_lines": unresolved_lines,
        "notes": notes,
        "suggested_action": suggested_action,
    }


_DOCUMENT_RESOLVERS = {
    "sales_order": _resolve_sales_order,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ImageImportService:
    """Image-based document import — extract, resolve, suggest action."""

    def upload_image(self, *, image: str, hint: str | None = None) -> dict:
        """Extract structured data from an image and resolve entities.

        Parameters:
            image: Image as base64 data URI, file:/// URL, plain file path, or raw base64.
            hint: Optional hint about the document content.

        Returns:
            Extraction result with resolved entities and suggested next action.
        """
        # Read and encode image
        img_bytes, mime = _read_image(image)
        image_data_uri = _to_data_uri(img_bytes, mime)

        logger.info("[ImageImport] Extracting data from image (%s, %d bytes)", mime, len(img_bytes))

        # Extract structured data via vision LLM
        extraction = _extract_document_data(image_data_uri=image_data_uri, hint=hint)

        document_type = extraction.get("document_type", "unknown")
        confidence = extraction.get("confidence", 0.0)
        data = extraction.get("data", {})

        logger.info(
            "[ImageImport] Detected document_type=%s confidence=%.2f",
            document_type, confidence,
        )

        # Resolve entities based on document type
        resolver = _DOCUMENT_RESOLVERS.get(document_type)
        if resolver:
            resolved = resolver(data=data)
        else:
            resolved = None

        return {
            "document_type": document_type,
            "confidence": confidence,
            "extracted_data": data,
            "resolved": resolved,
        }


image_import_service = ImageImportService()
