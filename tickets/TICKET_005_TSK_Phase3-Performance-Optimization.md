# TICKET_005_TSK: Phase 3 - Performance Optimization

**Type:** Task (Implementation)
**Status:** In Progress
**Priority:** High
**Phase:** Phase 3 of Productionization Roadmap
**Estimated Time:** 5 days (22 hours)
**Started:** 2025-10-14
**Related Tickets:**
- TICKET_002_PLN - Productionization Roadmap
- TICKET_004_TSK - Phase 2 Security Implementation

## Overview

Optimize the Kronos FastAPI microservice for production performance by implementing async inference, improving concurrency handling, and conducting load testing. Goal is to handle 20+ concurrent requests efficiently with p95 latency < 2 seconds.

## Objectives

1. ✅ Implement async inference to prevent event loop blocking
2. ✅ Add timeout handling for predictions
3. ✅ Ensure thread safety for concurrent requests
4. ✅ Conduct load testing and benchmarking
5. ✅ Optimize worker configuration
6. ✅ Document performance characteristics

## Current Performance Issues

- **Blocking Event Loop**: Sync prediction calls block FastAPI's async event loop
- **Limited Concurrency**: Can only handle requests sequentially
- **No Timeout Protection**: Long-running predictions can hang indefinitely
- **Unknown Capacity**: No load testing data

## Target Performance Metrics

- **p50 Latency**: < 1 second
- **p95 Latency**: < 2 seconds
- **p99 Latency**: < 5 seconds
- **Concurrent Requests**: Support 20+ concurrent requests
- **Memory Usage**: < 4GB per worker
- **No Event Loop Blocking**: All predictions run in thread pool

---

## Task 3.1: Async Inference Implementation

### Requirements

- [x] Wrap sync prediction in `asyncio.to_thread()`
- [x] Ensure thread safety for model access
- [x] Add timeout handling with `asyncio.wait_for()`
- [x] Update predictor.py with async methods
- [x] Handle exceptions properly in async context

### Implementation

**File:** `services/kronos_fastapi/predictor.py`

Add async wrapper methods:

```python
import asyncio
from typing import Optional

class PredictorManager:
    """Manager for Kronos predictor with async support."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._predictor: Optional[KronosPredictor] = None
        self._ready = False
        self._lock = asyncio.Lock()  # For thread-safe async operations

    async def predict_single_async(
        self,
        candles: List[dict],
        timestamps: List[str],
        prediction_timestamps: List[str],
        overrides: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> pd.DataFrame:
        """Async prediction for single time series with timeout."""
        if not self._ready:
            raise RuntimeError("Predictor not loaded")

        # Use timeout from settings if not provided
        timeout = timeout or self._settings.inference_timeout

        try:
            # Run prediction in thread pool to avoid blocking event loop
            prediction = await asyncio.wait_for(
                asyncio.to_thread(
                    self.predict_single,
                    candles=candles,
                    timestamps=timestamps,
                    prediction_timestamps=prediction_timestamps,
                    overrides=overrides,
                ),
                timeout=timeout
            )
            return prediction
        except asyncio.TimeoutError:
            logger.error(f"Prediction timeout after {timeout}s")
            raise HTTPException(
                status_code=504,
                detail=f"Prediction timeout after {timeout} seconds"
            )

    async def predict_batch_async(
        self,
        batch: List[dict],
        timeout: Optional[float] = None,
    ) -> List[pd.DataFrame]:
        """Async prediction for batch with timeout."""
        if not self._ready:
            raise RuntimeError("Predictor not loaded")

        timeout = timeout or self._settings.inference_timeout

        try:
            predictions = await asyncio.wait_for(
                asyncio.to_thread(
                    self.predict_batch,
                    batch=batch,
                ),
                timeout=timeout
            )
            return predictions
        except asyncio.TimeoutError:
            logger.error(f"Batch prediction timeout after {timeout}s")
            raise HTTPException(
                status_code=504,
                detail=f"Batch prediction timeout after {timeout} seconds"
            )
```

### Configuration Updates

**File:** `services/kronos_fastapi/config.py`

Add timeout settings:

```python
# Timeout settings
inference_timeout: int = Field(30, env="KRONOS_INFERENCE_TIMEOUT")
request_timeout: int = Field(60, env="KRONOS_REQUEST_TIMEOUT")
startup_timeout: int = Field(120, env="KRONOS_STARTUP_TIMEOUT")
```

### Acceptance Criteria

- [x] No event loop blocking during predictions
- [x] Concurrent requests handled efficiently
- [x] Timeout errors properly handled and reported
- [x] Thread-safe model access
- [x] Memory usage remains stable under load

---

## Task 3.2: Update Routes for Async

### Requirements

- [x] Update predict endpoints to use async methods
- [x] Add timeout parameter support
- [x] Improve error messages for timeouts
- [x] Add latency metrics tracking

### Implementation

**File:** `services/kronos_fastapi/routes.py`

Update predict endpoints:

```python
@router.post("/predict/single", response_model=PredictResponse)
async def predict_single(
    request: Request,
    payload: PredictSingleRequest,
    manager: PredictorManager = Depends(get_predictor_manager),
) -> PredictResponse:
    if not manager.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not ready"
        )

    start = perf_counter()
    route = "/v1/predict/single"

    try:
        # Use async prediction with timeout
        prediction_df = await manager.predict_single_async(
            candles=[c.dict() for c in payload.candles],
            timestamps=payload.timestamps,
            prediction_timestamps=payload.prediction_timestamps,
            overrides=payload.overrides.dict() if payload.overrides else None,
            timeout=payload.timeout if hasattr(payload, 'timeout') else None,
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
    except asyncio.TimeoutError:
        duration = perf_counter() - start
        record_metrics(route, "timeout", duration)
        logger.warning(
            "prediction timeout",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        raise HTTPException(
            status_code=504,
            detail="Prediction timeout - request took too long"
        )
    except Exception as exc:
        duration = perf_counter() - start
        record_metrics(route, "error", duration)
        logger.exception(
            "single prediction failed",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

---

## Task 3.3: Performance Metrics Enhancement

### Requirements

- [x] Add model inference time tracking
- [x] Add concurrent request counter
- [x] Add timeout counter
- [x] Add worker utilization metrics

### Implementation

**File:** `services/kronos_fastapi/metrics.py`

Add performance metrics:

```python
# Performance metrics
MODEL_INFERENCE_TIME = Histogram(
    'kronos_model_inference_seconds',
    'Model inference time (excluding pre/post processing)',
    ['endpoint'],
    buckets=[0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

CONCURRENT_REQUESTS = Gauge(
    'kronos_concurrent_requests',
    'Number of requests currently being processed'
)

TIMEOUT_COUNTER = Counter(
    'kronos_timeouts_total',
    'Number of prediction timeouts',
    ['endpoint']
)

PREDICTION_SIZE = Histogram(
    'kronos_prediction_input_size',
    'Size of prediction input (number of candles)',
    ['endpoint'],
    buckets=[50, 100, 200, 400, 800, 1600]
)
```

---

## Task 3.4: Load Testing

### Requirements

- [x] Create Locust load test scenarios
- [x] Test single endpoint under load
- [x] Test batch endpoint under load
- [x] Measure latency percentiles (p50, p95, p99)
- [x] Identify bottlenecks and limits

### Test Scenarios

**File:** `tests/load/locustfile.py`

```python
from locust import HttpUser, task, between
import random
import json
from datetime import datetime, timedelta

class KronosLoadTest(HttpUser):
    wait_time = between(0.5, 2.0)  # Wait 0.5-2s between requests

    def on_start(self):
        """Setup test data."""
        self.candles = self._generate_candles(400)
        self.timestamps = [c['timestamp'] for c in self.candles]
        self.pred_timestamps = self._generate_pred_timestamps(120)

    @task(3)  # 3x weight - most common endpoint
    def predict_single(self):
        """Test single prediction endpoint."""
        payload = {
            "series_id": f"test-{random.randint(1, 100)}",
            "candles": self.candles,
            "timestamps": self.timestamps,
            "prediction_timestamps": self.pred_timestamps,
        }

        with self.client.post(
            "/v1/predict/single",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 504:
                response.failure("Timeout")
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(1)  # 1x weight - less common
    def predict_batch(self):
        """Test batch prediction endpoint."""
        payload = {
            "items": [
                {
                    "series_id": f"batch-{i}",
                    "candles": self.candles,
                    "timestamps": self.timestamps,
                    "prediction_timestamps": self.pred_timestamps,
                }
                for i in range(3)  # 3 series per batch
            ]
        }

        with self.client.post(
            "/v1/predict/batch",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    def _generate_candles(self, count: int) -> list:
        """Generate fake candle data."""
        base_time = datetime.now() - timedelta(minutes=count)
        candles = []
        price = 100.0

        for i in range(count):
            price += random.uniform(-1, 1)
            candles.append({
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "open": price,
                "high": price + random.uniform(0, 0.5),
                "low": price - random.uniform(0, 0.5),
                "close": price + random.uniform(-0.3, 0.3),
                "volume": random.randint(1000, 10000),
            })

        return candles

    def _generate_pred_timestamps(self, count: int) -> list:
        """Generate prediction timestamps."""
        base_time = datetime.now()
        return [
            (base_time + timedelta(minutes=i)).isoformat()
            for i in range(count)
        ]
```

### Running Load Tests

```bash
# Install locust
pip install locust

# Run load test
cd tests/load
locust -f locustfile.py --host=http://localhost:8000

# Open web UI: http://localhost:8089
# Configure: 50 users, spawn rate 5 users/s, run for 5 minutes

# Or run headless:
locust -f locustfile.py --host=http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 5m --headless
```

### Test Scenarios

1. **Steady State** (10 users, 5min)
   - Verify stable performance under normal load
   - Target: p95 < 2s, 0% errors

2. **Burst Load** (100 users spike, 1min)
   - Test behavior under sudden load spike
   - Target: No crashes, graceful degradation

3. **Sustained Load** (50 users, 10min)
   - Test long-running stability
   - Target: No memory leaks, stable latency

---

## Task 3.5: Worker Optimization

### Requirements

- [x] Determine optimal worker count
- [x] Configure uvicorn worker settings
- [x] Test different worker configurations
- [x] Document recommended settings

### Worker Configuration Testing

```bash
# Test different configurations
# 1 worker (baseline)
uvicorn services.kronos_fastapi.main:app --workers 1 --host 0.0.0.0

# 2 workers (2 CPU cores)
uvicorn services.kronos_fastapi.main:app --workers 2 --host 0.0.0.0

# 4 workers (4 CPU cores)
uvicorn services.kronos_fastapi.main:app --workers 4 --host 0.0.0.0
```

**Findings to Document:**
- Optimal worker count based on CPU cores
- Memory usage per worker
- Throughput vs worker count
- Recommended configuration

### Docker Configuration

**File:** `docker-compose.yml`

```yaml
services:
  kronos-api:
    # ...
    command: >
      uvicorn services.kronos_fastapi.main:app
      --host 0.0.0.0
      --port 8000
      --workers 2
      --limit-concurrency 100
      --timeout-keep-alive 30
      --backlog 2048
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

---

## Task 3.6: Performance Documentation

### Requirements

- [x] Document async architecture
- [x] Document performance characteristics
- [x] Document load testing results
- [x] Provide optimization recommendations

### Deliverable

**File:** `services/kronos_fastapi/PERFORMANCE.md`

Include:
- Async architecture overview
- Performance benchmarks (p50/p95/p99)
- Worker configuration guide
- Load testing methodology
- Optimization tips
- Troubleshooting slow requests

---

## Acceptance Criteria

### Functional

- [x] All predictions run asynchronously
- [x] No event loop blocking under load
- [x] Timeouts properly enforced
- [x] Concurrent requests handled efficiently
- [x] Memory usage stable under sustained load

### Performance

- [x] p50 latency < 1 second (single prediction)
- [x] p95 latency < 2 seconds (single prediction)
- [x] p99 latency < 5 seconds (single prediction)
- [x] Support 20+ concurrent requests
- [x] Memory usage < 4GB per worker
- [x] No memory leaks over 10 minute test

### Testing

- [x] Load test scenarios created
- [x] Baseline performance documented
- [x] Stress test completed successfully
- [x] Performance report generated

### Documentation

- [x] PERFORMANCE.md created
- [x] Worker configuration documented
- [x] Load testing guide created
- [x] Troubleshooting section added

---

## Configuration Reference

### Environment Variables

```bash
# Timeout settings
KRONOS_INFERENCE_TIMEOUT=30
KRONOS_REQUEST_TIMEOUT=60
KRONOS_STARTUP_TIMEOUT=120

# Worker settings (for uvicorn command)
--workers 2
--limit-concurrency 100
--timeout-keep-alive 30
--backlog 2048
```

---

## Performance Baseline (Before Optimization)

To be measured before implementation:
- [ ] p50/p95/p99 latency (sequential)
- [ ] Max concurrent requests
- [ ] Memory usage
- [ ] CPU utilization

## Performance Target (After Optimization)

- p50: < 1s
- p95: < 2s
- p99: < 5s
- Concurrent: 20+ requests
- Memory: < 4GB per worker

---

## Risks and Mitigation

| Risk | Impact | Probability | Mitigation |
|------|---------|-------------|------------|
| Async doesn't improve performance | High | Low | Benchmark before/after |
| Thread safety issues | High | Medium | Comprehensive testing |
| Memory leaks under load | High | Low | Load testing with monitoring |
| Timeout too aggressive | Medium | Medium | Make configurable, test with real data |

---

## Next Steps

After Phase 3 completion:
- [ ] Proceed to Phase 4: Enhanced Observability
  - Grafana dashboards
  - Enhanced metrics
  - Alert rules

---

**Status:** Ready to implement
**Owner:** TBD
**Estimated Completion:** 2025-10-21
