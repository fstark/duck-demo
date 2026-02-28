"""Common utilities shared across MCP tool modules."""

import functools
import json
import logging
from typing import Any, Dict, List, TypedDict

from mcp.types import CallToolResult, TextContent

logger = logging.getLogger("duck-demo")


def log_tool(name: str):
    """Decorator to log tool calls with parameters and results."""
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
