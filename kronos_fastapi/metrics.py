from typing import Optional

from prometheus_client import Counter, Histogram, Gauge


REQUEST_COUNTER = Counter(
    "kronos_requests_total",
    "Total number of Kronos prediction requests",
    ["route", "status"],
)


REQUEST_LATENCY = Histogram(
    "kronos_request_duration_seconds",
    "Latency of Kronos prediction requests",
    ["route"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)

# Security metrics
SECURITY_EVENTS = Counter(
    'kronos_security_events_total',
    'Security events by type and container',
    ['event', 'container']
)

RATE_LIMIT_HITS = Counter(
    'kronos_rate_limit_hits_total',
    'Rate limit hits by container',
    ['container']
)

REQUEST_SIZE_REJECTIONS = Counter(
    'kronos_request_size_rejections_total',
    'Rejected requests due to size limit',
    ['container']
)

# Performance metrics (Phase 3)
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

PREDICTION_INPUT_SIZE = Histogram(
    'kronos_prediction_input_size',
    'Size of prediction input (number of candles)',
    ['endpoint'],
    buckets=[50, 100, 200, 400, 800, 1600]
)


def record_metrics(route: str, status: str, duration_seconds: Optional[float]) -> None:
    REQUEST_COUNTER.labels(route=route, status=status).inc()
    if duration_seconds is not None:
        REQUEST_LATENCY.labels(route=route).observe(duration_seconds)
