from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Sequence

import pandas as pd

from model import Kronos, KronosPredictor, KronosTokenizer

from .config import Settings


logger = logging.getLogger(__name__)


@dataclass
class PredictionParams:
    pred_len: int
    temperature: float
    top_k: int
    top_p: float
    sample_count: int


class PredictorManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tokenizer: Optional[KronosTokenizer] = None
        self._model: Optional[Kronos] = None
        self._predictor: Optional[KronosPredictor] = None
        self._model_version: Optional[str] = None
        self._tokenizer_version: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self._predictor is not None

    @property
    def model_version(self) -> Optional[str]:
        return self._model_version

    @property
    def tokenizer_version(self) -> Optional[str]:
        return self._tokenizer_version

    @property
    def device(self) -> Optional[str]:
        if self._predictor is None:
            return None
        return str(self._predictor.device)

    @property
    def device_warning(self) -> Optional[str]:
        if self._predictor is None:
            return None
        return self._predictor.device_warning

    def load(self) -> None:
        logger.info("loading Kronos tokenizer and model")
        
        # DEBUG: Log configuration on startup
        logger.info(
            f"Service configuration: "
            f"device={self._settings.device}, "
            f"inference_timeout={self._settings.inference_timeout}s, "
            f"request_timeout={self._settings.request_timeout}s"
        )

        # Use Hugging Face IDs if provided, otherwise use local paths
        if self._settings.tokenizer_id:
            tokenizer_source = self._settings.tokenizer_id
        else:
            tokenizer_path = os.path.join(self._settings.model_local_path, "tokenizer")
            if not os.path.exists(tokenizer_path):
                # Fallback to default Hugging Face model
                tokenizer_source = "NeoQuasar/Kronos-Tokenizer-base"
                logger.warning(f"Tokenizer path {tokenizer_path} not found, using default: {tokenizer_source}")
            else:
                tokenizer_source = tokenizer_path

        if self._settings.model_id:
            model_source = self._settings.model_id
        else:
            if not os.path.exists(self._settings.model_local_path):
                # Fallback to default Hugging Face model
                model_source = "NeoQuasar/Kronos-small"
                logger.warning(f"Model path {self._settings.model_local_path} not found, using default: {model_source}")
            else:
                model_source = self._settings.model_local_path

        self._tokenizer = KronosTokenizer.from_pretrained(tokenizer_source)
        self._model = Kronos.from_pretrained(model_source)

        self._model_version = getattr(self._model, "config", {}).get("name", None)
        self._tokenizer_version = getattr(self._tokenizer, "config", {}).get("name", None)

        self._predictor = KronosPredictor(
            model=self._model,
            tokenizer=self._tokenizer,
            device=self._settings.device,
            max_context=self._settings.max_context,
            clip=self._settings.clip_value,
        )

        resolved_device = str(self._predictor.device)
        if self._predictor.device_warning:
            logger.warning(self._predictor.device_warning)

        logger.info(
            "Kronos predictor initialized",
            extra={
                "model_source": model_source,
                "tokenizer_source": tokenizer_source,
                "device_requested": self._settings.device,
                "device_resolved": resolved_device,
            },
        )

    def _resolve_params(self, overrides: Optional[dict]) -> PredictionParams:
        overrides = overrides or {}
        pred_len = overrides.get("pred_len", self._settings.default_pred_len)
        temperature = overrides.get("temperature", self._settings.default_temperature)
        top_k = overrides.get("top_k", self._settings.default_top_k)
        top_p = overrides.get("top_p", self._settings.default_top_p)
        sample_count = overrides.get("sample_count", self._settings.default_sample_count)

        return PredictionParams(
            pred_len=pred_len,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            sample_count=sample_count,
        )

    def predict_single(
        self,
        candles: Sequence[dict],
        timestamps: Sequence[pd.Timestamp],
        prediction_timestamps: Sequence[pd.Timestamp],
        overrides: Optional[dict] = None,
    ) -> pd.DataFrame:
        if not self._predictor:
            raise RuntimeError("Predictor not initialized")

        params = self._resolve_params(overrides)

        df = pd.DataFrame(candles)
        df["timestamps"] = pd.to_datetime(timestamps)

        x_df = df[["open", "high", "low", "close", "volume", "amount"]]
        x_timestamp = df["timestamps"]
        y_timestamp = pd.Series(pd.to_datetime(prediction_timestamps))

        prediction = self._predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=params.pred_len,
            T=params.temperature,
            top_k=params.top_k,
            top_p=params.top_p,
            sample_count=params.sample_count,
            verbose=False,
        )

        prediction = prediction.reset_index().rename(columns={"index": "timestamp"})
        prediction["timestamp"] = pd.to_datetime(prediction["timestamp"])
        return prediction

    def predict_batch(
        self,
        series: Sequence[dict],
    ) -> List[pd.DataFrame]:
        if not self._predictor:
            raise RuntimeError("Predictor not initialized")

        df_list: List[pd.DataFrame] = []
        x_timestamp_list: List[pd.Series] = []
        y_timestamp_list: List[pd.Series] = []
        params_per_series: List[PredictionParams] = []

        for item in series:
            params = self._resolve_params(item.get("overrides"))
            params_per_series.append(params)

            candles = pd.DataFrame(item["candles"])
            timestamps = pd.to_datetime(item["timestamps"])
            prediction_timestamps = pd.to_datetime(item["prediction_timestamps"])

            df = candles[["open", "high", "low", "close", "volume", "amount"]]

            df_list.append(df)
            x_timestamp_list.append(pd.Series(timestamps))
            y_timestamp_list.append(pd.Series(pd.to_datetime(prediction_timestamps)))

        first_params = params_per_series[0]

        def ensure_same(attribute: str) -> None:
            if any(getattr(p, attribute) != getattr(first_params, attribute) for p in params_per_series):
                raise ValueError(f"Batch items must share the same {attribute} override")

        ensure_same("pred_len")
        ensure_same("temperature")
        ensure_same("top_k")
        ensure_same("top_p")
        ensure_same("sample_count")

        predictions = self._predictor.predict_batch(
            df_list=df_list,
            x_timestamp_list=x_timestamp_list,
            y_timestamp_list=y_timestamp_list,
            pred_len=first_params.pred_len,
            T=first_params.temperature,
            top_k=first_params.top_k,
            top_p=first_params.top_p,
            sample_count=first_params.sample_count,
            verbose=False,
        )

        outputs: List[pd.DataFrame] = []
        for df in predictions:
            outputs.append(df.reset_index().rename(columns={"index": "timestamp"}))

        return outputs

    # Async methods for non-blocking inference (Phase 3)

    async def predict_single_async(
        self,
        candles: Sequence[dict],
        timestamps: Sequence[pd.Timestamp],
        prediction_timestamps: Sequence[pd.Timestamp],
        overrides: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> pd.DataFrame:
        """Async prediction for single time series with timeout support.

        Runs prediction in thread pool to avoid blocking the event loop.
        """
        if not self._predictor:
            raise RuntimeError("Predictor not initialized")

        # Use configured timeout if not provided
        timeout_seconds = timeout if timeout is not None else self._settings.inference_timeout
        
        # DEBUG: Log the actual timeout being used
        logger.info(
            f"predict_single_async starting: "
            f"input_len={len(candles)}, "
            f"pred_len={len(prediction_timestamps)}, "
            f"timeout_configured={self._settings.inference_timeout}s, "
            f"timeout_used={timeout_seconds}s"
        )

        try:
            # Run sync prediction in thread pool
            prediction = await asyncio.wait_for(
                asyncio.to_thread(
                    self.predict_single,
                    candles=candles,
                    timestamps=timestamps,
                    prediction_timestamps=prediction_timestamps,
                    overrides=overrides,
                ),
                timeout=timeout_seconds
            )
            return prediction

        except asyncio.TimeoutError as exc:
            logger.error(f"Prediction timeout after {timeout_seconds}s")
            raise TimeoutError(
                f"Prediction timeout after {timeout_seconds} seconds"
            ) from exc

    async def predict_batch_async(
        self,
        series: Sequence[dict],
        timeout: Optional[float] = None,
    ) -> List[pd.DataFrame]:
        """Async prediction for batch with timeout support.

        Runs batch prediction in thread pool to avoid blocking the event loop.
        """
        if not self._predictor:
            raise RuntimeError("Predictor not initialized")

        # Use configured timeout if not provided
        timeout_seconds = timeout if timeout is not None else self._settings.inference_timeout

        try:
            # Run sync batch prediction in thread pool
            predictions = await asyncio.wait_for(
                asyncio.to_thread(
                    self.predict_batch,
                    series=series,
                ),
                timeout=timeout_seconds
            )
            return predictions

        except asyncio.TimeoutError as exc:
            logger.error(f"Batch prediction timeout after {timeout_seconds}s")
            raise TimeoutError(
                f"Batch prediction timeout after {timeout_seconds} seconds"
            ) from exc
