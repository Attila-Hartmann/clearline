from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from clearline.config import settings

SCHEMA = Path(__file__).with_name("schema.sql")


def _configure(conn: psycopg.Connection) -> None:
    register_vector(conn)


@lru_cache
def pool() -> ConnectionPool:
    # Extension must exist before register_vector can find the type.
    with psycopg.connect(settings().database_url, autocommit=True) as c:
        c.execute("create extension if not exists vector")
    return ConnectionPool(settings().database_url, min_size=1, max_size=8, configure=_configure,
                          kwargs={"row_factory": dict_row, "autocommit": True}, open=True)


@contextmanager
def conn() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with pool().connection() as c:
        yield cast("psycopg.Connection[dict[str, Any]]", c)  # pool is configured with dict_row


def migrate() -> None:
    with conn() as c:
        c.execute(SCHEMA.read_text(encoding="utf-8"))  # type: ignore[arg-type]
