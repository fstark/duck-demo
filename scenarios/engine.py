"""Scenario engine — orchestrator for story-driven demo data generation.

Resets the database, runs base_setup, then executes scenario modules in
chronological order.  Each scenario module must expose a ``run(ctx)`` function
that receives a context dict (customer IDs, SKU pools, etc.) and returns
a summary dict.

Usage:
    python -m scenarios                     # run all scenarios
    python -m scenarios --only s01,s02      # run selected scenarios
    python -m scenarios --base-only         # base setup only (no scenarios)
"""

import argparse
import importlib
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from db import DB_PATH, init_db, get_connection
from services._base import db_conn

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scenarios.engine")

# ---------------------------------------------------------------------------
# Available scenario modules (in chronological order)
# ---------------------------------------------------------------------------

SCENARIO_MODULES = [
    "s01_steady_state",
    "s02_halloween_spike",
    "s03_material_shortage",
    "s04_geo_expansion",
    "s05_price_revision",
    "s06_new_year_recovery",
]

# ---------------------------------------------------------------------------
# DB reset (without re-seeding old data)
# ---------------------------------------------------------------------------

def reset_database() -> None:
    """Drop all tables and recreate schema from schema.sql.

    Unlike AdminService.reset_database(), this does NOT re-seed with
    seed_demo.py data — we want a blank slate for the scenario framework.
    """
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()

    # Initialize simulation_state row (required by SimulationService)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO simulation_state (id, sim_time) VALUES (1, '2025-01-01 00:00:00')"
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("Database reset — schema recreated at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Summary / verification
# ---------------------------------------------------------------------------

def print_summary() -> None:
    """Query entity counts and print a summary table."""
    tables = [
        ("customers", "Customers"),
        ("items", "Items"),
        ("recipes", "Recipes"),
        ("suppliers", "Suppliers"),
        ("stock", "Stock rows"),
        ("sales_orders", "Sales Orders"),
        ("production_orders", "Production Orders"),
        ("purchase_orders", "Purchase Orders"),
        ("invoices", "Invoices"),
        ("quotes", "Quotes"),
        ("shipments", "Shipments"),
        ("emails", "Emails"),
        ("payments", "Payments"),
    ]
    with db_conn() as conn:
        sim_time = conn.execute("SELECT sim_time FROM simulation_state WHERE id = 1").fetchone()[0]
        print("\n" + "=" * 50)
        print("  SCENARIO ENGINE — SUMMARY")
        print("=" * 50)
        for table, label in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {label:<22} {count:>6}")
        print("-" * 50)
        print(f"  Simulation time:  {sim_time}")
        print("=" * 50 + "\n")


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def run_scenarios(
    only: Optional[List[str]] = None,
    base_only: bool = False,
) -> None:
    """Main orchestration: reset → base_setup → scenarios."""

    t0 = time.time()

    # 1. Reset
    logger.info("Step 1/3: Resetting database...")
    reset_database()

    # 2. Base setup
    logger.info("Step 2/3: Running base_setup...")
    from scenarios import base_setup
    base_result = base_setup.populate()

    # Build context dict that scenarios can use
    ctx: Dict = {
        "customer_ids": base_result["customer_ids"],
        "base_result": base_result,
    }

    if base_only:
        logger.info("--base-only specified, skipping scenarios")
        print_summary()
        elapsed = time.time() - t0
        logger.info("Done in %.1fs", elapsed)
        return

    # 3. Scenarios
    logger.info("Step 3/3: Running scenarios...")

    modules_to_run = SCENARIO_MODULES
    if only:
        # Filter: accept "s01", "s01_steady_state", etc.
        modules_to_run = []
        for name in only:
            name = name.strip()
            matched = [m for m in SCENARIO_MODULES if m.startswith(name)]
            if matched:
                modules_to_run.extend(matched)
            else:
                logger.warning("No scenario matching '%s' — skipping", name)

    for module_name in modules_to_run:
        fq_name = f"scenarios.{module_name}"
        try:
            mod = importlib.import_module(fq_name)
        except ModuleNotFoundError:
            logger.warning("Scenario module %s not found — skipping", fq_name)
            continue

        if not hasattr(mod, "run"):
            logger.warning("Scenario %s has no run(ctx) function — skipping", fq_name)
            continue

        logger.info("Running %s ...", module_name)
        try:
            result = mod.run(ctx)
            if isinstance(result, dict):
                ctx.update(result)  # scenarios can pass data downstream
            logger.info("Completed %s", module_name)
        except Exception:
            logger.exception("FAILED: %s", module_name)
            raise

    print_summary()
    elapsed = time.time() - t0
    logger.info("All done in %.1fs", elapsed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Story-driven demo data generator for Duck Inc."
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of scenario prefixes to run (e.g. s01,s02)",
    )
    parser.add_argument(
        "--base-only",
        action="store_true",
        help="Only run base_setup (no scenarios)",
    )
    args = parser.parse_args()

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    run_scenarios(only=only, base_only=args.base_only)


if __name__ == "__main__":
    main()
