"""Postgres connection pool and schema setup."""

from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _configure(conn: psycopg.Connection) -> None:
    register_vector(conn)


def create_pool(database_url: str) -> ConnectionPool:
    # The vector extension must exist before register_vector can look up its type.
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    pool = ConnectionPool(
        database_url,
        min_size=1,
        max_size=10,
        configure=_configure,
        kwargs={"row_factory": dict_row},
        open=True,
    )
    pool.wait()
    return pool


def run_migrations(pool: ConnectionPool) -> None:
    """Apply every SQL file in migrations/ in name order. Files must be idempotent.

    A real migration tool (Alembic, sqitch) would track applied versions; for a
    single-table-set prototype, idempotent DDL is enough and has no extra moving parts.
    """
    with pool.connection() as conn:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.execute(path.read_text())
