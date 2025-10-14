# IMPROVEMENT-001: FastAPI Microservice Production Readiness

**Status:** Open
**Priority:** Medium
**Created:** 2025-10-14
**Component:** FastAPI Microservice (`gitSource/services/kronos_fastapi/`)

## Summary

Evaluate and improve the FastAPI microservice for production deployment as a Docker-based backend service accessible only by other Docker containers on the same host.

## Current State Assessment

### ✅ Strengths
- Clean modular architecture (routes, predictor, config, schemas)
- Singleton pattern for model lifecycle management
- Structured logging with request ID tracking
- Prometheus metrics integration
- Health check endpoints (/healthz, /readyz)
- Environment-based configuration via Pydantic Settings
- Model fallback mechanism (local → Hugging Face)

### ⚠️ Areas for Improvement

#### 1. Performance and Concurrency
**Issue:** Synchronous blocking calls in prediction endpoints
```python
# predictor.py - blocks event loop
prediction = self._predictor.predict(...)
```

**Impact:** Limited concurrent request handling

**Proposed Solutions:**
- [ ] Use `asyncio.to_thread()` for model inference
- [ ] Implement request queuing with batching
- [ ] Consider async model serving frameworks (Ray Serve, Triton)

**Priority:** High (for medium-scale deployment)

---

#### 2. Error Handling and Resilience
**Issue:** Generic exception handling
```python
except Exception as exc:
    raise HTTPException(status_code=500, detail=str(exc))
```

**Missing:**
- Distinction between 4xx (client) vs 5xx (server) errors
- Timeout mechanisms
- Circuit breaker pattern
- Retry logic for transient failures

**Proposed Solutions:**
- [ ] Add custom exception classes
- [ ] Implement request timeout (e.g., 30s for prediction)
- [ ] Add circuit breaker for model failures
- [ ] Detailed error responses with error codes

**Priority:** High

---

#### 3. Resource Management
**Issue:** Model loaded once and kept in memory indefinitely

**Missing:**
- Model unload mechanism
- Model version management
- Memory monitoring
- Auto-restart on OOM

**Proposed Solutions:**
- [ ] Add model unload on shutdown
- [ ] Implement model hot-reload capability
- [ ] Add memory usage metrics
- [ ] Graceful degradation on low memory

**Priority:** Medium

---

#### 4. Security (Docker Inter-Container Communication)

**Deployment Context:**
- Service runs in Docker container
- Only accessible by other containers on same host (Docker network)
- Not exposed to public internet

**Current Gaps:**
- ❌ No authentication/authorization
- ❌ No rate limiting
- ❌ No request size limits
- ❌ No CORS configuration

**Discussion: Simplified Security for Docker Internal Network**

Since the service is **only accessible by trusted containers on the same host**, the security model can be simplified:

### Recommended Approach (Layered Security)

#### Layer 1: Network Isolation (PRIMARY DEFENSE)
```yaml
# docker-compose.yml
networks:
  kronos-internal:
    driver: bridge
    internal: true  # No external access
```
- ✅ Service only on internal Docker network
- ✅ No port mapping to host (0.0.0.0)
- ✅ Only whitelisted containers can join network

**Security Level:** Strong (prevents external access entirely)

#### Layer 2: Container-Level Access Control (RECOMMENDED)
```python
# config.py
allowed_containers: List[str] = Field(
    default=["frontend", "worker", "scheduler"],
    env="KRONOS_ALLOWED_CONTAINERS"
)
```
- ✅ Validate caller by Docker hostname/container name
- ✅ Simple whitelist in environment variable
- ✅ No complex auth needed

**Implementation:**
```python
# middleware.py
async def container_whitelist_middleware(request: Request, call_next):
    client_host = request.client.host
    container_name = socket.gethostbyaddr(client_host)[0]

    if container_name not in settings.allowed_containers:
        return JSONResponse(
            status_code=403,
            content={"detail": "Container not authorized"}
        )
    return await call_next(request)
```

**Security Level:** Good (for trusted internal network)

#### Layer 3: Rate Limiting (OPTIONAL BUT RECOMMENDED)
- ✅ Protects against misbehaving containers
- ✅ Prevents resource exhaustion
- ✅ Simple to implement with slowapi

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/v1/predict/single")
@limiter.limit("100/minute")  # Per container
async def predict_single(...):
    ...
```

**Security Level:** Good (prevents accidental DoS)

#### Layer 4: API Key (OPTIONAL)
**When to use:**
- Multi-tenant scenarios
- Need per-container usage tracking
- Regulatory compliance requirements

**When NOT needed:**
- Single-tenant deployment
- All containers equally trusted
- Simple internal communication

```python
# Only if needed
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    api_key = request.headers.get("X-API-Key")
    if api_key not in settings.valid_api_keys:
        return JSONResponse(status_code=401, ...)
    return await call_next(request)
```

**Security Level:** Strong (but adds complexity)

### Recommendation for Docker-Only Deployment

**Minimum Required (Sufficient for internal use):**
1. ✅ Network isolation (internal Docker network)
2. ✅ Container whitelist middleware
3. ✅ Rate limiting (per container)
4. ✅ Request size limits
5. ❌ Authentication/Authorization (NOT needed for pure internal)

**Reasoning:**
- Docker network isolation is primary security boundary
- Container whitelist prevents unauthorized containers
- Rate limiting prevents accidents, not attacks
- No internet exposure = no need for complex auth
- Simpler = fewer points of failure

**Trade-offs:**
| Approach | Security | Complexity | Maintainability |
|----------|----------|------------|-----------------|
| Network only | Medium | Low ⭐⭐⭐⭐⭐ | Excellent |
| + Container whitelist | Good | Low ⭐⭐⭐⭐ | Very Good |
| + Rate limiting | Good | Medium ⭐⭐⭐ | Good |
| + API Key | Strong | High ⭐⭐ | Fair |

**Proposed Solutions:**
- [x] Deploy in Docker with internal network
- [ ] Add container whitelist middleware
- [ ] Add rate limiting (slowapi)
- [ ] Add request size limits (FastAPI config)
- [ ] Document security model in README

**Priority:** Medium (sufficient for internal Docker deployment)

---

#### 5. Production Deployment Features

**Missing:**
- Graceful shutdown handling
- Request timeout configuration
- Connection pool management
- Load testing validation

**Proposed Solutions:**
- [ ] Add shutdown event handler
- [ ] Configure timeouts (read: 60s, write: 60s, keepalive: 5s)
- [ ] Add startup probes for K8s/Docker health checks
- [ ] Create load testing script (locust or k6)

**Priority:** Medium

---

#### 6. Monitoring and Alerting

**Current:** Basic Prometheus metrics

**Missing:**
- Prediction latency percentiles (p50, p95, p99)
- GPU/CPU utilization metrics
- Memory usage trends
- Error rate by type
- Model-specific metrics (inference time, batch size)

**Proposed Solutions:**
- [ ] Add detailed histogram metrics
- [ ] Integrate with node_exporter for system metrics
- [ ] Add Grafana dashboard templates
- [ ] Define alerting rules (latency > 5s, error rate > 5%)

**Priority:** Medium

---

## Docker Deployment Proposal

### Architecture
```
Docker Host
├── kronos-internal (network)
│   ├── kronos-api (this service)
│   ├── frontend-app (consumer)
│   ├── worker-service (consumer)
│   └── scheduler (consumer)
└── External Network (isolated)
```

### Implementation Checklist

#### Phase 1: Dockerization
- [ ] Create `Dockerfile` with multi-stage build
- [ ] Create `docker-compose.yml` for local development
- [ ] Create `.dockerignore`
- [ ] Test container build and startup
- [ ] Document environment variables

#### Phase 2: Security (Simplified for Internal Network)
- [ ] Configure internal Docker network
- [ ] Implement container whitelist middleware
- [ ] Add rate limiting (100 req/min per container)
- [ ] Add request size limits (10MB max)
- [ ] Document security model

#### Phase 3: Performance
- [ ] Async inference implementation
- [ ] Add request queuing
- [ ] Configure worker count (CPU cores * 2)
- [ ] Load testing and optimization

#### Phase 4: Observability
- [ ] Enhanced Prometheus metrics
- [ ] Grafana dashboard
- [ ] Log aggregation setup
- [ ] Alerting rules

#### Phase 5: Production Hardening
- [ ] Graceful shutdown
- [ ] Health check tuning
- [ ] Resource limits (CPU, memory)
- [ ] Auto-restart policy

---

## Production Readiness Score

| Aspect | Current | Target | Priority |
|--------|---------|--------|----------|
| Code Quality | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Low |
| Performance | ⭐⭐⭐ | ⭐⭐⭐⭐ | High |
| Reliability | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | High |
| Security (Internal) | ⭐⭐ | ⭐⭐⭐⭐ | Medium |
| Observability | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Medium |
| Ops-Friendly | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Medium |

**Current:** 3.0/5
**Target:** 4.5/5 (Docker internal deployment)

---

## Recommended Timeline

### Week 1: Dockerization + Basic Security
- Dockerfile and docker-compose
- Internal network setup
- Container whitelist middleware
- Rate limiting

### Week 2: Performance Optimization
- Async inference
- Request queuing
- Load testing
- Tuning

### Week 3: Observability + Hardening
- Enhanced metrics
- Grafana dashboard
- Graceful shutdown
- Documentation

---

## Decision: Simplified Security Model for Docker Internal Network

**Date:** 2025-10-14
**Decision:** Adopt simplified security approach without API key authentication

### Rationale

**Deployment Context:**
- Service runs in Docker container on internal network
- Only accessible by other trusted containers on same host
- No public internet exposure
- All containers controlled by same organization

**Approved Security Layers:**

1. ✅ **Docker Network Isolation** (Layer 1 - Primary Defense)
   - Internal Docker network only
   - No port mapping to host
   - Physical network boundary

2. ✅ **Container Whitelist Middleware** (Layer 2 - Configuration Protection)
   - Validate calling container by hostname
   - Simple environment-based whitelist
   - Prevents misconfigured containers

3. ✅ **Rate Limiting** (Layer 3 - Resource Protection)
   - 100 requests/minute per container
   - Prevents accidental resource exhaustion
   - Not for security, but reliability

4. ❌ **API Key Authentication** (REJECTED)
   - **Not needed** for fully trusted internal network
   - Adds unnecessary complexity
   - No additional security value in this context
   - Would require key management overhead

### Threat Model Analysis

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| External attack | None | N/A | Network isolation |
| Unauthorized container | Low | Medium | Container whitelist |
| Misconfiguration | Medium | Medium | Container whitelist |
| Resource exhaustion | Medium | High | Rate limiting |
| Malicious insider | Low | High | Docker network isolation |

### When to Revisit This Decision

Add API key authentication if:
- Service becomes multi-tenant
- Containers from untrusted sources
- Compliance requirements (SOX, HIPAA, etc.)
- Need per-container usage tracking/billing
- Service exposed beyond Docker network

**Current Status:** Simplified approach is **sufficient and recommended** ✅

## Discussion Points

1. **~~Authentication for Docker Internal Network~~** ✅ RESOLVED
   - **Decision:** Container whitelist only (no API keys)
   - **Rationale:** Sufficient for trusted internal Docker network
   - **Implementation:** See security layers above

2. **Performance vs Simplicity**
   - Async inference adds complexity
   - Is current sync performance acceptable for use case?
   - What is expected QPS (queries per second)?

3. **Model Management**
   - Should we support multiple model versions?
   - Is hot-reload needed?
   - Memory constraints?

4. **Deployment Environment**
   - Docker Compose or Kubernetes?
   - Single host or multi-host?
   - Auto-scaling requirements?

---

## Related Files

- `gitSource/services/kronos_fastapi/main.py`
- `gitSource/services/kronos_fastapi/routes.py`
- `gitSource/services/kronos_fastapi/predictor.py`
- `gitSource/services/kronos_fastapi/config.py`
- `gitSource/services/kronos_fastapi/README.md`

---

## Next Steps

1. **Discuss** security approach with team
2. **Create** Dockerfile (IMPROVEMENT-002)
3. **Implement** container whitelist middleware (IMPROVEMENT-003)
4. **Add** rate limiting (IMPROVEMENT-004)
5. **Load test** current implementation to understand bottlenecks

---

## Notes

- Service is already functional for internal use
- Docker isolation is primary security mechanism
- Focus on reliability and observability over complex auth
- Keep it simple for maintenance

---

**Last Updated:** 2025-10-14
