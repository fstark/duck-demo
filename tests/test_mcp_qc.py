"""MCP tool contract tests – QC tools."""

import pytest

pytestmark = pytest.mark.mcp


def _call(mcp_app, tool_name, **kwargs):
    tool = mcp_app._tool_manager._tools[tool_name]
    return tool.fn(**kwargs)


# ── Read tools ──────────────────────────────────────────────────────────────

def test_qc_list_pending_batches_returns_list(mcp_app):
    result = _call(mcp_app, "qc_list_pending_inspections")
    assert isinstance(result, list)


def test_qc_list_pending_batches_has_seeded_batch(mcp_app):
    result = _call(mcp_app, "qc_list_pending_inspections")
    ids = [b["id"] for b in result]
    assert "QCB-T001" in ids


def test_qc_get_batch_returns_detail(mcp_app):
    result = _call(mcp_app, "qc_get_batch", batch_id="QCB-T001")
    assert isinstance(result, dict)
    assert result["id"] == "QCB-T001"
    assert "lines" in result


def test_qc_get_batch_unknown_raises(mcp_app):
    with pytest.raises((ValueError, Exception)):
        _call(mcp_app, "qc_get_batch", batch_id="QCB-DOES-NOT-EXIST")


# ── Mutation tools return confirmation payload ───────────────────────────────

def test_qc_apply_disposition_returns_confirmation(mcp_app):
    """qc_apply_disposition should return a confirmation payload (not apply immediately)."""
    result = _call(mcp_app, "qc_apply_disposition",
                   qc_inspection_id="QCI-T001",
                   action="pass_release")
    # With structured_output=False, FastMCP wraps in CallToolResult
    # The structuredContent contains our confirmation payload
    assert result is not None
    assert not result.isError
    assert result.structuredContent is not None
    assert result.structuredContent.get("original_tool") == "qc_apply_disposition"
    assert "fields" in result.structuredContent
