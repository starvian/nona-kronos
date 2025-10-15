# Production Deployment Guide - Kronos FastAPI Service

**Last Updated:** 2025-10-14
**Target Environment:** Docker-based production deployment

## Table of Contents

- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Deployment Procedures](#deployment-procedures)
- [Rollback Procedures](#rollback-procedures)
- [Zero-Downtime Deployment](#zero-downtime-deployment)
- [Health Check Configuration](#health-check-configuration)
- [Monitoring and Alerts](#monitoring-and-alerts)
- [Troubleshooting](#troubleshooting)

## Pre-Deployment Checklist

### 1. Environment Configuration

**Verify all environment variables:**

```bash
# Required variables
KRONOS_MODEL_PATH=/models          # Path to model files
KRONOS_DEVICE=cpu                  # or cuda:0 for GPU

# Performance settings
KRONOS_INFERENCE_TIMEOUT=30        # Seconds
KRONOS_REQUEST_TIMEOUT=60          # Seconds

# Security settings
KRONOS_SECURITY_ENABLED=true
KRONOS_CONTAINER_WHITELIST=localhost,frontend-app,worker-service
KRONOS_RATE_LIMIT_ENABLED=true
KRONOS_RATE_LIMIT_PER_MINUTE=100

# Resource limits
KRONOS_MAX_REQUEST_SIZE_MB=10
```

**Checklist:**
- [ ] Environment variables configured in `.env` file
- [ ] Model files accessible at configured path
- [ ] Model files have correct permissions (readable)
- [ ] Container whitelist includes all legitimate services
- [ ] Rate limits appropriate for expected traffic

### 2. Resource Allocation

**Verify Docker resources:**

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'        # Adjust based on load
      memory: 4G         # Minimum 4GB recommended
    reservations:
      cpus: '1.0'
      memory: 2G
```

**Checklist:**
- [ ] CPU allocation sufficient for expected load
- [ ] Memory allocation >= 4GB (model + overhead)
- [ ] Disk space available for logs (10GB+ recommended)
- [ ] Network configured correctly (internal/monitoring)

### 3. Monitoring Setup

**Checklist:**
- [ ] Prometheus configured to scrape `/v1/metrics`
- [ ] Grafana dashboard imported
- [ ] Alert rules loaded in Prometheus
- [ ] Alert Manager configured
- [ ] Notification channels tested (Slack, email, etc.)

### 4. Backup and Rollback Plan

**Checklist:**
- [ ] Previous image tagged and available
- [ ] Rollback procedure documented and tested
- [ ] Database/state backup if applicable
- [ ] Downtime window communicated

### 5. Testing

**Checklist:**
- [ ] Integration tests passed
- [ ] Load tests completed
- [ ] Health checks verified
- [ ] Metrics collection working
- [ ] Logs being written correctly

## Deployment Procedures

### Standard Deployment (With Downtime)

**Steps:**

1. **Build new image:**
```bash
cd kronos_fastapi
./build.sh
```

2. **Stop current service:**
```bash
docker-compose stop kronos-api
```

3. **Deploy new version:**
```bash
docker-compose up -d kronos-api
```

4. **Verify deployment:**
```bash
# Check container status
docker ps | grep kronos-api

# Check health
curl http://localhost:8000/v1/healthz

# Wait for model loading
curl http://localhost:8000/v1/readyz

# Check logs
docker logs kronos-api --tail 50
```

5. **Monitor metrics:**
```bash
# Check request rate
curl http://localhost:8000/v1/metrics | grep kronos_requests_total

# Check error rate
curl http://localhost:8000/v1/metrics | grep error
```

**Expected Downtime:** 1-2 minutes (model loading time)

### Zero-Downtime Deployment (Blue-Green)

**Prerequisites:**
- Load balancer or proxy (Nginx, Traefik)
- Sufficient resources for 2 instances

**Steps:**

1. **Start green instance:**
```bash
# Rename current service to "blue"
docker rename kronos-api kronos-api-blue

# Start green instance on different port
docker run -d \
  --name kronos-api-green \
  --network kronos-internal \
  -p 8001:8000 \
  -e KRONOS_MODEL_PATH=/models \
  ... other env vars ... \
  kronos-fastapi:latest
```

2. **Verify green instance:**
```bash
# Health check
curl http://localhost:8001/v1/healthz

# Readiness check
curl http://localhost:8001/v1/readyz

# Test prediction
curl -X POST http://localhost:8001/v1/predict/single \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```

3. **Switch traffic:**
```bash
# Update load balancer to point to green instance
# (Specific steps depend on your load balancer)

# For Nginx:
# Edit nginx.conf:
#   upstream kronos {
#     server kronos-api-green:8000;  # Changed from kronos-api-blue
#   }
nginx -s reload
```

4. **Monitor green instance:**
```bash
# Watch logs
docker logs -f kronos-api-green

# Monitor metrics
watch -n 5 'curl -s http://localhost:8001/v1/metrics | grep kronos_requests_total'
```

5. **Stop blue instance:**
```bash
# After confirming green is stable (wait 10-15 minutes)
docker stop kronos-api-blue
docker rm kronos-api-blue
```

6. **Rename green to primary:**
```bash
docker rename kronos-api-green kronos-api
```

**Expected Downtime:** Zero

### Rolling Update (Multiple Instances)

**For horizontally scaled deployments:**

```yaml
# docker-compose.yml
services:
  kronos-api:
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 30s
        failure_action: rollback
        monitor: 60s
```

**Deploy:**
```bash
docker stack deploy -c docker-compose.yml kronos-stack
```

Docker Swarm will:
1. Update 1 instance at a time
2. Wait 30s between updates
3. Monitor for 60s
4. Rollback if failures detected

### Canary Deployment

**Deploy to subset of traffic first:**

1. **Deploy canary instance:**
```bash
docker run -d \
  --name kronos-api-canary \
  --network kronos-internal \
  --label version=canary \
  kronos-fastapi:latest
```

2. **Configure load balancer for weighted routing:**
```nginx
# Nginx example: 90% stable, 10% canary
upstream kronos {
    server kronos-api-stable:8000 weight=9;
    server kronos-api-canary:8000 weight=1;
}
```

3. **Monitor canary metrics:**
```bash
# Compare error rates
curl http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=rate(kronos_requests_total{status="error"}[5m])'
```

4. **Promote or rollback:**
```bash
# If canary is healthy, promote to 100%
# If canary has issues, rollback
docker stop kronos-api-canary
```

## Rollback Procedures

### Quick Rollback

**If new deployment has issues:**

1. **Stop new version:**
```bash
docker stop kronos-api
```

2. **Start previous version:**
```bash
# Pull previous image
docker pull kronos-fastapi:previous

# Start with previous image
docker run -d \
  --name kronos-api \
  --network kronos-internal \
  ... same config as before ... \
  kronos-fastapi:previous
```

3. **Verify rollback:**
```bash
curl http://localhost:8000/v1/healthz
curl http://localhost:8000/v1/readyz
```

**Rollback Time:** 1-2 minutes

### Rollback Verification

**Checklist:**
- [ ] Health checks passing
- [ ] Model loaded successfully
- [ ] No error spikes in logs
- [ ] Metrics look normal
- [ ] Integration tests passing

## Zero-Downtime Deployment

### Using Docker Compose with Multiple Services

**docker-compose.prod.yml:**

```yaml
version: '3.8'

services:
  kronos-api-1:
    image: kronos-fastapi:${VERSION}
    container_name: kronos-api-1
    networks:
      - kronos-internal
      - monitoring
    environment:
      - KRONOS_MODEL_PATH=/models
      # ... other env vars ...
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/healthz"]
      interval: 10s
      timeout: 5s
      retries: 3

  kronos-api-2:
    image: kronos-fastapi:${VERSION}
    container_name: kronos-api-2
    networks:
      - kronos-internal
      - monitoring
    environment:
      - KRONOS_MODEL_PATH=/models
      # ... other env vars ...
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/healthz"]
      interval: 10s
      timeout: 5s
      retries: 3

  nginx:
    image: nginx:latest
    container_name: kronos-lb
    networks:
      - kronos-internal
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "8000:80"
    depends_on:
      - kronos-api-1
      - kronos-api-2

networks:
  kronos-internal:
    driver: bridge
  monitoring:
    external: true
```

**nginx.conf for load balancing:**

```nginx
http {
    upstream kronos_backend {
        # Health check aware load balancing
        server kronos-api-1:8000 max_fails=3 fail_timeout=30s;
        server kronos-api-2:8000 max_fails=3 fail_timeout=30s;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://kronos_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

            # Timeouts
            proxy_connect_timeout 10s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;

            # Health check
            proxy_next_upstream error timeout http_503;
        }
    }
}
```

**Deploy procedure:**

```bash
# Update instance 1
export VERSION=v1.2.0
docker-compose up -d kronos-api-1

# Wait for health check
sleep 60

# Update instance 2
docker-compose up -d kronos-api-2
```

## Health Check Configuration

### Kubernetes Probes

**deployment.yaml:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kronos-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: kronos-api
  template:
    metadata:
      labels:
        app: kronos-api
    spec:
      containers:
      - name: kronos-api
        image: kronos-fastapi:latest
        ports:
        - containerPort: 8000

        # Startup probe (model loading)
        startupProbe:
          httpGet:
            path: /v1/readyz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 12  # Allow 2 minutes for startup

        # Liveness probe (is service alive?)
        livenessProbe:
          httpGet:
            path: /v1/healthz
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 20
          timeoutSeconds: 5
          failureThreshold: 3

        # Readiness probe (ready to serve traffic?)
        readinessProbe:
          httpGet:
            path: /v1/readyz
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
```

### Docker Health Check

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/v1/healthz"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s  # Allow model loading
```

## Monitoring and Alerts

### Deployment Success Criteria

**Monitor these metrics:**

```promql
# No error spike
rate(kronos_requests_total{status="error"}[5m]) < 0.01

# Latency within bounds
histogram_quantile(0.95, rate(kronos_request_duration_seconds_bucket[5m])) < 5

# No timeout spike
rate(kronos_timeouts_total[5m]) < 0.005

# Service is up
up{job="kronos-api"} == 1
```

### Post-Deployment Monitoring

**Monitor for 30 minutes after deployment:**

1. **Request rate:** Should return to normal
2. **Error rate:** Should be < 1%
3. **Latency p95:** Should be < 2s
4. **Memory usage:** Should be stable
5. **No alerts firing**

### Rollback Triggers

**Automatic rollback if:**
- Error rate > 5% for 2 minutes
- p95 latency > 10s for 5 minutes
- Service down for 1 minute
- Memory usage > 95% for 5 minutes

## Troubleshooting

### Deployment Failures

#### Problem: Container won't start

**Diagnosis:**
```bash
docker logs kronos-api
docker inspect kronos-api
```

**Common causes:**
- Model path not accessible
- Insufficient memory
- Port already in use
- Environment variables incorrect

**Solution:**
```bash
# Check model path
docker exec kronos-api ls -la /models

# Check memory
docker stats kronos-api

# Check port
netstat -tulpn | grep 8000

# Check environment
docker exec kronos-api env | grep KRONOS
```

#### Problem: Model fails to load

**Symptoms:**
- `/v1/readyz` returns `model_loaded: false`
- Logs show model loading errors

**Diagnosis:**
```bash
# Check startup logs
docker logs kronos-api | grep -i "model\|error"

# Check model files
docker exec kronos-api ls -lh /models
```

**Solutions:**
1. Verify model files exist and are readable
2. Check memory allocation (need >= 2GB for model)
3. Verify KRONOS_MODEL_PATH is correct
4. Check for corrupted model files

#### Problem: High error rate after deployment

**Diagnosis:**
```bash
# Check error logs
docker logs kronos-api | grep ERROR

# Check metrics
curl http://localhost:8000/v1/metrics | grep error

# Query Prometheus
curl -G http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=rate(kronos_requests_total{status="error"}[5m])'
```

**Solutions:**
1. Check for validation errors in logs
2. Verify input data format hasn't changed
3. Check for model compatibility issues
4. Review recent code changes
5. Consider rollback if persistent

#### Problem: Performance degradation

**Symptoms:**
- Increased latency
- Timeouts
- Slow responses

**Diagnosis:**
```bash
# Check CPU/memory
docker stats kronos-api

# Check concurrent requests
curl http://localhost:8000/v1/metrics | grep concurrent

# Check inference time
curl http://localhost:8000/v1/metrics | grep inference
```

**Solutions:**
1. Scale horizontally (add instances)
2. Increase CPU/memory allocation
3. Review worker count
4. Check for memory leaks
5. Optimize input sizes

### Recovery Procedures

#### Graceful Restart

```bash
# Send SIGTERM for graceful shutdown
docker stop -t 30 kronos-api

# Start new instance
docker-compose up -d kronos-api
```

#### Force Restart (Last Resort)

```bash
# Kill immediately
docker kill kronos-api
docker rm kronos-api

# Start fresh
docker-compose up -d kronos-api
```

## Best Practices

### 1. Always Use Graceful Shutdown

```bash
# Good: Allows in-flight requests to complete
docker stop -t 30 kronos-api

# Bad: Kills immediately
docker kill kronos-api
```

### 2. Monitor Deployment

- Watch metrics for 30 minutes
- Check for error rate spikes
- Verify latency within bounds
- Ensure no memory leaks

### 3. Test Before Production

```bash
# Run integration tests
pytest tests/integration/

# Run load tests
locust -f tests/load/locustfile.py --host=http://staging:8000

# Verify health checks
curl http://staging:8000/v1/healthz/detailed
```

### 4. Document Changes

- Update CHANGELOG
- Tag releases in git
- Document configuration changes
- Update runbooks if needed

### 5. Have Rollback Plan

- Keep previous image
- Know rollback procedure
- Test rollback in staging
- Document rollback triggers

## Platform-Specific Guides

### AWS ECS

See [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) (future)

### Google Cloud Run

See [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md) (future)

### Kubernetes

See health check configuration above

### Docker Swarm

Use rolling updates as documented

---

**Last Updated:** 2025-10-14
**Maintained By:** ML Platform Team
**Review Schedule:** Quarterly
