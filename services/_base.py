"""Shared base utilities for service modules."""

import sqlite3
import logging
import threading
from contextlib import contextmanager
from typing import Iterator

from db import get_connection

logger = logging.getLogger(__name__)

_local = threading.local()


@contextmanager
def db_conn() -> Iterator[sqlite3.Connection]:
    """Database connection context manager with per-thread reuse.

    The first call on a thread opens a connection that is reused by all
    nested ``db_conn()`` blocks.  The outermost block closes it.
    """
    existing = getattr(_local, "conn", None)
    if existing is not None:
        # Reuse the connection already open on this thread.
        yield existing
        return

    conn = get_connection()
    _local.conn = conn
    try:
        yield conn
    finally:
        _local.conn = None
        conn.close()
