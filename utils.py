"""Utility functions for the duck-demo application."""

from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote
import os


UI_BASE = os.getenv("UI_BASE", "http://127.0.0.1:5173")


def parse_date(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO date string to datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def eta_from_days(days: int) -> str:
    """Calculate ETA date string from days offset."""
    return (datetime.utcnow().date() + timedelta(days=days)).isoformat()


def ui_href(page: str, identifier: str) -> str:
    """Generate UI deep link URL."""
    safe_id = quote(str(identifier), safe="")
    return f"{UI_BASE}#/{page}/{safe_id}"
