"""Common utilities shared across MCP tool modules."""

import functools
import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from mcp.types import CallToolResult, TextContent

logger = logging.getLogger("duck-demo")

# ---------------------------------------------------------------------------
# Tool → activity_log mapping for mutating business actions
# Only tools listed here produce activity_log entries.
# ---------------------------------------------------------------------------
TOOL_ACTION_MAP: Dict[str, tuple] = {
    # tool_name → (category, action)
    "sales_confirm_order":       ("sales",      "sales_order.confirmed"),
    "sales_price_order":         ("sales",      "sales_order.priced"),
    "production_create_order":   ("production", "production_order.created"),
    "production_start_order":    ("production", "production_order.started"),
    "production_complete_order": ("production", "production_order.completed"),
    "logistics_create_shipment": ("logistics",  "shipment.created"),
    "invoice_create":            ("billing",    "invoice.created"),
    "invoice_issue":             ("billing",    "invoice.issued"),
    "invoice_record_payment":    ("billing",    "payment.recorded"),
    "quote_create":              ("sales",      "quote.created"),
    "quote_send":                ("sales",      "quote.sent"),
    "quote_accept":              ("sales",      "quote.accepted"),
    "quote_reject":              ("sales",      "quote.rejected"),
    "quote_revise":              ("sales",      "quote.revised"),
    "purchase_create_order":     ("purchasing",  "purchase_order.created"),
    "purchase_receive_order":    ("purchasing",  "purchase_order.received"),
    "purchase_restock_materials":("purchasing",  "purchase_orders.restocked"),
    "crm_create_customer":       ("sales",      "customer.created"),
    "crm_update_customer":       ("sales",      "customer.updated"),
    "messaging_send_email":      ("sales",      "email.sent"),
    "sales_link_shipment":       ("logistics",  "shipment.linked"),
}

# Keys in a tool result dict that identify an entity ID
_ENTITY_ID_KEYS = [
    "sales_order_id", "production_order_id", "shipment_id", "invoice_id",
    "quote_id", "purchase_order_id", "customer_id", "email_id", "payment_id",
]

# entity_id key → entity_type value
_KEY_TO_TYPE = {
    "sales_order_id": "sales_order",
    "production_order_id": "production_order",
    "shipment_id": "shipment",
    "invoice_id": "invoice",
    "quote_id": "quote",
    "purchase_order_id": "purchase_order",
    "customer_id": "customer",
    "email_id": "email",
    "payment_id": "payment",
}


def _extract_entity(result: Any) -> tuple:
    """Extract (entity_type, entity_id) from a tool result dict."""
    if isinstance(result, dict):
        for key in _ENTITY_ID_KEYS:
            val = result.get(key)
            if val:
                return _KEY_TO_TYPE.get(key, key.replace("_id", "")), str(val)
    return None, None


def log_tool(name: str):
    """Decorator to log tool calls with parameters and results.

    If the tool is in TOOL_ACTION_MAP, also writes an activity_log entry.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                params_str = json.dumps({"args": args, "kwargs": kwargs}, default=str)
            except Exception:
                params_str = f"args={args}, kwargs={kwargs}"
            logger.info("[CallToolRequest] tool=%s params=%s", name, params_str)
            try:
                result = func(*args, **kwargs)
                try:
                    result_str = json.dumps(result, default=str)
                except Exception:
                    result_str = str(result)
                logger.info("[CallToolResponse] tool=%s result=%s", name, result_str)

                # Write activity_log for mapped mutating tools
                mapping = TOOL_ACTION_MAP.get(name)
                if mapping:
                    try:
                        from services.activity import log_activity
                        category, action = mapping
                        entity_type, entity_id = _extract_entity(result)
                        # Derive actor from tool name prefix
                        actor = f"mcp:{name.split('_')[0]}" if "_" in name else "mcp"
                        log_activity(actor, category, action, entity_type, entity_id)
                    except Exception:
                        logger.debug("activity_log write failed for tool %s", name, exc_info=True)

                return result
            except Exception as exc:
                logger.exception("[CallToolError] tool=%s error=%s", name, exc)
                raise
        return wrapper
    return decorator


# ==================== Confirmation System Types ====================

class FieldMetadata(TypedDict, total=False):
    """Metadata for a single field in a confirmation dialog."""
    name: str
    label: str
    type: str
    value: Any
    required: bool
    help_text: str
    group: str
    display_order: int
    options: List[str]


class ConfirmationMetadata(TypedDict):
    """Complete metadata for a confirmation dialog."""
    original_tool: str
    title: str
    description: str
    category: str
    fields: List[FieldMetadata]
    arguments: Dict[str, Any]


def create_confirmation_response(
    tool_name: str,
    title: str,
    description: str,
    field_configs: List[Dict[str, Any]],
    arguments: Dict[str, Any],
    category: str = "general"
) -> CallToolResult:
    """
    Helper to create standardized confirmation response.

    Args:
        tool_name: Name of the original tool (for routing back through dispatcher)
        title: Dialog title
        description: Action description shown to user
        field_configs: List of field configurations (each dict becomes a FieldMetadata)
        arguments: Original tool arguments (will be passed to dispatcher)
        category: Category for styling (customer, order, financial, etc.)

    Returns:
        CallToolResult with confirmation metadata for MCP App consumption
    """
    fields: List[FieldMetadata] = []
    for config in field_configs:
        field: FieldMetadata = {
            "name": config["name"],
            "label": config.get("label", config["name"].replace("_", " ").title()),
            "type": config.get("type", "text"),
            "value": config["value"],
            "required": config.get("required", False),
        }
        if "help_text" in config:
            field["help_text"] = config["help_text"]
        if "group" in config:
            field["group"] = config["group"]
        if "display_order" in config:
            field["display_order"] = config["display_order"]
        if "options" in config:
            field["options"] = config["options"]
        fields.append(field)

    metadata: ConfirmationMetadata = {
        "original_tool": tool_name,
        "title": title,
        "description": description,
        "category": category,
        "fields": fields,
        "arguments": arguments
    }

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=f"Please confirm action: **{title}**"
            )
        ],
        structuredContent=metadata,
        isError=False
    )
