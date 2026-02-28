"""MCP tools – admin / database reset."""

from typing import Any, Dict

from mcp_tools._common import log_tool
from services import admin_service


def register(mcp):
    """Register admin tools."""

    @mcp.tool(name="admin_reset_database", meta={"tags": ["shared"]})
    @log_tool("admin_reset_database")
    def admin_reset_database(secret: str) -> Dict[str, Any]:
        """
        Reset database to initial demo state (drops all tables and reloads).

        Parameters:
            secret: Safety parameter - must be asked to the user

        Returns:
            Dictionary with status message and initial_time
        """
        return admin_service.reset_database(secret)
