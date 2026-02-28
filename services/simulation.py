"""Service for managing simulated time."""

from typing import Any, Dict, Optional

from services._base import db_conn


class SimulationService:
    """Service for managing simulated time."""

    @staticmethod
    def get_current_time() -> str:
        """Get current simulation time."""
        with db_conn() as conn:
            result = conn.execute(
                "SELECT sim_time FROM simulation_state WHERE id = 1"
            ).fetchone()
            return result[0]

    @staticmethod
    def advance_time(
        hours: Optional[float] = None,
        days: Optional[int] = None,
        to_time: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Advance the simulated time forward.

        Args:
            hours: Number of hours to advance
            days: Number of days to advance
            to_time: ISO datetime to set time to

        Returns:
            Dictionary with old_time and new_time
        """
        with db_conn() as conn:
            old_time = conn.execute(
                "SELECT sim_time FROM simulation_state WHERE id = 1"
            ).fetchone()[0]

            if to_time:
                conn.execute(
                    "UPDATE simulation_state SET sim_time = ? WHERE id = 1",
                    (to_time,)
                )
            elif hours:
                conn.execute(
                    "UPDATE simulation_state SET sim_time = datetime(sim_time, ? || ' hours') WHERE id = 1",
                    (f'+{hours}',)
                )
            elif days:
                conn.execute(
                    "UPDATE simulation_state SET sim_time = datetime(sim_time, ? || ' days') WHERE id = 1",
                    (f'+{days}',)
                )
            else:
                raise ValueError("Must specify hours, days, or to_time")

            conn.commit()

            new_time = conn.execute(
                "SELECT sim_time FROM simulation_state WHERE id = 1"
            ).fetchone()[0]

            # Auto-mark overdue invoices based on new sim time
            overdue_count = conn.execute(
                "UPDATE invoices SET status = 'overdue' "
                "WHERE status = 'issued' AND due_date IS NOT NULL AND due_date < ?",
                (new_time[:10],)
            ).rowcount
            conn.commit()

            result = {
                "old_time": old_time,
                "new_time": new_time
            }
            if overdue_count > 0:
                result["invoices_marked_overdue"] = overdue_count
            return result


simulation_service = SimulationService()
