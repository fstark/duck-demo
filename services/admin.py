"""Service for admin operations."""

from typing import Any, Dict

from services._base import db_conn


class AdminService:
    """Service for admin operations."""

    @staticmethod
    def reset_database(confirm: str) -> Dict[str, Any]:
        """Reset database to initial demo state."""
        if confirm != "kondor":
            raise ValueError("Invalid confirmation")
        from seed_demo import seed
        with db_conn() as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
            for table in tables:
                conn.execute(f"DROP TABLE IF EXISTS {table[0]}")
            conn.commit()
        seed(from_admin=True)
        return {"status": "Database reset complete", "initial_time": "2025-12-24 08:30:00"}


admin_service = AdminService()
