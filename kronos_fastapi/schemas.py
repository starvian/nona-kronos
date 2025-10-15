from datetime import datetime
from typing import List, Optional

try:
    from pydantic import BaseModel, Field, model_validator
except ImportError:
    from pydantic import BaseModel, Field, root_validator as model_validator


class Candle(BaseModel):
    open: float = Field(..., gt=0, description="Opening price (must be positive)")
    high: float = Field(..., gt=0, description="High price (must be positive)")
    low: float = Field(..., gt=0, description="Low price (must be positive)")
    close: float = Field(..., gt=0, description="Closing price (must be positive)")
    volume: Optional[float] = Field(default=0.0, ge=0, description="Trading volume (non-negative)")
    amount: Optional[float] = Field(default=0.0, ge=0, description="Trading amount (non-negative)")

    @model_validator(mode='after')
    def validate_ohlc(self):
        """Validate OHLC relationships: Low <= Open/Close <= High."""
        if self.low > min(self.open, self.close):
            raise ValueError(f"Low ({self.low}) cannot be greater than open ({self.open}) or close ({self.close})")
        if self.high < max(self.open, self.close):
            raise ValueError(f"High ({self.high}) cannot be less than open ({self.open}) or close ({self.close})")
        if self.low > self.high:
            raise ValueError(f"Low ({self.low}) cannot be greater than high ({self.high})")
        return self


class PredictionOverrides(BaseModel):
    pred_len: Optional[int]
    temperature: Optional[float]
    top_k: Optional[int]
    top_p: Optional[float]
    sample_count: Optional[int]


class PredictSingleRequest(BaseModel):
    series_id: Optional[str] = Field(None, description="Identifier for the time series")
    candles: List[Candle] = Field(..., min_length=1, max_length=2048, description="Input candles (1-2048)")
    timestamps: List[datetime] = Field(..., min_length=1, description="Timestamps for input candles")
    prediction_timestamps: List[datetime] = Field(..., min_length=1, max_length=512, description="Prediction timestamps (1-512)")
    overrides: Optional[PredictionOverrides] = None

    @model_validator(mode='after')
    def validate_lengths(self):
        # Length matching
        if len(self.candles) != len(self.timestamps):
            raise ValueError(
                f"candles and timestamps length mismatch: "
                f"{len(self.candles)} candles but {len(self.timestamps)} timestamps"
            )
        if not self.prediction_timestamps:
            raise ValueError("prediction_timestamps cannot be empty")

        # Timestamp ordering (Phase 5)
        for i in range(1, len(self.timestamps)):
            if self.timestamps[i] <= self.timestamps[i-1]:
                raise ValueError(
                    f"timestamps must be in ascending order: "
                    f"timestamp[{i-1}] = {self.timestamps[i-1]} >= timestamp[{i}] = {self.timestamps[i]}"
                )

        for i in range(1, len(self.prediction_timestamps)):
            if self.prediction_timestamps[i] <= self.prediction_timestamps[i-1]:
                raise ValueError(
                    f"prediction_timestamps must be in ascending order: "
                    f"prediction_timestamps[{i-1}] = {self.prediction_timestamps[i-1]} >= "
                    f"prediction_timestamps[{i}] = {self.prediction_timestamps[i]}"
                )

        # Prediction timestamps should be after input timestamps
        if self.timestamps and self.prediction_timestamps:
            if self.prediction_timestamps[0] <= self.timestamps[-1]:
                raise ValueError(
                    f"prediction_timestamps must be after input timestamps: "
                    f"last input timestamp = {self.timestamps[-1]}, "
                    f"first prediction timestamp = {self.prediction_timestamps[0]}"
                )

        return self


class PredictBatchItem(BaseModel):
    series_id: str
    candles: List[Candle] = Field(..., min_length=1, max_length=2048)
    timestamps: List[datetime] = Field(..., min_length=1)
    prediction_timestamps: List[datetime] = Field(..., min_length=1, max_length=512)
    overrides: Optional[PredictionOverrides] = None

    @model_validator(mode='after')
    def validate_lengths(self):
        # Same validation as PredictSingleRequest
        if len(self.candles) != len(self.timestamps):
            raise ValueError(
                f"[{self.series_id}] candles and timestamps length mismatch: "
                f"{len(self.candles)} candles but {len(self.timestamps)} timestamps"
            )
        if not self.prediction_timestamps:
            raise ValueError(f"[{self.series_id}] prediction_timestamps cannot be empty")

        # Timestamp ordering
        for i in range(1, len(self.timestamps)):
            if self.timestamps[i] <= self.timestamps[i-1]:
                raise ValueError(
                    f"[{self.series_id}] timestamps must be in ascending order at index {i}"
                )

        for i in range(1, len(self.prediction_timestamps)):
            if self.prediction_timestamps[i] <= self.prediction_timestamps[i-1]:
                raise ValueError(
                    f"[{self.series_id}] prediction_timestamps must be in ascending order at index {i}"
                )

        if self.timestamps and self.prediction_timestamps:
            if self.prediction_timestamps[0] <= self.timestamps[-1]:
                raise ValueError(
                    f"[{self.series_id}] prediction_timestamps must be after input timestamps"
                )

        return self


class PredictBatchRequest(BaseModel):
    items: List[PredictBatchItem]


class PredictionPoint(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


class PredictResponse(BaseModel):
    series_id: Optional[str]
    prediction: List[PredictionPoint]
    model_version: Optional[str]
    tokenizer_version: Optional[str]


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    model_loaded: bool
    device: Optional[str] = None
    device_warning: Optional[str] = None


# Enhanced error responses (Phase 5)
class ErrorDetail(BaseModel):
    """Detailed error information."""
    field: Optional[str] = Field(None, description="Field that caused the error")
    index: Optional[int] = Field(None, description="Index of problematic item in array")
    value: Optional[str] = Field(None, description="Value that caused the error")
    constraint: Optional[str] = Field(None, description="Constraint that was violated")


class ErrorResponse(BaseModel):
    """Structured error response with context."""
    error: str = Field(..., description="Error type (e.g., ValidationError, TimeoutError)")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[ErrorDetail] = Field(None, description="Additional error context")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
