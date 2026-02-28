"""Shared base utilities for service modules."""

import sqlite3
import logging
from contextlib import contextmanager
from typing import Iterator

from db import get_connection

logger = logging.getLogger(__name__)


@contextmanager
def db_conn() -> Iterator[sqlite3.Connection]:
    """Database connection context manager."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
