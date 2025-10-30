"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime


class CandleResponse(BaseModel):
    """Single K-line candle."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None  # Calculated field


class KlineDataResponse(BaseModel):
    """K-line data response."""
    symbol: str
    timeframe: str
    start_time: str
    end_time: str
    count: int
    candles: List[CandleResponse]


class KlineRequest(BaseModel):
    """K-line data request."""
    symbol: str = Field(..., description="Currency pair (e.g., 'EURUSD', 'BTC-USD')")
    limit: int = Field(128, ge=1, le=10000, description="Number of candles")
    end_time: Optional[datetime] = Field(None, description="End time (default: now)")
    timeframe: str = Field('1h', pattern='^(1h|1d)$', description="Timeframe: '1h' or '1d'")

    @field_validator('end_time')
    @classmethod
    def set_default_end_time(cls, v):
        return v or datetime.now()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    database_connected: bool
    version: str = "1.0.0"
