"""Service for document storage and retrieval."""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from db import generate_id
from services._base import db_conn


def store_document(
    entity_type: str,
    entity_id: str,
    document_type: str,
    content: bytes,
    filename: str,
    mime_type: str = "application/pdf",
    notes: Optional[str] = None
) -> str:
    """Store a document in the database."""
    from services.simulation import simulation_service

    with db_conn() as conn:
        sim_time = simulation_service.get_current_time()
        doc_id = generate_id(conn, "DOC", "documents")
        conn.execute(
            "INSERT INTO documents (id, entity_type, entity_id, document_type, content, mime_type, filename, generated_at, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, entity_type, entity_id, document_type, content, mime_type, filename, sim_time, notes)
        )
        conn.commit()
        return doc_id

def get_document(entity_type: str, entity_id: str, document_type: str) -> Optional[Dict[str, Any]]:
    """Get the most recent document for an entity."""
    with db_conn() as conn:
        row = conn.execute(
            "SELECT id, entity_type, entity_id, document_type, content, mime_type, filename, generated_at, notes "
            "FROM documents "
            "WHERE entity_type = ? AND entity_id = ? AND document_type = ? "
            "ORDER BY generated_at DESC LIMIT 1",
            (entity_type, entity_id, document_type)
        ).fetchone()
        if not row:
            return None
        return dict(row)

def list_documents(entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
    """List all documents for an entity (excluding content)."""
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT id, entity_type, entity_id, document_type, mime_type, filename, generated_at, notes "
            "FROM documents "
            "WHERE entity_type = ? AND entity_id = ? "
            "ORDER BY generated_at DESC",
            (entity_type, entity_id)
        ).fetchall()
        return [dict(row) for row in rows]


# Namespace for backward compatibility
document_service = SimpleNamespace(
    store_document=store_document,
    get_document=get_document,
    list_documents=list_documents,
)
DocumentService = type(document_service)
