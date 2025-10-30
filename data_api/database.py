"""
ClickHouse database connection management.
"""

from clickhouse_driver import Client
from typing import Optional, List, Dict, Any
import logging
import time

from .config import get_settings, Settings

logger = logging.getLogger(__name__)


class ClickHouseConnection:
    """ClickHouse connection manager with retry logic."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._client: Optional[Client] = None

    def connect(self) -> Client:
        """Create and return ClickHouse client."""
        if self._client is None:
            try:
                self._client = Client(
                    host=self.settings.clickhouse_host,
                    port=self.settings.clickhouse_port,
                    user=self.settings.clickhouse_user,
                    password=self.settings.clickhouse_password,
                    database=self.settings.clickhouse_database,
                    settings={
                        'max_execution_time': self.settings.clickhouse_timeout,
                    }
                )
                logger.info(
                    f"Connected to ClickHouse at "
                    f"{self.settings.clickhouse_host}:{self.settings.clickhouse_port}"
                )
            except Exception as e:
                logger.error(f"Failed to connect to ClickHouse: {e}")
                raise

        return self._client

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[tuple]:
        """Execute query with retry logic."""
        client = self.connect()
        retries = 0

        while retries < self.settings.clickhouse_max_retries:
            try:
                result = client.execute(query, params or {})
                return result
            except Exception as e:
                retries += 1
                logger.warning(
                    f"Query failed (attempt {retries}/{self.settings.clickhouse_max_retries}): {e}"
                )
                if retries >= self.settings.clickhouse_max_retries:
                    logger.error(f"Query failed after {retries} attempts")
                    raise
                time.sleep(self.settings.clickhouse_retry_delay)

        return []  # Should not reach here

    def disconnect(self):
        """Close connection."""
        if self._client:
            self._client.disconnect()
            self._client = None
            logger.info("Disconnected from ClickHouse")

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
