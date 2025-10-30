"""
K-line data aggregation from ClickHouse.

Based on ForexDataProcessor._get_aggregated_data() from nona_server_06.
"""

from datetime import datetime
from typing import Optional, List
import pandas as pd
import logging

from .database import ClickHouseConnection

logger = logging.getLogger(__name__)


class KlineAggregator:
    """K-line (OHLC) data aggregation from ClickHouse."""

    def __init__(self, db_connection: ClickHouseConnection):
        self.db = db_connection

    def get_kline_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        timeframe: str = '1h',
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get K-line (OHLC) data from ClickHouse.

        Args:
            symbol: Currency pair (e.g., 'EURUSD', 'BTC-USD')
            start_time: Query start time
            end_time: Query end time
            timeframe: '1h' (hourly) or '1d' (daily)
            limit: Maximum number of candles to return

        Returns:
            DataFrame with OHLC data and timestamp index
        """
        logger.info(
            f"Fetching K-line data: symbol={symbol}, "
            f"timeframe={timeframe}, start={start_time}, end={end_time}, limit={limit}"
        )

        try:
            if timeframe == '1d':
                query = self._build_daily_query(limit)
            else:
                query = self._build_hourly_query(limit)

            results = self.db.execute_query(
                query,
                {
                    'currency_pair': symbol,
                    'start_time': start_time,
                    'end_time': end_time
                }
            )

            if not results:
                logger.warning(f"No data found for {symbol} in timeframe {timeframe}")
                return pd.DataFrame()

            df = self._parse_results(results, timeframe)
            logger.info(f"Retrieved {len(df)} candles for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching K-line data: {e}")
            raise

    def _build_hourly_query(self, limit: Optional[int]) -> str:
        """
        Build hourly aggregation query.

        Based on nona_server_06 implementation with trading day logic:
        - Trading day starts at 17:00 UTC
        - Hours 17:00-23:59 belong to next calendar day
        """
        limit_clause = f'LIMIT {limit}' if limit else ''

        return f"""
            WITH
            raw_data AS (
                SELECT
                    timestamp,
                    bid_price,
                    ask_price,
                    volume,
                    toDate(if(toHour(timestamp) >= 17, addDays(timestamp, 1), timestamp)) as trading_date,
                    if(toHour(timestamp) < 17,
                        toHour(timestamp) + 7,
                        toHour(timestamp) - 17) as trading_hour
                FROM forex
                WHERE
                    currency_pair = %(currency_pair)s
                    AND timestamp BETWEEN %(start_time)s AND %(end_time)s
                ORDER BY timestamp ASC
            ),
            hourly_data AS (
                SELECT
                    trading_date,
                    trading_hour as hour,
                    argMin(bid_price, timestamp) as open,
                    max(bid_price) as high,
                    min(bid_price) as low,
                    argMax(bid_price, timestamp) as close,
                    avg(bid_price) as avg_bid_price,
                    avg(ask_price) as avg_ask_price,
                    sum(volume) as volume,
                    count() as tick_count
                FROM raw_data
                GROUP BY trading_date, trading_hour
                ORDER BY trading_date DESC, trading_hour DESC
            )
            SELECT
                trading_date,
                hour,
                open,
                high,
                low,
                close,
                avg_bid_price,
                avg_ask_price,
                volume,
                tick_count
            FROM hourly_data
            {limit_clause}
        """

    def _build_daily_query(self, limit: Optional[int]) -> str:
        """
        Build daily aggregation query.

        Based on nona_server_06 implementation with trading day logic.
        """
        limit_clause = f'LIMIT {limit}' if limit else ''

        return f"""
            WITH
            raw_data AS (
                SELECT
                    timestamp,
                    bid_price,
                    ask_price,
                    volume,
                    toDate(if(toHour(timestamp) >= 17, addDays(timestamp, 1), timestamp)) as trading_date
                FROM forex
                WHERE
                    currency_pair = %(currency_pair)s
                    AND timestamp BETWEEN %(start_time)s AND %(end_time)s
                ORDER BY timestamp ASC
            ),
            daily_data AS (
                SELECT
                    trading_date,
                    0 as hour,
                    argMin(bid_price, timestamp) as open,
                    max(bid_price) as high,
                    min(bid_price) as low,
                    argMax(bid_price, timestamp) as close,
                    avg(bid_price) as avg_bid_price,
                    avg(ask_price) as avg_ask_price,
                    sum(volume) as volume,
                    count() as tick_count
                FROM raw_data
                GROUP BY trading_date
                ORDER BY trading_date DESC
            )
            SELECT
                trading_date,
                hour,
                open,
                high,
                low,
                close,
                avg_bid_price,
                avg_ask_price,
                volume,
                tick_count
            FROM daily_data
            {limit_clause}
        """

    def _parse_results(self, results: List[tuple], timeframe: str) -> pd.DataFrame:
        """Parse query results into DataFrame with timestamp index."""
        df = pd.DataFrame(
            results,
            columns=[
                'trading_date', 'hour', 'open', 'high', 'low', 'close',
                'avg_bid_price', 'avg_ask_price', 'volume', 'tick_count'
            ]
        )

        # Create timestamp index
        temp_timestamp_col = pd.to_datetime(df['trading_date'])

        if timeframe == '1d':
            df.set_index(temp_timestamp_col, inplace=True)
            df.index = df.index.tz_localize('UTC')
        else:
            df['timestamp'] = temp_timestamp_col + pd.to_timedelta(df['hour'], unit='h')
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
            df.set_index('timestamp', inplace=True)

        df.index.name = 'timestamp'
        return df
