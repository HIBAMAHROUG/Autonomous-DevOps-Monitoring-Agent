"""
Connecteur PostgreSQL pour le module remediation (KB, catalogue, décisions).

Utilise un pool de connexions psycopg2 simple.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

_POOL: SimpleConnectionPool | None = None


def _build_dsn() -> str:
    return (
        f"host={os.getenv('REMEDIATION_DB_HOST', 'localhost')} "
        f"port={os.getenv('REMEDIATION_DB_PORT', '5432')} "
        f"dbname={os.getenv('REMEDIATION_DB_NAME', 'remediation')} "
        f"user={os.getenv('REMEDIATION_DB_USER', 'postgres')} "
        f"password={os.getenv('REMEDIATION_DB_PASSWORD', 'devpass')}"
    )


def init_pool(minconn: int = 1, maxconn: int = 5) -> None:
    """À appeler une fois au démarrage de l'app."""
    global _POOL

    if _POOL is None:
        _POOL = SimpleConnectionPool(
            minconn,
            maxconn,
            dsn=_build_dsn()
        )


def close_pool() -> None:
    global _POOL

    if _POOL is not None:
        _POOL.closeall()
        _POOL = None


@contextmanager
def get_connection() -> Iterator[psycopg2.extensions.connection]:
    """
    Usage:

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """

    if _POOL is None:
        init_pool()

    assert _POOL is not None

    conn = _POOL.getconn()

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _POOL.putconn(conn)


@contextmanager
def get_dict_cursor() -> Iterator[psycopg2.extras.RealDictCursor]:
    """Curseur qui retourne des dictionnaires plutôt que des tuples."""

    with get_connection() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            yield cur
