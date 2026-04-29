"""MCP tools for data import."""

from mcp_tools._common import log_tool
from services.data_import import data_import_service


def register(mcp):
    """Register data import tools."""

    # --- Agent-facing tool (visibility: model + app) ---

    @mcp.tool(
        name="data_import_upload",
        meta={
            "tags": ["data_import"],
            "ui": {
                "resourceUri": "ui://data-import/result",
                "visibility": ["model", "app"],
            },
        },
        structured_output=False,
    )
    @log_tool("data_import_upload")
    def data_import_upload(
        source: str,
        hint: str | None = None,
    ) -> dict:
        """Upload a file for import into the ERP.

        The file is parsed, the entity type is auto-detected, columns are mapped,
        transforms are applied, validation and entity resolution are run — all in
        one call. The result appears in the interactive import panel where you can
        review and fix issues before importing.

        Parameters:
            source: File path URL (file:///...) or inline content
            hint: Optional description of the data
        """
        return data_import_service.upload(source=source, hint=hint)

    # --- App-only tools (not exposed to agents) ---

    @mcp.tool(name="data_import_fix", meta={
        "tags": [],
        "ui": {"visibility": ["app"]}
    })
    @log_tool("data_import_fix")
    def data_import_fix(job_id: str, instruction: str) -> dict:
        """Interpret a free-text fix instruction and apply it to staging data.

        Called by the MCP app when the user types in the Fix field.

        Args:
            job_id: Import job ID (e.g. "IMP-001")
            instruction: Free-text fix instruction
        """
        return data_import_service.fix(job_id=job_id, instruction=instruction)

    @mcp.tool(name="data_import_execute", meta={
        "tags": [],
        "ui": {"visibility": ["app"]}
    })
    @log_tool("data_import_execute")
    def data_import_execute(job_id: str, exclude_columns: list[str] | None = None) -> dict:
        """Execute the import — create records in the ERP.

        Called by the MCP app when the user clicks Import.

        Args:
            job_id: Import job ID
            exclude_columns: Optional list of target column names to exclude from import
        """
        return data_import_service.execute(job_id=job_id, exclude_columns=exclude_columns)

    @mcp.tool(name="data_import_get_state", meta={
        "tags": [],
        "ui": {"visibility": ["app"]}
    })
    @log_tool("data_import_get_state")
    def data_import_get_state(job_id: str) -> dict:
        """Get the current staging state for an import job.

        Called by the MCP app to refresh state (e.g. after reconnect).

        Args:
            job_id: Import job ID
        """
        return data_import_service.get_state(job_id=job_id)
