"""Common helpers shared across API route modules."""

import logging
from typing import Any, Optional

from starlette.responses import JSONResponse, Response

logger = logging.getLogger("duck-demo")


DEMO_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "*",
}


def _json(data: Any, status_code: int = 200) -> JSONResponse:
    """Return JSON response with CORS headers."""
    return JSONResponse(data, status_code=status_code, headers=DEMO_CORS_HEADERS)


def _cors_preflight(methods: list) -> Response:
    """Handle CORS preflight requests."""
    headers = dict(DEMO_CORS_HEADERS)
    headers["Access-Control-Allow-Methods"] = ", ".join(methods)
    return Response(status_code=204, headers=headers)


def _parse_bool(val: Optional[str]) -> bool:
    """Parse boolean from query string."""
    if val is None:
        return False
    return val.lower() in {"1", "true", "yes", "y", "on"}
