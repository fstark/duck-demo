"""MCP tools – current user info."""

from typing import Any, Dict

from mcp_tools._common import log_tool


def register(mcp):
    """Register user-related tools."""

    @mcp.tool(name="user_get_current", meta={"tags": ["shared"]})
    @log_tool("user_get_current")
    def get_current_user() -> Dict[str, Any]:
        """Get current user information including first name, last name, role, and email."""
        return {
            "first_name": "Fred",
            "last_name": "Stark",
            "role": "Duck Inc Sales",
            "email": "fred.stark@rubberducks.ia"
        }
