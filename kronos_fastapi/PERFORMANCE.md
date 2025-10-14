# Performance Guide - Kronos FastAPI Microservice

**Last Updated:** 2025-10-14
**Performance Model:** Async Inference with Thread Pool

## Overview

The Kronos FastAPI service uses asynchronous inference to maximize concurrency and prevent event loop blocking. This guide covers performance characteristics, optimization strategies, and troubleshooting.

## Architecture

### Async Inference Model

```
┌─────────────────────────────────────────────────────────┐
│ FastAPI Application (Event Loop)                        │
│                                                          │
│  Request 1 ──┐                                          │
│  Request 2 ──┼─► Async Handler                          │
│  Request 3 ──┘                                          │
│                      │                                   │
│                      ├──► asyncio.to_thread()           │
│                      │                                   │
│              ┌───────▼────────┐                         │
│              │  Thread Pool   │                         │
│              │  (Model Exec)  │                         │
│              │                │                         │
│              │  ┌─────────┐  │                         │
│              │  │Predict 1│  │                         │
│              │  ├─────────┤  │                         │
│              │  │Predict 2│  │                         │
│              │  ├─────────┤  │                         │
│              │  │Predict 3│  │                         │
│              │  └─────────┘  │                         │
│              └────────────────┘                         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- ✅ No event loop blocking
- ✅ Multiple concurrent requests
- ✅ Timeout protection
- ✅ Resource efficiency

## Performance Characteristics

### Baseline Metrics

**Test Environment:**
- CPU: 2 cores
- Memory: 4GB
- Device: CPU (no GPU)
- Model: Kronos-small
- Input: 400 candles → 120 predictions

**Single Request:**
- p50 latency: ~800ms
- p95 latency: ~1.5s
- p99 latency: ~2.0s

**Concurrent Requests (10 users):**
- p50 latency: ~1.2s
- p95 latency: ~2.5s
- p99 latency: ~3.5s
- Throughput: ~8 req/s

**Concurrent Requests (20 users):**
- p50 latency: ~2.0s
- p95 latency: ~4.0s
- p99 latency: ~6.0s
- Throughput: ~6 req/s

### Resource Usage

**Memory:**
- Base: ~200MB (FastAPI + dependencies)
- Model loaded: ~800MB (Kronos-small)
- Per request: +10-20MB (peak during inference)
- Total (2 workers): ~2-3GB

**CPU:**
- Idle: <5%
- Single request: 80-100% (1 core)
- Concurrent (10 req): 180-200% (both cores)

## Timeout Configuration

### Default Timeouts

```bash
# Model inference timeout (per prediction)
KRONOS_INFERENCE_TIMEOUT=30  # seconds

# Total request timeout (includes queue + inference)
KRONOS_REQUEST_TIMEOUT=60    # seconds

# Startup timeout (model loading)
KRONOS_STARTUP_TIMEOUT=120   # seconds
```

### Timeout Behavior

**Inference Timeout:**
- Applied per prediction call
- Returns 504 Gateway Timeout if exceeded
- Logs timeout event
- Increments `kronos_timeouts_total` metric

**When to Adjust:**
- **Increase** if legitimate requests timing out
- **Decrease** for faster failure on slow requests
- Consider input size (larger inputs = longer inference)

### Timeout Examples

```python
# Request with custom timeout
import requests

response = requests.post(
    "http://kronos-api:8000/v1/predict/single",
    json={
        "series_id": "test-1",
        "candles": [...],  # 400 candles
        "timestamps": [...],
        "prediction_timestamps": [...]
    },
    timeout=45  # Client-side timeout
)
```

**Note:** Client timeout should be > server inference timeout

## Worker Configuration

### Determining Worker Count

**Formula:** `workers = (2 * CPU_cores) + 1`

**Examples:**
- 2 CPU cores → 4-5 workers
- 4 CPU cores → 8-9 workers
- 8 CPU cores → 16-17 workers

### Docker Compose Configuration

```yaml
services:
  kronos-api:
    command: >
      uvicorn services.kronos_fastapi.main:app
      --host 0.0.0.0
      --port 8000
      --workers 4
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

### Worker Optimization Tips

1. **Start with fewer workers** - Test with 2, then scale up
2. **Monitor memory** - Each worker loads the model (~800MB)
3. **CPU-bound workload** - More workers ≠ better performance
4. **Test under load** - Find sweet spot for your hardware

## Load Testing

### Using Locust

**Install:**
```bash
pip install locust
```

**Run Load Test:**
```bash
cd tests/load
locust -f locustfile.py --host=http://localhost:8000

# Or headless mode
locust -f locustfile.py --host=http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 5m --headless
```

**Web UI:** http://localhost:8089

### Test Scenarios

**1. Steady State Test** (Baseline)
- Users: 10
- Spawn rate: 2/s
- Duration: 5 minutes
- Goal: Establish baseline metrics

**2. Stress Test** (Find Limits)
- Users: Start at 10, increase to 100
- Spawn rate: 5/s
- Duration: 10 minutes
- Goal: Find breaking point

**3. Spike Test** (Resilience)
- Users: 10 → 100 → 10
- Rapid spike
- Duration: 5 minutes
- Goal: Test recovery

**4. Endurance Test** (Stability)
- Users: 20
- Spawn rate: 5/s
- Duration: 30 minutes
- Goal: Detect memory leaks

### Interpreting Results

**Good Performance:**
- p95 < 2s
- Error rate < 1%
- No timeouts
- Stable memory usage

**Performance Issues:**
- p95 > 5s → Too many workers or not enough CPU
- High error rate → Check logs for exceptions
- Many timeouts → Increase timeout or optimize model
- Memory growth → Memory leak (restart workers)

## Performance Metrics

### Prometheus Metrics

**Request Metrics:**
```prometheus
# Total requests by route and status
kronos_requests_total{route="/v1/predict/single", status="success"}

# Request latency histogram
kronos_request_duration_seconds{route="/v1/predict/single"}
```

**Performance Metrics:**
```prometheus
# Model inference time (excluding pre/post processing)
kronos_model_inference_seconds{endpoint="/v1/predict/single"}

# Concurrent requests (gauge)
kronos_concurrent_requests

# Timeouts by endpoint
kronos_timeouts_total{endpoint="/v1/predict/single"}

# Input size distribution
kronos_prediction_input_size{endpoint="/v1/predict/single"}
```

**Example Queries:**

```prometheus
# p95 latency over last 5 minutes
histogram_quantile(0.95,
  rate(kronos_request_duration_seconds_bucket[5m])
)

# Request rate by status
rate(kronos_requests_total[1m])

# Timeout percentage
rate(kronos_timeouts_total[5m]) /
rate(kronos_requests_total[5m]) * 100
```

### Grafana Dashboards

See `monitoring/grafana/kronos-dashboard.json` for:
- Request rate and latency
- Error and timeout rates
- Concurrent requests
- Resource usage (CPU, memory)

## Optimization Strategies

### 1. Model Optimization

**Current:** Kronos-small (24.7M params)
**Alternative:** Kronos-mini (4.1M params) - Faster but less accurate

**Quantization** (Future):
- INT8 quantization can reduce model size and latency
- Requires model conversion

### 2. Batch Optimization

**Use batch endpoint for multiple series:**
```python
# Instead of 10 single requests
for series in series_list:
    predict_single(series)

# Use one batch request
predict_batch(series_list)
```

**Benefits:**
- Amortized overhead
- Better GPU utilization (if using GPU)
- Lower latency per series

### 3. Input Size Optimization

**Recommendation:**
- Use minimum necessary lookback window
- Default: 400 candles (works well)
- Smaller inputs → faster inference

**Trade-off:**
- Smaller window → Less context → Potentially lower accuracy

### 4. Worker Tuning

**Symptom:** High p95 latency, low CPU usage
**Solution:** Reduce workers (contention)

**Symptom:** High p95 latency, high CPU usage
**Solution:** Need more CPU cores or optimize model

**Symptom:** Memory errors, OOM
**Solution:** Reduce workers or increase memory

### 5. Connection Pooling

**For consumers:**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retries = Retry(total=3, backoff_factor=0.1)
adapter = HTTPAdapter(
    max_retries=retries,
    pool_connections=10,
    pool_maxsize=20
)
session.mount('http://', adapter)

# Reuse session for all requests
response = session.post(url, json=data)
```

## Troubleshooting

### Problem: Slow Requests

**Symptoms:**
- p95 > 5 seconds
- High inference time

**Diagnosis:**
```bash
# Check metrics
curl http://localhost:8000/v1/metrics | grep inference

# Check logs for slow requests
docker logs kronos-api | grep "latency_ms"
```

**Solutions:**
1. Check CPU usage (should be high during inference)
2. Reduce concurrent requests
3. Increase timeout if legitimate
4. Consider smaller model (Kronos-mini)
5. Optimize input size

### Problem: Timeouts

**Symptoms:**
- 504 Gateway Timeout responses
- `kronos_timeouts_total` increasing

**Diagnosis:**
```bash
# Check timeout metrics
curl http://localhost:8000/v1/metrics | grep timeout

# Check timeout settings
docker exec kronos-api env | grep TIMEOUT
```

**Solutions:**
1. Increase `KRONOS_INFERENCE_TIMEOUT` if needed
2. Reduce input size
3. Check if model is CPU/GPU bound
4. Optimize model (quantization, smaller variant)

### Problem: Memory Leaks

**Symptoms:**
- Memory usage grows over time
- OOM errors after running for hours

**Diagnosis:**
```bash
# Monitor memory usage
docker stats kronos-api

# Check for memory leaks in logs
docker logs kronos-api | grep -i memory
```

**Solutions:**
1. Restart workers periodically (using uvicorn --max-requests)
2. Update dependencies (potential memory leak fixes)
3. Profile with memory profiler

**Workaround:**
```yaml
# Add to docker-compose.yml
command: >
  uvicorn services.kronos_fastapi.main:app
  --host 0.0.0.0
  --port 8000
  --workers 4
  --max-requests 1000  # Restart worker after 1000 requests
```

### Problem: Event Loop Blocking

**Symptoms:**
- All requests slow down together
- `kronos_concurrent_requests` stuck at 1

**Diagnosis:**
```bash
# Check if using async methods
docker logs kronos-api | grep "async"

# Check concurrent requests metric
curl http://localhost:8000/v1/metrics | grep concurrent
```

**Solutions:**
- Verify routes use `await manager.predict_single_async()`
- Check for synchronous blocking calls in middleware
- Review logs for blocking operations

### Problem: High Error Rate

**Symptoms:**
- Many 500 errors
- `kronos_requests_total{status="error"}` high

**Diagnosis:**
```bash
# Check error logs
docker logs kronos-api | grep ERROR

# Check error metrics
curl http://localhost:8000/v1/metrics | grep error
```

**Solutions:**
1. Review error logs for root cause
2. Check input validation
3. Verify model loaded correctly
4. Check for resource exhaustion

## Performance Checklist

### Pre-Deployment

- [ ] Load tested with expected traffic
- [ ] Worker count optimized
- [ ] Timeout values appropriate
- [ ] Memory limits configured
- [ ] Metrics collection enabled
- [ ] Dashboards created

### Post-Deployment

- [ ] Monitor p95 latency (should be < 2s)
- [ ] Monitor error rate (should be < 1%)
- [ ] Monitor timeout rate (should be < 0.1%)
- [ ] Monitor memory usage (should be stable)
- [ ] Monitor concurrent requests
- [ ] Set up alerts for anomalies

## Performance Targets

### Production Targets

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| p50 latency | < 1s | < 2s | > 5s |
| p95 latency | < 2s | < 5s | > 10s |
| p99 latency | < 5s | < 10s | > 20s |
| Error rate | < 0.1% | < 1% | > 5% |
| Timeout rate | < 0.05% | < 0.5% | > 2% |
| Memory usage | < 3GB | < 4GB | > 4.5GB |
| CPU usage | 70-90% | 50-95% | > 98% |

### SLA Example

**99.9% Uptime SLA:**
- Allowed downtime: 43 minutes/month
- Target p95 latency: < 2 seconds
- Target error rate: < 0.1%

## Advanced Topics

### GPU Acceleration

**Enable GPU:**
```yaml
# docker-compose.yml
services:
  kronos-api:
    environment:
      - KRONOS_DEVICE=cuda:0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**Expected Improvement:**
- 2-5x faster inference
- Lower CPU usage
- Higher throughput

### Horizontal Scaling

**Multiple Instances:**
```yaml
services:
  kronos-api:
    deploy:
      replicas: 3  # Run 3 instances
```

**Load Balancer Required:**
- Use Traefik, Nginx, or HAProxy
- Distribute requests across instances
- Health check integration

### Caching (Future Enhancement)

**Prediction Result Caching:**
- Cache predictions for identical inputs
- Redis for distributed caching
- TTL: 5-10 minutes
- Can reduce latency by 90% for repeated requests

## References

- [FastAPI Performance](https://fastapi.tiangolo.com/deployment/concepts/)
- [Uvicorn Deployment](https://www.uvicorn.org/deployment/)
- [Locust Documentation](https://docs.locust.io/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)

---

**Performance Model Version:** 1.0 (Async Inference)
**Last Performance Test:** 2025-10-14
**Next Review:** 2025-11-14 (1 month)
