import os
from contextlib import contextmanager
from importlib.resources import files

import psycopg
from psycopg.rows import dict_row


def database_url():
    return os.getenv("DATABASE_URL", "postgresql://catalog:catalog@localhost:55440/catalog")


@contextmanager
def connection():
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=5) as conn:
        yield conn


def migrate():
    with connection() as conn:
        conn.execute(files("catalog").joinpath("schema.sql").read_text())
