"""Data source integrations for the RAG knowledge base."""

from rag.data_sources.base import DataSource

# Lazy imports so missing optional dependencies don't break the package.
try:
    from rag.data_sources.rss_source import RSSSource
except ImportError:
    RSSSource = None  # type: ignore[assignment,misc]

try:
    from rag.data_sources.db_source import DBSource
except ImportError:
    DBSource = None  # type: ignore[assignment,misc]

try:
    from rag.data_sources.api_source import APISource
except ImportError:
    APISource = None  # type: ignore[assignment,misc]

__all__ = ["DataSource", "RSSSource", "DBSource", "APISource"]
