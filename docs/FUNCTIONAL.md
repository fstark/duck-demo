This is a demo erp, focused on providing a set of mcp endpoint to prototype agents.

This erp only suport build-to-order workflows.

There is no authentication, authorization, or permissions system. All endpoints are open and unprotected by design.

The data is re-generated on each run from ``python -m scenarios --only s01`` to provide a consistent starting point.

The UI is read-only. All mutating actions are designed to be triggered by agents via the MCP interface.
