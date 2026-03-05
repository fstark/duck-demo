"""Service for the activity_log — persistent event stream for factory observability."""

import json
import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from db import generate_id
from services._base import db_conn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def log_activity(
    actor: str,
    category: str,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
) -> str:
    """Write a single activity_log row.

    Args:
        actor: Who performed the action ('scenario', 'system', 'mcp:sales', …).
        category: Business domain ('sales', 'production', 'logistics', 'purchasing', 'billing').
        action: Dot-notation event name ('sales_order.created', 'production_order.completed', …).
        entity_type: Optional entity table name ('sales_order', 'shipment', …).
        entity_id: Optional entity ID ('SO-1042', 'MO-0012', …).
        details: Optional JSON-serialisable context dict.
        timestamp: ISO string; defaults to current sim time.

    Returns:
        The generated activity_log ID.
    """
    with db_conn() as conn:
        if timestamp is None:
            row = conn.execute("SELECT sim_time FROM simulation_state WHERE id = 1").fetchone()
            timestamp = row[0] if row else ""
        act_id = generate_id(conn, "ACT", "activity_log")
        details_json = json.dumps(details, default=str) if details else None
        conn.execute(
            "INSERT INTO activity_log (id, timestamp, actor, category, action, entity_type, entity_id, details) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (act_id, timestamp, actor, category, action, entity_type, entity_id, details_json),
        )
        conn.commit()
    return act_id


def log_batch(entries: List[Dict[str, Any]]) -> int:
    """Bulk-insert activity_log rows for scenario efficiency.

    Each entry dict must contain: actor, category, action.
    Optional keys: entity_type, entity_id, details, timestamp.

    Returns:
        Count of rows inserted.
    """
    if not entries:
        return 0
    with db_conn() as conn:
        sim_time = conn.execute("SELECT sim_time FROM simulation_state WHERE id = 1").fetchone()
        default_ts = sim_time[0] if sim_time else ""
        for entry in entries:
            act_id = generate_id(conn, "ACT", "activity_log")
            details = entry.get("details")
            details_json = json.dumps(details, default=str) if details else None
            conn.execute(
                "INSERT INTO activity_log (id, timestamp, actor, category, action, entity_type, entity_id, details) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    act_id,
                    entry.get("timestamp", default_ts),
                    entry["actor"],
                    entry["category"],
                    entry["action"],
                    entry.get("entity_type"),
                    entry.get("entity_id"),
                    details_json,
                ),
            )
        conn.commit()
    return len(entries)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_log(
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_ids: Optional[List[str]] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> Dict[str, Any]:
    """Paginated, filterable activity log query.

    Returns:
        {"entries": [...], "total": int, "limit": int, "offset": int}
    """
    conditions: List[str] = []
    params: List[Any] = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if action:
        conditions.append("action = ?")
        params.append(action)
    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type)
    if entity_ids:
        placeholders = ','.join('?' * len(entity_ids))
        conditions.append(f"entity_id IN ({placeholders})")
        params.extend(entity_ids)
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)
    if until:
        conditions.append("timestamp <= ?")
        params.append(until)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with db_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM activity_log{where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM activity_log{where} ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    entries = []
    for r in rows:
        entry = dict(r)
        if entry.get("details"):
            try:
                entry["details"] = json.loads(entry["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        entries.append(entry)

    return {"entries": entries, "total": total, "limit": limit, "offset": offset}


def get_daily_summary(
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Aggregate log entries by date, category and action — for charts.

    Returns:
        List of {"date": "YYYY-MM-DD", "category": str, "action": str, "count": int}.
    """
    conditions: List[str] = []
    params: List[Any] = []
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)
    if until:
        conditions.append("timestamp <= ?")
        params.append(until)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with db_conn() as conn:
        rows = conn.execute(
            f"SELECT date(timestamp) as date, category, action, COUNT(*) as count "
            f"FROM activity_log{where} "
            f"GROUP BY date(timestamp), category, action "
            f"ORDER BY date(timestamp)",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

activity_service = SimpleNamespace(
    log_activity=log_activity,
    log_batch=log_batch,
    get_log=get_log,
    get_daily_summary=get_daily_summary,
)
ActivityService = activity_service
