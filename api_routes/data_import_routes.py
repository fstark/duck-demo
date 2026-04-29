"""API routes – data import jobs (read-only)."""

import json

from api_routes._common import _json, cors_handler
from db import dict_rows
from services._base import db_conn


def register(mcp):
    """Register data import routes."""

    @mcp.custom_route("/api/import-jobs", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_import_jobs(request):
        with db_conn() as conn:
            rows = dict_rows(conn.execute(
                "SELECT id, entity_type, source_filename, source_format, status, row_count, created_at, executed_at "
                "FROM import_jobs ORDER BY created_at DESC"
            ).fetchall())
        return _json({"import_jobs": rows})

    @mcp.custom_route("/api/import-jobs/{job_id}", methods=["GET", "OPTIONS"])
    @cors_handler(["GET"])
    async def api_import_job_detail(request):
        job_id = request.path_params.get("job_id")
        with db_conn() as conn:
            job = conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
            if not job:
                return _json({"error": "Import job not found"}, status_code=404)
            job = dict(job)

            rows = dict_rows(conn.execute(
                "SELECT id, source_row, raw_data, mapped_data, resolved_refs, status, issues, "
                "merged_into, created_entity_type, created_entity_id "
                "FROM import_rows WHERE job_id = ? ORDER BY source_row",
                (job_id,),
            ).fetchall())

        # Parse JSON fields on job
        job["columns_detected"] = json.loads(job["columns_detected"]) if job.get("columns_detected") else []
        job["mapping_plan"] = json.loads(job["mapping_plan"]) if job.get("mapping_plan") else None
        job["issues_summary"] = json.loads(job["issues_summary"]) if job.get("issues_summary") else {}
        # Remove source_content from detail (can be large)
        job.pop("source_content", None)

        # Parse JSON fields on rows
        for row in rows:
            row["raw_data"] = json.loads(row["raw_data"]) if row["raw_data"] else {}
            row["mapped_data"] = json.loads(row["mapped_data"]) if row["mapped_data"] else {}
            row["resolved_refs"] = json.loads(row["resolved_refs"]) if row["resolved_refs"] else {}
            row["issues"] = json.loads(row["issues"]) if row["issues"] else []

        job["rows"] = rows
        return _json(job)
