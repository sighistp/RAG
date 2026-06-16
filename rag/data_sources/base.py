"""Abstract base class for all data sources."""

from abc import ABC, abstractmethod


class DataSource(ABC):
    """Base class that every data source must implement.

    Subclasses must provide:
    - ``async fetch()``  -- retrieve documents from the source.
    - ``test_connection()`` -- check whether the source is reachable.
    """

    @abstractmethod
    async def fetch(self) -> list[dict]:
        """Fetch data from the source.

        Returns a list of dicts, each containing at least:
        ``title``, ``content``, ``url``, ``published_at``.
        """
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """Return *True* if the source is reachable and configuration is valid."""
        ...
