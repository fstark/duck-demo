#!/usr/bin/env python3
"""Migration script to add documents table to existing database."""

import sqlite3
import sys

def migrate():
    """Add documents table if it doesn't exist."""
    try:
        conn = sqlite3.connect("duck.db")
        cursor = conn.cursor()
        
        # Check if documents table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
        if cursor.fetchone():
            print("✓ documents table already exists")
        else:
            print("Adding documents table...")
            cursor.execute("""
                CREATE TABLE documents (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    content BLOB NOT NULL,
                    mime_type TEXT NOT NULL DEFAULT 'application/pdf',
                    filename TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    notes TEXT
                )
            """)
            
            cursor.execute("CREATE INDEX idx_documents_entity ON documents(entity_type, entity_id)")
            cursor.execute("CREATE INDEX idx_documents_type ON documents(document_type)")
            
            conn.commit()
            print("✓ documents table created successfully")
        
        conn.close()
        print("\n✓ Migration completed successfully")
        return 0
        
    except Exception as e:
        print(f"✗ Migration failed: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(migrate())
