"""MCP tools – simulation time management."""

from typing import Any, Dict, Optional

from mcp_tools._common import log_tool
from services import simulation_service


def register(mcp):
    """Register simulation tools."""

    @mcp.tool(name="simulation_get_time", meta={"tags": ["shared"]})
    @log_tool("simulation_get_time")
    def simulation_get_time() -> Dict[str, Any]:
        """
        Get the current simulated time.

        Returns:
            Dictionary with current_time (ISO format string)
        """
        return {"current_time": simulation_service.get_current_time()}

    @mcp.tool(name="simulation_advance_time", meta={"tags": ["shared"]})
    @log_tool("simulation_advance_time")
    def simulation_advance_time(
        hours: Optional[float] = None,
        days: Optional[int] = None,
        to_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Advance the simulated time forward.

        Parameters:
            hours: Number of hours to advance (e.g., 2.5)
            days: Number of days to advance (e.g., 7)
            to_time: ISO datetime to set time to (e.g., '2025-01-15 14:00:00')

        Returns:
            Dictionary with old_time and new_time
        """
        return simulation_service.advance_time(hours, days, to_time)
