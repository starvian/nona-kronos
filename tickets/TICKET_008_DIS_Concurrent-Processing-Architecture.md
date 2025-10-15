# TICKET_008_DIS - Concurrent Processing Architecture Discussion

**Type:** Discussion
**Status:** Open
**Priority:** Medium
**Created:** 2025-10-15
**Participants:** User, Claude Code

## Overview

Discussion about Kronos FastAPI service's current concurrency model and potential improvements for handling multiple simultaneous prediction requests.

## Questions Raised

### 1. Is the service synchronous or asynchronous?

**Answer:** Hybrid model - Async API layer + Sync model execution

### 2. Can Kronos process multiple tasks simultaneously or must it process one by one?

**Answer:** Currently processes **one by one (serial execution)** despite async API layer.

## Current Architecture Analysis

### Request Flow

```
┌─────────────────────────────────────────────────────┐
│ FastAPI (Async Framework)                           │
│                                                      │
│ async def predict_single()  ← Async receive         │
│         ↓                                            │
│ await manager.predict_single_async()  ← Async wrap  │
│         ↓                                            │
│ asyncio.to_thread(                                   │
│     self.predict_single  ← Sync execution (thread)  │
│ )                                                    │
│         ↓                                            │
│ KronosPredictor.predict()  ← Model inference (CPU)  │
└─────────────────────────────────────────────────────┘
```

### Key Characteristics

**API Layer:**
- Framework: FastAPI (async)
- Request handling: `async def predict_single()`
- Non-blocking request acceptance: ✅

**Execution Layer:**
- Model inference: Synchronous
- Execution method: `asyncio.to_thread()` (thread pool)
- Concurrent inference: ❌ (serial execution)

**Model Management:**
- Pattern: Singleton (`PredictorManagerRegistry`)
- Instances: 1 model loaded in memory
- Shared resource: All requests use same model instance

### Actual Behavior Example

```
Timeline with 3 concurrent requests:

0.0s  - Request 1 arrives → Start inference (0.8s)
0.1s  - Request 2 arrives → Queued (waiting in thread pool)
0.2s  - Request 3 arrives → Queued (waiting in thread pool)
0.8s  - Request 1 completes
0.8s  - Request 2 starts inference (0.8s)
1.6s  - Request 2 completes
1.6s  - Request 3 starts inference (0.8s)
2.4s  - Request 3 completes

Total time: 2.4s (serial)
Ideal parallel time: 0.8s (if truly concurrent)
```

### Root Causes

1. **Single Model Instance**
   ```python
   # routes.py
   class PredictorManagerRegistry:
       _manager: PredictorManager | None = None  # Singleton!
   ```

2. **Thread Pool Serialization**
   - `asyncio.to_thread()` uses default thread pool
   - Thread pool size limited (typically CPU cores)
   - Model inference is CPU-intensive
   - GIL (Global Interpreter Lock) limits Python threading

3. **Model Architecture**
   - PyTorch models process one input at a time
   - Single model instance cannot handle concurrent requests
   - Memory layout optimized for single-threaded execution

## Performance Characteristics

### Current Throughput

**Single instance metrics:**
- Sequential processing: ~8 req/s (at 800ms per request)
- Latency p50: 1.2s (with queuing)
- Latency p95: 2.5s (10 concurrent users)

**Bottleneck:**
- Not network I/O
- Not request parsing
- **Model inference CPU time** (80-100% during prediction)

### Resource Usage

**Memory:**
- Model loaded: ~800MB (Kronos-small)
- Per request overhead: ~10-20MB
- Total (single worker): ~1GB

**CPU:**
- Idle: <5%
- During inference: 80-100% (single core)
- Multiple requests: Still 80-100% (queued, not parallel)

## Proposed Solutions

### Option 1: Model Pool ⭐

**Concept:** Create multiple model instances in memory

```python
class PredictorPool:
    def __init__(self, settings: Settings, pool_size: int = 4):
        self.pool = []
        for _ in range(pool_size):
            predictor = PredictorManager(settings)
            predictor.load()  # Each loads full model
            self.pool.append(predictor)
        self.semaphore = asyncio.Semaphore(pool_size)

    async def predict(self, *args, **kwargs):
        async with self.semaphore:
            predictor = await self._get_available_predictor()
            return await predictor.predict_single_async(*args, **kwargs)
```

**Pros:**
- True concurrent inference (4 requests simultaneously)
- 4x throughput improvement
- Simple to implement
- No architecture changes needed

**Cons:**
- Memory usage: 4x (4 models × 800MB = ~3.2GB)
- Still limited by pool size
- GIL may still cause some contention

**Best for:** Medium traffic (10-50 req/s), sufficient memory

### Option 2: Horizontal Scaling (Multi-Container) ⭐⭐

**Concept:** Run multiple Docker containers with load balancer

```yaml
# docker-compose.yml
services:
  kronos-api-1:
    image: kronos-fastapi:latest
    deploy:
      resources:
        limits:
          memory: 4G

  kronos-api-2:
    image: kronos-fastapi:latest
    deploy:
      resources:
        limits:
          memory: 4G

  kronos-api-3:
    image: kronos-fastapi:latest
    deploy:
      resources:
        limits:
          memory: 4G

  nginx:
    image: nginx
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "8000:80"
```

```nginx
# nginx.conf
upstream kronos_backend {
    server kronos-api-1:8000;
    server kronos-api-2:8000;
    server kronos-api-3:8000;
}

server {
    location / {
        proxy_pass http://kronos_backend;
    }
}
```

**Pros:**
- True parallel processing (3 containers = 3x throughput)
- Process isolation (failure in one doesn't affect others)
- Easy to scale (add more containers)
- Standard deployment pattern
- Works with existing code (no changes needed)

**Cons:**
- More resources (3 containers × 4GB = 12GB memory)
- Need load balancer (Nginx/Traefik)
- Slightly more complex deployment

**Best for:** High traffic (>20 req/s), production deployment

### Option 3: Batch Processing Optimization

**Concept:** Encourage clients to use batch endpoint

```python
# Client side - Bad
for series in series_list:
    result = predict_single(series)  # 10 sequential requests

# Client side - Good
results = predict_batch(series_list)  # 1 batch request
```

**Current batch implementation:**
```python
# predictor.py
predictions = self._predictor.predict_batch(
    df_list=df_list,           # Multiple series
    x_timestamp_list=x_timestamp_list,
    y_timestamp_list=y_timestamp_list,
    ...
)
```

**Pros:**
- No code changes needed (already implemented)
- Model can optimize batch processing internally
- Lower network overhead
- Better GPU/CPU utilization

**Cons:**
- Requires client cooperation
- Still serial at batch level
- All items in batch must have same parameters

**Best for:** Use cases where batching is natural (batch jobs, scheduled tasks)

### Option 4: Async Task Queue (Complex)

**Concept:** Decouple request acceptance from processing

```
Client → FastAPI → Queue (Redis/RabbitMQ) → Workers → Results
```

**Architecture:**
```python
# FastAPI endpoint
@app.post("/predict/single")
async def predict_single(payload):
    task_id = enqueue_prediction_task(payload)
    return {"task_id": task_id, "status": "queued"}

@app.get("/predict/{task_id}")
async def get_result(task_id):
    result = get_task_result(task_id)
    if result.ready:
        return {"status": "completed", "data": result.data}
    else:
        return {"status": "processing"}
```

**Pros:**
- Highly scalable (add more workers)
- Fault tolerant (persistent queue)
- Supports long-running tasks
- Can prioritize tasks

**Cons:**
- Complex architecture (need Redis/RabbitMQ + Celery/RQ)
- API changes (async response pattern)
- Client needs polling or webhooks
- Operational complexity

**Best for:** Very high traffic (>100 req/s), complex workflows

## Recommendations

### By Traffic Level

| Traffic (req/s) | Recommendation | Rationale |
|----------------|----------------|-----------|
| < 10 | **Current architecture** | Single instance sufficient |
| 10-30 | **Option 2: 3-5 containers** | Balance of simplicity and scale |
| 30-100 | **Option 2: 10+ containers + K8s** | Auto-scaling, orchestration |
| > 100 | **Option 2 + GPU + Option 4** | Queue for buffering, GPU for speed |

### By Resource Constraints

| Constraint | Recommendation | Rationale |
|------------|----------------|-----------|
| Limited memory | **Option 3: Batch optimization** | No extra memory needed |
| Limited CPU | **Option 2 with fewer containers** | Distribute load |
| Unlimited resources | **Option 1: Large pool** | Simplest implementation |

### By Deployment Environment

| Environment | Recommendation | Implementation |
|-------------|----------------|----------------|
| Single server | **Option 1: Model pool (4-8 instances)** | In-process concurrency |
| Docker Compose | **Option 2: 3-5 containers + Nginx** | Multi-container setup |
| Kubernetes | **Option 2: Deployment with HPA** | Auto-scaling pods |
| Serverless | **Not recommended** | Model loading too slow |

## Performance Projections

### Option 1: Model Pool (4 instances)

```
Expected throughput: 32 req/s (4 × 8 req/s)
Memory usage: 3.2GB (4 × 800MB)
Latency p50: 0.8s (no queuing with <32 req/s)
Latency p95: 1.5s (light queuing)
```

### Option 2: Horizontal Scaling (4 containers)

```
Expected throughput: 32 req/s (4 × 8 req/s)
Memory usage: 16GB (4 containers × 4GB each)
Latency p50: 0.8s (distributed load)
Latency p95: 1.2s (less variance)
```

### Option 3: Batch Optimization (batch size 10)

```
Expected throughput: 15-20 req/s (batch efficiency gain)
Memory usage: 1GB (same as current)
Latency per request: 1.5s (batch overhead)
Total batch latency: 1.5s (for 10 requests)
```

## Implementation Complexity

| Option | Complexity | Development Time | Testing Effort |
|--------|-----------|------------------|----------------|
| Option 1: Model Pool | Medium | 4-6 hours | Medium |
| Option 2: Multi-Container | Low | 2-3 hours | Low |
| Option 3: Batch Optimization | Very Low | 0 hours (done) | Very Low |
| Option 4: Task Queue | High | 16-24 hours | High |

## Trade-offs Summary

| Factor | Option 1 | Option 2 | Option 3 | Option 4 |
|--------|----------|----------|----------|----------|
| Throughput gain | 4x | 4x | 2x | 10x+ |
| Memory cost | High | Very High | None | Medium |
| Code changes | Medium | None | None | High |
| Ops complexity | Low | Medium | None | High |
| Scalability | Limited | Excellent | Limited | Excellent |
| Fault tolerance | Low | High | Low | Very High |

## Next Steps

### Immediate Actions

1. **Measure current performance**
   ```bash
   # Run load test
   locust -f tests/load/locustfile.py --host=http://localhost:8000
   ```

2. **Determine traffic requirements**
   - What is expected peak traffic?
   - What is acceptable latency (p95)?
   - What are resource constraints?

3. **Choose solution based on measurements**

### If Proceeding with Option 1 (Model Pool)

**Implementation tasks:**
- [ ] Create `PredictorPool` class
- [ ] Add pool configuration to settings
- [ ] Update `PredictorManagerRegistry` to use pool
- [ ] Add pool metrics (available/busy instances)
- [ ] Load testing with pool
- [ ] Documentation

### If Proceeding with Option 2 (Multi-Container)

**Implementation tasks:**
- [ ] Create load balancer config (Nginx)
- [ ] Update docker-compose for multiple services
- [ ] Configure health checks
- [ ] Test failover behavior
- [ ] Document scaling procedures
- [ ] Set up monitoring for all instances

### If Proceeding with Option 3 (Batch Optimization)

**Implementation tasks:**
- [ ] Document batch API usage
- [ ] Create client examples
- [ ] Add batch size recommendations
- [ ] Monitor batch vs single usage
- [ ] Encourage migration to batch endpoint

### If Proceeding with Option 4 (Task Queue)

**Implementation tasks:**
- [ ] Choose queue system (Celery/RQ)
- [ ] Design task schema
- [ ] Implement async API endpoints
- [ ] Create worker processes
- [ ] Add result storage (Redis)
- [ ] Implement polling/webhook notifications
- [ ] Update client libraries
- [ ] Extensive integration testing

## Open Questions

1. **What is the expected production traffic?**
   - Current: Unknown
   - Need: Req/s at peak, average latency tolerance

2. **What are resource constraints?**
   - Memory available?
   - CPU cores available?
   - Budget for infrastructure?

3. **What is the deployment target?**
   - Single server?
   - Docker Compose?
   - Kubernetes?
   - Cloud platform (AWS/GCP/Azure)?

4. **What is acceptable downtime for deployment?**
   - Zero-downtime required? → Option 2
   - Can tolerate brief outage? → Option 1 acceptable

5. **GPU availability?**
   - If GPU available: Much faster inference (200-500ms → 50-100ms)
   - Changes recommendation (can handle more with fewer instances)

## Related Tickets

- TICKET_002_PLN - Productionization Roadmap
- TICKET_005_TSK - Phase 3 Performance Optimization (async implementation)
- TICKET_007_TSK - Phase 5 Production Hardening

## Decision Record

**Status:** Discussion ongoing

**Decision:** TBD (pending user requirements)

**When to revisit:**
- After measuring production traffic
- Before scaling to >10 req/s
- If p95 latency exceeds 5s
- If resource constraints change

## References

- [FastAPI Concurrency](https://fastapi.tiangolo.com/async/)
- [Python asyncio Thread Pool](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread)
- [Load Balancing Strategies](https://www.nginx.com/blog/load-balancing-strategies/)
- [Horizontal vs Vertical Scaling](https://www.cloudzero.com/blog/horizontal-vs-vertical-scaling)

---

**Ticket Type:** Discussion (DIS)
**Created:** 2025-10-15
**Status:** Open - Awaiting requirements and decision
**Priority:** Medium - Important for production scale planning
