#!/usr/bin/env python3
"""Migration script to add quotes and quote_lines tables to existing database."""

import sqlite3
import sys

def migrate():
    """Add quotes and quote_lines tables if they don't exist."""
    try:
        conn = sqlite3.connect("duck.db")
        cursor = conn.cursor()
        
        # Check if quotes table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quotes'")
        if cursor.fetchone():
            print("✓ quotes table already exists")
        else:
            print("Adding quotes table...")
            cursor.execute("""
                CREATE TABLE quotes (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    revision_number INTEGER NOT NULL DEFAULT 1,
                    supersedes_quote_id TEXT,
                    requested_delivery_date TEXT,
                    ship_to_line1 TEXT,
                    ship_to_postal_code TEXT,
                    ship_to_city TEXT,
                    ship_to_country TEXT,
                    note TEXT,
                    subtotal REAL NOT NULL DEFAULT 0,
                    discount REAL NOT NULL DEFAULT 0,
                    shipping REAL NOT NULL DEFAULT 0,
                    tax REAL NOT NULL DEFAULT 0,
                    total REAL NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'EUR',
                    valid_until TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    accepted_at TEXT,
                    rejected_at TEXT
                )
            """)
            print("✓ quotes table created")
        
        # Check if quote_lines table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quote_lines'")
        if cursor.fetchone():
            print("✓ quote_lines table already exists")
        else:
            print("Adding quote_lines table...")
            cursor.execute("""
                CREATE TABLE quote_lines (
                    id TEXT PRIMARY KEY,
                    quote_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    qty REAL NOT NULL,
                    unit_price REAL NOT NULL,
                    line_total REAL NOT NULL
                )
            """)
            print("✓ quote_lines table created")
        
        conn.commit()
        conn.close()
        print("\n✓ Migration completed successfully")
        return 0
        
    except Exception as e:
        print(f"✗ Migration failed: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(migrate())
