from time import perf_counter
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import Limiter

from .config import Settings, get_settings
from .logging_utils import REQUEST_ID_HEADER, get_logger
from .metrics import record_metrics, RATE_LIMIT_HITS
from .predictor import PredictorManager
from .schemas import (
    HealthResponse,
    PredictBatchRequest,
    PredictResponse,
    PredictSingleRequest,
    ReadyResponse,
)


logger = get_logger(__name__)


def get_predictor_manager(settings: Settings = Depends(get_settings)) -> PredictorManager:
    return PredictorManagerRegistry.get(settings)


class PredictorManagerRegistry:
    _manager: PredictorManager | None = None
    _settings_hash: str | None = None

    @classmethod
    def get(cls, settings: Settings) -> PredictorManager:
        settings_hash = str(hash(settings.json()))
        if cls._manager is None or cls._settings_hash != settings_hash:
            cls._manager = PredictorManager(settings)
            cls._settings_hash = settings_hash
        return cls._manager


router = APIRouter(prefix="/v1")


@router.get("/healthz", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadyResponse)
async def ready(manager: PredictorManager = Depends(get_predictor_manager)) -> ReadyResponse:
    return ReadyResponse(status="ok" if manager.ready else "loading", model_loaded=manager.ready)


@router.post("/predict/single", response_model=PredictResponse)
async def predict_single(
    request: Request,
    payload: PredictSingleRequest,
    manager: PredictorManager = Depends(get_predictor_manager),
) -> PredictResponse:
    if not manager.ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model not ready")

    start = perf_counter()
    route = "/v1/predict/single"

    try:
        # Use async prediction to avoid blocking event loop (Phase 3)
        prediction_df = await manager.predict_single_async(
            candles=[c.dict() for c in payload.candles],
            timestamps=payload.timestamps,
            prediction_timestamps=payload.prediction_timestamps,
            overrides=payload.overrides.dict() if payload.overrides else None,
        )
        duration = perf_counter() - start
        record_metrics(route, "success", duration)

        logger.info(
            "single prediction completed",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "latency_ms": round(duration * 1000, 2),
                "rows": len(payload.candles),
                "pred_len": len(payload.prediction_timestamps),
            },
        )

        predictions: List[dict] = prediction_df.to_dict(orient="records")

        return PredictResponse(
            series_id=payload.series_id,
            prediction=[dict_to_point(p) for p in predictions],
            model_version=manager.model_version,
            tokenizer_version=manager.tokenizer_version,
        )
    except TimeoutError as exc:
        duration = perf_counter() - start
        record_metrics(route, "timeout", duration)
        logger.warning(
            "single prediction timeout",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        duration = perf_counter() - start
        record_metrics(route, "error", duration)
        logger.exception(
            "single prediction failed",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/predict/batch", response_model=List[PredictResponse])
async def predict_batch(
    request: Request,
    payload: PredictBatchRequest,
    manager: PredictorManager = Depends(get_predictor_manager),
) -> List[PredictResponse]:
    if not manager.ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model not ready")

    start = perf_counter()
    route = "/v1/predict/batch"

    try:
        # Use async prediction to avoid blocking event loop (Phase 3)
        predictions = await manager.predict_batch_async(
            [
                {
                    "candles": [c.dict() for c in item.candles],
                    "timestamps": item.timestamps,
                    "prediction_timestamps": item.prediction_timestamps,
                    "overrides": item.overrides.dict() if item.overrides else None,
                }
                for item in payload.items
            ]
        )

        duration = perf_counter() - start
        record_metrics(route, "success", duration)

        logger.info(
            "batch prediction completed",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "latency_ms": round(duration * 1000, 2),
                "series_count": len(payload.items),
            },
        )

        responses: List[PredictResponse] = []
        for item, df in zip(payload.items, predictions, strict=True):
            records = df.to_dict(orient="records")
            responses.append(
                PredictResponse(
                    series_id=item.series_id,
                    prediction=[dict_to_point(r) for r in records],
                    model_version=manager.model_version,
                    tokenizer_version=manager.tokenizer_version,
                )
            )
        return responses
    except TimeoutError as exc:
        duration = perf_counter() - start
        record_metrics(route, "timeout", duration)
        logger.warning(
            "batch prediction timeout",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        duration = perf_counter() - start
        record_metrics(route, "error", duration)
        logger.exception(
            "batch prediction failed",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/metrics")
async def metrics() -> Response:
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


def dict_to_point(row: dict) -> dict:
    timestamp = row.get("timestamp")
    if hasattr(timestamp, "to_pydatetime"):
        timestamp = timestamp.to_pydatetime()

    return {
        "timestamp": timestamp,
        "open": float(row.get("open", 0.0)),
        "high": float(row.get("high", 0.0)),
        "low": float(row.get("low", 0.0)),
        "close": float(row.get("close", 0.0)),
        "volume": float(row.get("volume", 0.0)),
        "amount": float(row.get("amount", 0.0)),
    }
