# PLAN-001: Kronos FastAPI Microservice Productionization Roadmap

**Status:** In Planning
**Priority:** High
**Start Date:** 2025-10-14
**Target Completion:** 3 weeks
**Owner:** TBD

## Overview

Transform the Kronos FastAPI microservice into a production-ready Docker-based backend service for internal container-to-container communication.

## Goals

1. ✅ Dockerize the service with multi-stage build
2. ✅ Implement simplified security (network isolation + container whitelist + rate limiting)
3. ✅ Add async inference for better concurrency
4. ✅ Enhance observability (metrics, logging, dashboards)
5. ✅ Production hardening (graceful shutdown, error handling, timeouts)
6. ✅ Documentation and operational runbooks

## Scope

**In Scope:**
- Docker containerization
- Security middleware (container whitelist, rate limiting)
- Performance optimization (async inference, batching)
- Enhanced monitoring and metrics
- Graceful shutdown and error handling
- Production documentation

**Out of Scope:**
- Kubernetes deployment (Docker Compose only)
- Multi-host orchestration
- API key authentication (deferred)
- Model version management (future)
- Auto-scaling (future)

## Architecture

### Target Deployment

```
┌─────────────────────────────────────────────────────────┐
│ Docker Host                                              │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ kronos-internal (Docker Network - internal)    │    │
│  │                                                 │    │
│  │  ┌──────────────┐                              │    │
│  │  │ kronos-api   │ ← This service               │    │
│  │  │ (Port 8000)  │                              │    │
│  │  └──────┬───────┘                              │    │
│  │         │                                       │    │
│  │    ┌────┴────┬────────┬──────────┐            │    │
│  │    │         │        │          │            │    │
│  │  ┌─▼──┐   ┌─▼───┐  ┌─▼───┐   ┌─▼──────┐     │    │
│  │  │Web │   │Work-│  │Sche-│   │Monitor-│     │    │
│  │  │App │   │er   │  │duler│   │ing     │     │    │
│  │  └────┘   └─────┘  └─────┘   └────────┘     │    │
│  │                                                 │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ Monitoring Stack (separate network)             │    │
│  │  • Prometheus                                   │    │
│  │  • Grafana                                      │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 1: Dockerization (Week 1, Days 1-3)

### Objectives
- Create production-ready Dockerfile
- Setup Docker Compose for development and production
- Verify container builds and runs correctly

### Tasks

#### Task 1.1: Create Dockerfile
**File:** `gitSource/services/kronos_fastapi/Dockerfile`
**Estimated Time:** 4 hours

**Requirements:**
- [ ] Multi-stage build (builder + runtime)
- [ ] Base image: `python:3.10-slim`
- [ ] Install system dependencies (minimal)
- [ ] Copy only necessary files
- [ ] Non-root user for security
- [ ] Health check configuration
- [ ] Environment variable support
- [ ] Optimized layer caching

**Deliverables:**
- Working Dockerfile
- Build script (`build.sh`)
- Image size < 2GB

**Acceptance Criteria:**
- Container builds successfully
- Service starts and responds to health check
- Image scans clean (no critical vulnerabilities)

---

#### Task 1.2: Create Docker Compose
**Files:**
- `docker-compose.yml` (production)
- `docker-compose.dev.yml` (development with hot-reload)

**Estimated Time:** 3 hours

**Requirements:**
- [ ] Internal network definition
- [ ] Volume mounts for models
- [ ] Environment variable configuration
- [ ] Health checks
- [ ] Restart policies
- [ ] Resource limits (CPU, memory)
- [ ] Logging configuration

**Deliverables:**
- docker-compose.yml
- docker-compose.dev.yml
- .env.example file

**Acceptance Criteria:**
- `docker-compose up` starts service successfully
- Service accessible from other containers
- Hot-reload works in dev mode

---

#### Task 1.3: Create .dockerignore
**File:** `gitSource/services/kronos_fastapi/.dockerignore`
**Estimated Time:** 30 minutes

**Requirements:**
- [ ] Exclude __pycache__, *.pyc
- [ ] Exclude .git, .env
- [ ] Exclude test files, logs
- [ ] Exclude unnecessary directories

---

#### Task 1.4: Testing and Documentation
**Estimated Time:** 2 hours

**Requirements:**
- [ ] Test container build
- [ ] Test container startup
- [ ] Test health endpoints from another container
- [ ] Document Docker commands in README
- [ ] Create deployment guide

**Deliverables:**
- Updated README with Docker instructions
- `DEPLOYMENT.md` guide

---

## Phase 2: Security Implementation (Week 1, Days 4-5)

### Objectives
- Implement container whitelist middleware
- Add rate limiting
- Add request size limits
- Configure secure Docker networking

### Tasks

#### Task 2.1: Container Whitelist Middleware
**File:** `gitSource/services/kronos_fastapi/security.py`
**Estimated Time:** 4 hours

**Requirements:**
- [ ] Extract caller container hostname
- [ ] Validate against whitelist from env variable
- [ ] Return 403 for unauthorized containers
- [ ] Log authorization attempts
- [ ] Add metrics for auth failures

**Implementation:**
```python
# security.py
import socket
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class ContainerWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Implementation
        ...
```

**Deliverables:**
- security.py module
- Unit tests
- Configuration documentation

**Acceptance Criteria:**
- Whitelisted containers can access
- Non-whitelisted containers get 403
- Logs show authorization events

---

#### Task 2.2: Rate Limiting
**File:** `gitSource/services/kronos_fastapi/main.py` (integrate slowapi)
**Estimated Time:** 3 hours

**Requirements:**
- [ ] Install slowapi package
- [ ] Configure rate limits (100/minute per container)
- [ ] Custom key function (by container name)
- [ ] Rate limit response headers
- [ ] Metrics for rate limit hits

**Dependencies:**
- Add `slowapi>=0.1.9` to requirements.txt

**Deliverables:**
- Rate limiting integration
- Configuration options
- Tests

**Acceptance Criteria:**
- Rate limits enforced per container
- 429 responses for exceeded limits
- Metrics show rate limit hits

---

#### Task 2.3: Request Size Limits
**File:** `gitSource/services/kronos_fastapi/main.py`
**Estimated Time:** 1 hour

**Requirements:**
- [ ] Configure FastAPI max request size (10MB)
- [ ] Add custom error handler for oversized requests
- [ ] Log oversized request attempts

**Configuration:**
```python
app = FastAPI(
    title=settings.app_name,
    max_request_size=10 * 1024 * 1024  # 10MB
)
```

---

#### Task 2.4: Docker Network Security
**File:** `docker-compose.yml`
**Estimated Time:** 2 hours

**Requirements:**
- [ ] Create internal Docker network
- [ ] No port mapping to host (internal only)
- [ ] Document network configuration
- [ ] Test inter-container communication

**Configuration:**
```yaml
networks:
  kronos-internal:
    driver: bridge
    internal: false  # Allow internet for model download
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

---

#### Task 2.5: Security Testing and Documentation
**Estimated Time:** 2 hours

**Requirements:**
- [ ] Test whitelist enforcement
- [ ] Test rate limiting
- [ ] Security audit checklist
- [ ] Document security model

**Deliverables:**
- SECURITY.md documentation
- Security test suite

---

## Phase 3: Performance Optimization (Week 2)

### Objectives
- Implement async inference
- Add request queuing and batching
- Optimize model loading
- Load testing and tuning

### Tasks

#### Task 3.1: Async Inference Implementation
**File:** `gitSource/services/kronos_fastapi/predictor.py`
**Estimated Time:** 8 hours

**Requirements:**
- [ ] Wrap sync prediction in `asyncio.to_thread()`
- [ ] Ensure thread safety
- [ ] Add timeout handling
- [ ] Update routes to use async predictor

**Before:**
```python
def predict_single(...):
    prediction = self._predictor.predict(...)  # Blocks event loop
```

**After:**
```python
async def predict_single(...):
    prediction = await asyncio.to_thread(
        self._predictor.predict, ...
    )
```

**Deliverables:**
- Async predictor implementation
- Performance benchmarks
- Documentation

**Acceptance Criteria:**
- No event loop blocking
- Concurrent requests handled efficiently
- Latency improvement demonstrated

---

#### Task 3.2: Request Queuing (Optional)
**Estimated Time:** 6 hours
**Priority:** Medium (if async not enough)

**Requirements:**
- [ ] Implement request queue
- [ ] Batch similar requests
- [ ] Configure queue size and timeout
- [ ] Metrics for queue depth

---

#### Task 3.3: Load Testing
**File:** `tests/load/locustfile.py`
**Estimated Time:** 4 hours

**Requirements:**
- [ ] Create locust test scenarios
- [ ] Test single and batch endpoints
- [ ] Measure p50, p95, p99 latencies
- [ ] Identify bottlenecks

**Test Scenarios:**
1. Steady state: 10 req/s
2. Burst: 100 req/s for 1 minute
3. Sustained load: 50 req/s for 10 minutes

**Deliverables:**
- Locust test file
- Load testing report
- Performance tuning recommendations

---

#### Task 3.4: Performance Tuning
**Estimated Time:** 4 hours

**Requirements:**
- [ ] Optimize worker count
- [ ] Tune timeout settings
- [ ] Model inference optimization
- [ ] Memory profiling

**Targets:**
- p95 latency < 2 seconds
- Support 20+ concurrent requests
- Memory usage < 4GB per worker

---

## Phase 4: Enhanced Observability (Week 2)

### Objectives
- Add detailed metrics
- Create Grafana dashboards
- Improve logging
- Setup alerting

### Tasks

#### Task 4.1: Enhanced Prometheus Metrics
**File:** `gitSource/services/kronos_fastapi/metrics.py`
**Estimated Time:** 4 hours

**Requirements:**
- [ ] Prediction latency histogram (by endpoint)
- [ ] Request count by container and status
- [ ] Model inference time
- [ ] Queue depth (if implemented)
- [ ] Error rate by error type
- [ ] Resource usage (memory, CPU)

**New Metrics:**
```python
PREDICTION_LATENCY = Histogram(
    'kronos_prediction_latency_seconds',
    'Prediction latency',
    ['endpoint', 'status'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

MODEL_INFERENCE_TIME = Histogram(
    'kronos_model_inference_seconds',
    'Model inference time',
    buckets=[0.05, 0.1, 0.5, 1.0, 2.0]
)
```

**Deliverables:**
- Updated metrics.py
- Metrics documentation
- Example PromQL queries

---

#### Task 4.2: Grafana Dashboard
**File:** `monitoring/grafana/kronos-dashboard.json`
**Estimated Time:** 4 hours

**Requirements:**
- [ ] Request rate and latency panels
- [ ] Error rate panel
- [ ] Model performance metrics
- [ ] Resource usage (CPU, memory)
- [ ] Container health status
- [ ] Alert indicators

**Panels:**
1. Request Rate (req/s)
2. Latency Percentiles (p50, p95, p99)
3. Error Rate (%)
4. Model Inference Time
5. Memory Usage
6. Active Connections
7. Rate Limit Hits

**Deliverables:**
- Grafana dashboard JSON
- Dashboard screenshot
- Setup instructions

---

#### Task 4.3: Structured Logging Enhancement
**File:** `gitSource/services/kronos_fastapi/logging_utils.py`
**Estimated Time:** 2 hours

**Requirements:**
- [ ] Add correlation IDs
- [ ] Include container metadata
- [ ] Log prediction parameters
- [ ] Error context logging
- [ ] Performance logging

**Log Format (JSON):**
```json
{
  "timestamp": "2025-10-14T12:00:00Z",
  "level": "INFO",
  "request_id": "req-123",
  "container_name": "frontend",
  "endpoint": "/v1/predict/single",
  "latency_ms": 1234,
  "status": 200
}
```

---

#### Task 4.4: Alerting Rules
**File:** `monitoring/prometheus/alerts.yml`
**Estimated Time:** 3 hours

**Requirements:**
- [ ] High error rate alert (>5% for 5m)
- [ ] High latency alert (p95 > 5s for 5m)
- [ ] Service down alert
- [ ] High memory usage alert (>90%)
- [ ] Rate limit excessive hits alert

**Deliverables:**
- Prometheus alert rules
- Alert notification templates
- Runbook for each alert

---

## Phase 5: Production Hardening (Week 3)

### Objectives
- Implement graceful shutdown
- Improve error handling
- Add timeouts
- Resource limits
- Final testing

### Tasks

#### Task 5.1: Graceful Shutdown
**File:** `gitSource/services/kronos_fastapi/main.py`
**Estimated Time:** 3 hours

**Requirements:**
- [ ] Shutdown event handler
- [ ] Wait for in-flight requests
- [ ] Unload model on shutdown
- [ ] Close connections
- [ ] Log shutdown events

**Implementation:**
```python
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down gracefully")
    # Wait for in-flight requests (handled by uvicorn)
    # Unload model
    manager = PredictorManagerRegistry.get(settings)
    manager.unload()
    logger.info("Shutdown complete")
```

---

#### Task 5.2: Enhanced Error Handling
**File:** `gitSource/services/kronos_fastapi/errors.py`
**Estimated Time:** 4 hours

**Requirements:**
- [ ] Custom exception classes
- [ ] Structured error responses
- [ ] Error code enumeration
- [ ] Distinguish 4xx vs 5xx errors
- [ ] Log error context

**Error Response Format:**
```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Candles and timestamps length mismatch",
    "details": {
      "candles_count": 100,
      "timestamps_count": 99
    },
    "request_id": "req-123"
  }
}
```

**Custom Exceptions:**
- `InvalidInputError` → 400
- `ModelNotReadyError` → 503
- `PredictionTimeoutError` → 504
- `InternalError` → 500

---

#### Task 5.3: Timeout Configuration
**Files:** `config.py`, `main.py`
**Estimated Time:** 2 hours

**Requirements:**
- [ ] Request timeout (60s)
- [ ] Model inference timeout (30s)
- [ ] Startup timeout (120s)
- [ ] Configurable via environment

**Configuration:**
```python
# config.py
request_timeout: int = Field(60, env="KRONOS_REQUEST_TIMEOUT")
inference_timeout: int = Field(30, env="KRONOS_INFERENCE_TIMEOUT")
```

---

#### Task 5.4: Resource Limits
**File:** `docker-compose.yml`
**Estimated Time:** 2 hours

**Requirements:**
- [ ] CPU limits (2 cores)
- [ ] Memory limits (4GB)
- [ ] Restart policy (unless-stopped)
- [ ] Health check retries

**Configuration:**
```yaml
services:
  kronos-api:
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

#### Task 5.5: Integration Testing
**File:** `tests/integration/test_production.py`
**Estimated Time:** 6 hours

**Requirements:**
- [ ] End-to-end tests with Docker
- [ ] Container communication tests
- [ ] Security tests (whitelist, rate limit)
- [ ] Error handling tests
- [ ] Performance tests
- [ ] Graceful shutdown test

**Test Scenarios:**
1. Happy path prediction
2. Batch prediction
3. Unauthorized container access
4. Rate limit enforcement
5. Oversized request handling
6. Model not ready handling
7. Timeout handling
8. Graceful shutdown

---

#### Task 5.6: Smoke Testing
**File:** `tests/smoke/test_smoke.sh`
**Estimated Time:** 2 hours

**Requirements:**
- [ ] Basic health check
- [ ] Single prediction test
- [ ] Batch prediction test
- [ ] Metrics endpoint check
- [ ] Run on container startup

**Deliverables:**
- Smoke test script
- CI/CD integration ready

---

## Phase 6: Documentation and Handoff (Week 3)

### Objectives
- Complete all documentation
- Create operational runbooks
- Setup deployment automation
- Knowledge transfer

### Tasks

#### Task 6.1: Complete Documentation
**Estimated Time:** 6 hours

**Files to Update:**
- [ ] README.md - Quick start with Docker
- [ ] DEPLOYMENT.md - Production deployment guide
- [ ] SECURITY.md - Security model and configuration
- [ ] MONITORING.md - Metrics and alerting guide
- [ ] TROUBLESHOOTING.md - Common issues and solutions
- [ ] API.md - API endpoint documentation
- [ ] CLAUDE.md - Update with Docker commands

**Each Document Should Include:**
- Purpose and overview
- Prerequisites
- Step-by-step instructions
- Configuration options
- Examples
- Common issues

---

#### Task 6.2: Operational Runbooks
**File:** `docs/runbooks/`
**Estimated Time:** 4 hours

**Runbooks to Create:**
1. **Deployment Runbook**
   - Initial deployment steps
   - Rolling update procedure
   - Rollback procedure

2. **Incident Response Runbook**
   - Service down response
   - High latency response
   - High error rate response
   - Memory leak response

3. **Maintenance Runbook**
   - Model update procedure
   - Configuration changes
   - Log rotation
   - Backup and restore

4. **Monitoring Runbook**
   - Dashboard walkthrough
   - Alert interpretation
   - Metrics troubleshooting

---

#### Task 6.3: Deployment Automation
**File:** `deploy.sh`
**Estimated Time:** 3 hours

**Requirements:**
- [ ] Automated deployment script
- [ ] Pre-deployment checks
- [ ] Build and push Docker image
- [ ] Update containers
- [ ] Health check verification
- [ ] Rollback on failure

**Features:**
- Environment selection (dev/prod)
- Dry-run mode
- Colored output
- Error handling

---

#### Task 6.4: CI/CD Pipeline (Optional)
**File:** `.github/workflows/deploy.yml`
**Estimated Time:** 4 hours (if needed)

**Requirements:**
- [ ] Automated tests on PR
- [ ] Build Docker image
- [ ] Push to registry
- [ ] Deploy to staging
- [ ] Smoke tests
- [ ] Deploy to production (manual approval)

---

## Success Criteria

### Functional Requirements
- ✅ Service runs in Docker container
- ✅ Accessible only from internal Docker network
- ✅ Container whitelist enforcement
- ✅ Rate limiting active
- ✅ Async inference working
- ✅ Health checks passing
- ✅ Metrics exposed
- ✅ Graceful shutdown

### Performance Requirements
- ✅ p95 latency < 2 seconds (single prediction)
- ✅ Support 20+ concurrent requests
- ✅ Memory usage < 4GB per worker
- ✅ No event loop blocking
- ✅ 99.9% uptime in testing

### Security Requirements
- ✅ Network isolated (internal only)
- ✅ Container whitelist enforced
- ✅ Rate limiting (100/min per container)
- ✅ No critical vulnerabilities in image
- ✅ Non-root user
- ✅ Request size limits

### Observability Requirements
- ✅ Structured JSON logs
- ✅ Prometheus metrics with histograms
- ✅ Grafana dashboard
- ✅ Alert rules defined
- ✅ Request tracing (correlation IDs)

### Operational Requirements
- ✅ Docker Compose for deployment
- ✅ One-command startup
- ✅ Graceful shutdown
- ✅ Health check endpoints
- ✅ Complete documentation
- ✅ Runbooks for incidents

---

## Timeline Summary

| Phase | Duration | Dependencies | Risk Level |
|-------|----------|--------------|------------|
| 1. Dockerization | 3 days | None | Low |
| 2. Security | 2 days | Phase 1 | Low |
| 3. Performance | 5 days | Phase 1, 2 | Medium |
| 4. Observability | 4 days | Phase 3 | Low |
| 5. Hardening | 4 days | Phase 3, 4 | Medium |
| 6. Documentation | 2 days | All phases | Low |

**Total:** 20 working days (3 weeks)

---

## Resource Requirements

### Team
- 1 Backend Developer (full-time)
- 0.5 DevOps Engineer (part-time)
- 0.25 QA Engineer (testing support)

### Infrastructure
- Docker host with:
  - 4 CPU cores minimum
  - 8GB RAM minimum
  - 20GB disk space
  - GPU (optional, for inference)

### Tools and Services
- Docker & Docker Compose
- Prometheus & Grafana
- Git repository
- Container registry (optional)

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Async conversion breaks functionality | Medium | High | Comprehensive testing, gradual rollout |
| Performance targets not met | Medium | Medium | Early benchmarking, fallback to sync |
| Docker networking issues | Low | Medium | Testing with real containers |
| Resource constraints | Medium | Medium | Load testing, resource monitoring |
| Timeline slip | Medium | Low | Buffer time, prioritize MVP |

---

## Rollout Strategy

### Stage 1: Development Environment (Week 1-2)
- Deploy to dev environment
- Internal testing
- Fix issues

### Stage 2: Staging Environment (Week 3)
- Deploy to staging
- Integration testing with consumer containers
- Load testing
- Fix remaining issues

### Stage 3: Production (After Week 3)
- Deploy to production with monitoring
- Gradual traffic migration (if applicable)
- Monitor metrics closely
- Rollback plan ready

---

## Post-Deployment

### Week 4: Monitoring and Stabilization
- [ ] Monitor production metrics daily
- [ ] Address any issues quickly
- [ ] Tune performance based on real usage
- [ ] Collect feedback from consumers

### Week 5-6: Optimization
- [ ] Analyze performance data
- [ ] Optimize based on patterns
- [ ] Improve documentation based on issues
- [ ] Plan next improvements

---

## Future Enhancements (Out of Scope)

These are intentionally deferred for simplicity:

1. **Model Version Management**
   - A/B testing
   - Canary deployments
   - Model rollback

2. **Auto-Scaling**
   - Horizontal scaling
   - Load-based scaling
   - Kubernetes deployment

3. **Advanced Batching**
   - Dynamic batch sizing
   - Request coalescing
   - Batch timeout optimization

4. **Caching**
   - Prediction result caching
   - Redis integration

5. **Multi-Model Support**
   - Multiple model versions
   - Model routing

---

## Dependencies and Prerequisites

### Before Starting
- [x] Existing service is functional
- [x] Requirements documented
- [ ] Docker host available
- [ ] Access to model files
- [ ] Team assigned

### External Dependencies
- Python packages (in requirements.txt)
- Docker 20.10+
- Docker Compose 2.0+
- Model files (Kronos-small)
- Prometheus (for metrics)
- Grafana (for dashboards)

---

## Communication Plan

### Weekly Status Updates
- Progress report every Friday
- Blockers and risks
- Next week plan

### Demos
- End of Week 1: Dockerization demo
- End of Week 2: Performance and observability demo
- End of Week 3: Final demo and handoff

### Stakeholder Reviews
- Mid-project review (end of Week 2)
- Final review before production (end of Week 3)

---

## Approval and Sign-off

**Plan Approved By:**
- [ ] Technical Lead
- [ ] DevOps Lead
- [ ] Product Owner

**Date:** ___________

**Production Deployment Approved By:**
- [ ] Technical Lead
- [ ] DevOps Lead
- [ ] Security Review
- [ ] Product Owner

**Date:** ___________

---

## Appendix

### A. Related Tickets
- IMPROVEMENT-001: FastAPI Production Readiness Assessment
- IMPROVEMENT-002: Dockerfile Creation (to be created)
- IMPROVEMENT-003: Security Middleware (to be created)
- IMPROVEMENT-004: Performance Optimization (to be created)

### B. Reference Materials
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Docker Best Practices: https://docs.docker.com/develop/dev-best-practices/
- Prometheus Metrics: https://prometheus.io/docs/concepts/metric_types/
- Grafana Dashboards: https://grafana.com/docs/

### C. Key Decision Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-10-14 | No API Key auth | Simplified security for internal Docker network |
| 2025-10-14 | Use slowapi for rate limiting | Simple, well-maintained, FastAPI-compatible |
| 2025-10-14 | Async inference with asyncio | Standard library, no extra dependencies |

---

**Last Updated:** 2025-10-14
**Version:** 1.0
