"""Database data source supporting SQLite, MySQL, and PostgreSQL."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from rag.data_sources.base import DataSource

logger = logging.getLogger(__name__)


class DBSource(DataSource):
    """Execute a SQL query against a database and return the results as documents.

    Supported connection string formats:
    - ``sqlite:///path/to/db.sqlite``
    - ``mysql://user:pass@host:port/dbname``
    - ``postgresql://user:pass@host:port/dbname``
    """

    def __init__(self, connection_string: str, query: str) -> None:
        if not connection_string:
            raise ValueError("connection_string is required for DBSource")
        if not query:
            raise ValueError("query is required for DBSource")
        self.connection_string = connection_string
        self.query = query

    # -- helpers --------------------------------------------------------------

    def _parse_scheme(self) -> str:
        parsed = urlparse(self.connection_string)
        return parsed.scheme.lower()

    def _get_sqlite_path(self) -> str:
        """Extract the file path from a ``sqlite:///`` connection string."""
        return self.connection_string[len("sqlite://") :]

    # -- SQLite ---------------------------------------------------------------

    def _sqlite_test(self) -> bool:
        import sqlite3

        try:
            conn = sqlite3.connect(self._get_sqlite_path())
            conn.execute(self.query)
            conn.close()
            return True
        except Exception as exc:
            logger.warning("SQLite connection test failed: %s", exc)
            return False

    def _sqlite_fetch(self) -> list[dict]:
        import sqlite3

        conn = sqlite3.connect(self._get_sqlite_path())
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(self.query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    # -- MySQL ----------------------------------------------------------------

    def _mysql_test(self) -> bool:
        try:
            import pymysql  # type: ignore[import-untyped]
        except ImportError:
            logger.error("pymysql is required for MySQL sources")
            return False

        parsed = urlparse(self.connection_string)
        try:
            conn = pymysql.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 3306,
                user=parsed.username or "",
                password=parsed.password or "",
                database=parsed.path.lstrip("/") or None,
            )
            cur = conn.cursor()
            cur.execute(self.query)
            cur.close()
            conn.close()
            return True
        except Exception as exc:
            logger.warning("MySQL connection test failed: %s", exc)
            return False

    def _mysql_fetch(self) -> list[dict]:
        try:
            import pymysql
        except ImportError:
            raise RuntimeError("pymysql is required for MySQL sources")

        parsed = urlparse(self.connection_string)
        conn = pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "",
            password=parsed.password or "",
            database=parsed.path.lstrip("/") or None,
        )
        try:
            cur = conn.cursor()
            cur.execute(self.query)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    # -- PostgreSQL -----------------------------------------------------------

    def _pg_test(self) -> bool:
        try:
            import psycopg2  # type: ignore[import-untyped]
        except ImportError:
            logger.error("psycopg2 is required for PostgreSQL sources")
            return False

        try:
            conn = psycopg2.connect(self.connection_string)
            cur = conn.cursor()
            cur.execute(self.query)
            cur.close()
            conn.close()
            return True
        except Exception as exc:
            logger.warning("PostgreSQL connection test failed: %s", exc)
            return False

    def _pg_fetch(self) -> list[dict]:
        try:
            import psycopg2
        except ImportError:
            raise RuntimeError("psycopg2 is required for PostgreSQL sources")

        conn = psycopg2.connect(self.connection_string)
        try:
            cur = conn.cursor()
            cur.execute(self.query)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    # -- DataSource interface -------------------------------------------------

    def test_connection(self) -> bool:
        scheme = self._parse_scheme()
        if scheme == "sqlite":
            return self._sqlite_test()
        elif scheme in ("mysql", "mysql+pymysql"):
            return self._mysql_test()
        elif scheme in ("postgresql", "postgres", "psycopg2"):
            return self._pg_test()
        else:
            logger.error("Unsupported database scheme: %s", scheme)
            return False

    async def fetch(self) -> list[dict]:
        scheme = self._parse_scheme()
        if scheme == "sqlite":
            return self._sqlite_fetch()
        elif scheme in ("mysql", "mysql+pymysql"):
            return self._mysql_fetch()
        elif scheme in ("postgresql", "postgres", "psycopg2"):
            return self._pg_fetch()
        else:
            raise RuntimeError(f"Unsupported database scheme: {scheme}")
