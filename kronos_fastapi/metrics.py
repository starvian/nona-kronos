from typing import Optional

from prometheus_client import Counter, Histogram


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


def record_metrics(route: str, status: str, duration_seconds: Optional[float]) -> None:
    REQUEST_COUNTER.labels(route=route, status=status).inc()
    if duration_seconds is not None:
        REQUEST_LATENCY.labels(route=route).observe(duration_seconds)
