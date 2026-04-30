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
                "resourceUri": "ui://data-import/mapping",
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
        and a sample preview is generated. The result appears in the mapping review
        panel where you can adjust mappings before confirming.

        Parameters:
            source: File path URL (file:///...) or inline content
            hint: Optional description of the data
        """
        return data_import_service.upload(source=source, hint=hint)

    # --- App-only tools ---

    @mcp.tool(name="data_import_preview_sample", meta={
        "tags": [],
        "ui": {"visibility": ["app"]}
    })
    @log_tool("data_import_preview_sample")
    def data_import_preview_sample(job_id: str, mapping: list[dict], global_instructions: str = "") -> dict:
        """Re-transform sample rows with an updated mapping.

        Called by the mapping review app when the user edits column mappings.
        Returns 5 sample rows with both raw and mapped values.

        Args:
            job_id: Import job ID (e.g. "IMP-001")
            mapping: Updated mapping array with source/target/transform entries
            global_instructions: Optional user instructions about data conventions
        """
        return data_import_service.preview_sample(job_id=job_id, mapping=mapping, global_instructions=global_instructions)

    @mcp.tool(
        name="data_import_confirm_mapping",
        meta={
            "tags": [],
            "ui": {"visibility": ["app"]},
        },
    )
    @log_tool("data_import_confirm_mapping")
    def data_import_confirm_mapping(
        job_id: str,
        mapping: list[dict],
        global_instructions: str = "",
    ) -> dict:
        """Confirm the column mapping and proceed to row review.

        Persists the final mapping and global instructions. Returns a short
        status message that the agent uses to proceed to the next step.

        Args:
            job_id: Import job ID
            mapping: Final mapping array (user may have edited targets/transforms)
            global_instructions: Free-text instructions for interpreting the data
        """
        return data_import_service.confirm_mapping(
            job_id=job_id, mapping=mapping, global_instructions=global_instructions,
        )

    @mcp.tool(
        name="data_import_start_processing",
        meta={
            "tags": ["data_import"],
            "ui": {
                "resourceUri": "ui://data-import/rows",
                "visibility": ["model", "app"],
            },
        },
        structured_output=False,
    )
    @log_tool("data_import_start_processing")
    def data_import_start_processing(job_id: str) -> dict:
        """Start processing an import job and open the row review UI.

        Call this after confirm_mapping returns status='mapped'. Triggers
        the full transform/validate/resolve pipeline in the background and
        opens the row review panel.

        Args:
            job_id: Import job ID (e.g. "IMP-0009")
        """
        return data_import_service.start_processing(job_id=job_id)

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

    @mcp.tool(name="data_import_set_cell", meta={
        "tags": [],
        "ui": {"visibility": ["app"]}
    })
    @log_tool("data_import_set_cell")
    def data_import_set_cell(job_id: str, source_row: int, field: str, value: str) -> dict:
        """Directly set a cell value in a row's mapped data.

        Called by the MCP app when the user edits a cell inline.

        Args:
            job_id: Import job ID (e.g. "IMP-001")
            source_row: The source row number to edit
            field: The target field name (column) to set
            value: The new value for the cell
        """
        return data_import_service.set_cell(job_id=job_id, source_row=source_row, field=field, value=value)

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
