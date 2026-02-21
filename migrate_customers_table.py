#!/usr/bin/env python3
"""Migration script to add new columns to customers table."""

import sqlite3
import sys

def migrate():
    """Add new columns to customers table if they don't exist."""
    try:
        conn = sqlite3.connect("demo.db")
        cursor = conn.cursor()
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(customers)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        
        # Columns to add with their definitions
        new_columns = [
            ("phone", "TEXT"),
            ("address_line1", "TEXT"),
            ("address_line2", "TEXT"),
            ("postal_code", "TEXT"),
            ("country", "TEXT DEFAULT 'FR'"),
            ("tax_id", "TEXT"),
            ("payment_terms", "INTEGER DEFAULT 30"),
            ("currency", "TEXT DEFAULT 'EUR'"),
            ("notes", "TEXT"),
        ]
        
        for col_name, col_def in new_columns:
            if col_name in existing_cols:
                print(f"✓ {col_name} column already exists")
            else:
                print(f"Adding {col_name} column...")
                cursor.execute(f"ALTER TABLE customers ADD COLUMN {col_name} {col_def}")
                print(f"✓ {col_name} column added")
        
        conn.commit()
        conn.close()
        print("\n✓ Migration completed successfully")
        return 0
        
    except Exception as e:
        print(f"✗ Migration failed: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(migrate())
