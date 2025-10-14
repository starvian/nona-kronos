from datetime import datetime
from typing import List, Optional

try:
    from pydantic import BaseModel, Field, model_validator
except ImportError:
    from pydantic import BaseModel, Field, root_validator as model_validator


class Candle(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = Field(default=0.0)
    amount: Optional[float] = Field(default=0.0)


class PredictionOverrides(BaseModel):
    pred_len: Optional[int]
    temperature: Optional[float]
    top_k: Optional[int]
    top_p: Optional[float]
    sample_count: Optional[int]


class PredictSingleRequest(BaseModel):
    series_id: Optional[str] = Field(None, description="Identifier for the time series")
    candles: List[Candle]
    timestamps: List[datetime]
    prediction_timestamps: List[datetime]
    overrides: Optional[PredictionOverrides] = None

    @model_validator(mode='after')
    def validate_lengths(self):
        if len(self.candles) != len(self.timestamps):
            raise ValueError("candles and timestamps length mismatch")
        if not self.prediction_timestamps:
            raise ValueError("prediction_timestamps cannot be empty")
        return self


class PredictBatchItem(BaseModel):
    series_id: str
    candles: List[Candle]
    timestamps: List[datetime]
    prediction_timestamps: List[datetime]
    overrides: Optional[PredictionOverrides] = None

    @model_validator(mode='after')
    def validate_lengths(self):
        if len(self.candles) != len(self.timestamps):
            raise ValueError("candles and timestamps length mismatch")
        if not self.prediction_timestamps:
            raise ValueError("prediction_timestamps cannot be empty")
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
