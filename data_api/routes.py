"""
API routes for Data API service.
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
from typing import Optional
import logging

from .schemas import KlineDataResponse, KlineRequest, HealthResponse, CandleResponse
from .aggregator import KlineAggregator
from .database import ClickHouseConnection
from .config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Dependency injection
def get_db_connection():
    """Dependency: Database connection."""
    settings = get_settings()
    return ClickHouseConnection(settings)


def get_aggregator(db: ClickHouseConnection = Depends(get_db_connection)):
    """Dependency: K-line aggregator."""
    return KlineAggregator(db)


@router.get("/v1/healthz", response_model=HealthResponse)
async def health_check(db: ClickHouseConnection = Depends(get_db_connection)):
    """
    Health check endpoint.

    Returns service status and database connectivity.
    """
    try:
        # Test database connection
        client = db.connect()
        result = client.execute("SELECT 1")
        db_connected = result == [(1,)]
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_connected = False

    return HealthResponse(
        status="ok" if db_connected else "degraded",
        timestamp=datetime.now().isoformat(),
        database_connected=db_connected
    )


@router.post("/v1/kline", response_model=KlineDataResponse)
async def get_kline_data(
    request: KlineRequest,
    aggregator: KlineAggregator = Depends(get_aggregator)
):
    """
    Get K-line (OHLC) data from ClickHouse.

    **Example request:**
    ```json
    {
        "symbol": "EURUSD",
        "limit": 128,
        "end_time": "2025-10-30T12:00:00",
        "timeframe": "1h"
    }
    ```

    **Returns:**
    - List of OHLC candles
    - Timestamps in ISO format
    - Trading volume and derived amount
    """
    try:
        # Calculate start time based on limit and timeframe
        if request.timeframe == '1h':
            start_time = request.end_time - timedelta(hours=request.limit + 24)  # Buffer
        else:  # 1d
            start_time = request.end_time - timedelta(days=request.limit + 7)   # Buffer

        # Fetch data
        df = aggregator.get_kline_data(
            symbol=request.symbol,
            start_time=start_time,
            end_time=request.end_time,
            timeframe=request.timeframe,
            limit=request.limit
        )

        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {request.symbol} in timeframe {request.timeframe}"
            )

        # Reverse to get chronological order (oldest first)
        df = df.iloc[::-1]

        # Convert to response format
        candles = []
        for idx, row in df.iterrows():
            candle = CandleResponse(
                timestamp=idx.isoformat(),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']),
                amount=float(row['volume']) * float(row['close'])  # Approximate
            )
            candles.append(candle)

        return KlineDataResponse(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_time=df.index.min().isoformat(),
            end_time=df.index.max().isoformat(),
            count=len(candles),
            candles=candles
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing K-line request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/kline/{symbol}", response_model=KlineDataResponse)
async def get_kline_by_path(
    symbol: str,
    limit: int = 128,
    end_time: Optional[str] = None,
    timeframe: str = '1h',
    aggregator: KlineAggregator = Depends(get_aggregator)
):
    """
    Get K-line data via GET request.

    **Example:** `GET /v1/kline/EURUSD?limit=128&timeframe=1h`
    """
    # Convert to KlineRequest and reuse POST handler logic
    request = KlineRequest(
        symbol=symbol,
        limit=limit,
        end_time=datetime.fromisoformat(end_time) if end_time else None,
        timeframe=timeframe
    )
    return await get_kline_data(request, aggregator)
