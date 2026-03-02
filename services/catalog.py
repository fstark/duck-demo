"""Service for item/catalog operations."""

import re
import sqlite3
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import config
from db import dict_rows
from utils import ui_href
from services._base import db_conn


def load_item(sku_or_id: str) -> Optional[Dict[str, Any]]:
    """Load item by SKU or item_id."""
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT id, sku, name, type, unit_price, cost_price, uom, reorder_qty, default_supplier_id, image FROM items WHERE sku = ? OR id = ?",
            (sku_or_id, sku_or_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None

def get_item(sku_or_id: str) -> Dict[str, Any]:
    """Fetch an item by SKU or item_id."""
    item = load_item(sku_or_id)
    if not item:
        raise ValueError("Item not found")
    result = dict(item)
    if result.get("image"):
        result["image_url"] = f"{config.API_BASE}/api/items/{result['sku']}/image.png"
    result.pop("image", None)
    return result

def search_items(words: List[str], limit: int = 10, min_score: int = 1) -> Dict[str, Any]:
    """Fuzzy item search via containment on SKU/name tokens."""
    normalized_phrases = [w.strip().lower() for w in words if w and w.strip()]

    def phrase_tokens(phrase: str) -> List[str]:
        return [tok for tok in re.split(r"[^a-z0-9]+", phrase) if tok]

    query_tokens: List[str] = []
    for phrase in normalized_phrases:
        query_tokens.extend(phrase_tokens(phrase))

    if not query_tokens:
        raise ValueError("words required")

    def tokens_for(row: sqlite3.Row) -> List[str]:
        raw = f"{row['sku']} {row['name']}".lower()
        return [tok for tok in re.split(r"[^a-z0-9]+", raw) if tok]

    with db_conn() as conn:
        rows = conn.execute("SELECT id, sku, name, type, unit_price FROM items").fetchall()
        scored: List[Dict[str, Any]] = []
        for row in rows:
            token_set = set(tokens_for(row))
            matched = [w for w in query_tokens if any(w in tok for tok in token_set)]

            score = len(matched)
            if score >= min_score:
                item_dict = dict(row)
                item_dict["ui_url"] = ui_href("items", item_dict["sku"])
                scored.append({"item": item_dict, "score": score, "matched_words": matched})

        scored.sort(key=lambda entry: (-entry["score"], entry["item"]["sku"]))
        return {"items": scored[:limit], "query": query_tokens}

def list_items(in_stock_only: bool = False, item_type: Optional[str] = "finished_good", limit: int = 50) -> Dict[str, Any]:
    """List items, optionally only those with available stock."""
    from services.inventory import inventory_service

    with db_conn() as conn:
        base_sql = "SELECT id, sku, name, type, unit_price, image FROM items"
        params: List[Any] = []
        filters = []

        if item_type:
            filters.append("type = ?")
            params.append(item_type)

        if in_stock_only:
            filters.append("id IN (SELECT DISTINCT item_id FROM stock WHERE on_hand > 0)")

        if filters:
            base_sql += " WHERE " + " AND ".join(filters)

        base_sql += " ORDER BY sku LIMIT ?"
        params.append(limit)
        rows = dict_rows(conn.execute(base_sql, params))
        # Attach stock totals for all items
        for row in rows:
            summary = inventory_service.get_stock_summary(row["id"])
            row["on_hand_total"] = summary["on_hand_total"]
            row["available_total"] = summary["available_total"]
        for row in rows:
            row["ui_url"] = ui_href("items", row["sku"])
            if row.get("image"):
                row["image_url"] = f"{config.API_BASE}/api/items/{row['sku']}/image.png"
            row.pop("image", None)
        return {"items": rows}


# Namespace for backward compatibility
catalog_service = SimpleNamespace(
    load_item=load_item,
    get_item=get_item,
    search_items=search_items,
    list_items=list_items,
)
CatalogService = type(catalog_service)
