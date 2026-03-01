"""Utility functions for the duck-demo application."""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote
import config


# ---------------------------------------------------------------------------
# Address helpers — single source of truth for dict ↔ DB column mapping
# ---------------------------------------------------------------------------

_SHIP_TO_FIELDS = ("line1", "line2", "postal_code", "city", "country")
"""Canonical dict keys for a ship-to address."""


def ship_to_columns(ship_to: Optional[Dict[str, Any]]) -> Tuple:
    """Return a tuple of DB values (line1, line2, postal_code, city, country)
    ready to splice into an INSERT statement."""
    if not ship_to:
        return (None, None, None, None, None)
    return tuple(ship_to.get(k) for k in _SHIP_TO_FIELDS)


def ship_to_dict(row: Any) -> Optional[Dict[str, str]]:
    """Reconstruct a ship-to dict from a DB row with ``ship_to_*`` columns.
    Returns *None* if ``ship_to_line1`` is empty."""
    if not row["ship_to_line1"]:
        return None
    return {k: row[f"ship_to_{k}"] for k in _SHIP_TO_FIELDS}


def customer_to_ship_to(row: Any) -> Dict[str, str]:
    """Build a ship-to dict from a customers DB row."""
    return {
        "line1": row["address_line1"] or "",
        "line2": row["address_line2"] or "",
        "postal_code": row["postal_code"] or "",
        "city": row["city"] or "",
        "country": row["country"] or "FR",
    }


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
    return f"{config.API_BASE}#/{page}/{safe_id}"


def format_qty(value: int, uom: str) -> str:
    """Format an integer quantity for human-readable display.

    All quantities are stored in their smallest base unit:
    - grams ("g")  → displayed as kg when ≥ 1000 (e.g. 2400 → "2.4 kg")
    - millilitres ("ml") → displayed as L when ≥ 1000 (e.g. 1500 → "1.5 L")
    - anything else (e.g. "ea") → "{value} {uom}"

    Always returns an integer-clean number (no trailing ".0").
    """
    if uom == "g" and value >= 1000:
        kg = value / 1000
        fmt = f"{kg:g}"
        return f"{fmt} kg"
    if uom == "ml" and value >= 1000:
        litres = value / 1000
        fmt = f"{litres:g}"
        return f"{fmt} L"
    return f"{value} {uom}"
