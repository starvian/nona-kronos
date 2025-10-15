# Observability Guide - Kronos FastAPI Microservice

**Last Updated:** 2025-10-14
**Monitoring Approach:** Configuration-only (Integration with Centralized Infrastructure)

## Overview

This guide covers the observability capabilities of Kronos FastAPI service, designed to integrate seamlessly with your existing centralized Prometheus/Grafana monitoring infrastructure.

**Philosophy:** We provide configuration files and documentation, but do NOT bundle monitoring containers. This allows you to integrate Kronos into your existing monitoring setup alongside other services (Python backends, WordPress, etc.).

## Table of Contents

- [Architecture](#architecture)
- [Metrics Reference](#metrics-reference)
- [Prometheus Integration](#prometheus-integration)
- [Grafana Dashboard](#grafana-dashboard)
- [Alert Rules](#alert-rules)
- [Logging](#logging)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Architecture

### Centralized Monitoring Model

```
┌─────────────────────────────────────────────────────────┐
│  Centralized Monitoring Infrastructure                  │
│  ┌──────────────┐      ┌──────────────┐                │
│  │ Prometheus   │◄─────┤  Grafana     │                │
│  │              │      │              │                │
│  └──────┬───────┘      └──────────────┘                │
│         │                                                │
│         │ Scrapes /metrics endpoints                     │
└─────────┼────────────────────────────────────────────────┘
          │
          ├─────────► Python Backend (/metrics)
          │
          ├─────────► WordPress (exporter)
          │
          └─────────► Kronos FastAPI (/v1/metrics)
```

### Three Pillars of Observability

#### 1. Metrics (Prometheus)
- Quantitative measurements
- Request rates, latency, errors
- Performance indicators
- Resource utilization

#### 2. Logs (Structured JSON)
- Event records
- Request traces
- Error details
- Contextual information

#### 3. Traces (Future Enhancement)
- Request flow tracking
- Distributed tracing
- Performance profiling

## Metrics Reference

### Request Metrics

#### `kronos_requests_total`
**Type:** Counter
**Labels:** `route`, `status`
**Description:** Total number of prediction requests

```promql
# Examples:
kronos_requests_total{route="/v1/predict/single", status="success"}
kronos_requests_total{route="/v1/predict/batch", status="error"}

# Request rate (req/s)
rate(kronos_requests_total[1m])

# Success rate
sum(rate(kronos_requests_total{status="success"}[5m]))
  /
sum(rate(kronos_requests_total[5m]))
```

**Statuses:**
- `success` - Request completed successfully
- `error` - Internal server error (500)
- `timeout` - Request timed out (504)

#### `kronos_request_duration_seconds`
**Type:** Histogram
**Labels:** `route`
**Description:** Request latency distribution

**Buckets:** 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0 seconds

```promql
# p50 latency
histogram_quantile(0.50, rate(kronos_request_duration_seconds_bucket[5m]))

# p95 latency
histogram_quantile(0.95, rate(kronos_request_duration_seconds_bucket[5m]))

# p99 latency
histogram_quantile(0.99, rate(kronos_request_duration_seconds_bucket[5m]))

# Average latency
rate(kronos_request_duration_seconds_sum[5m])
  /
rate(kronos_request_duration_seconds_count[5m])
```

### Performance Metrics

#### `kronos_model_inference_seconds`
**Type:** Histogram
**Labels:** `endpoint`
**Description:** Model inference time (excluding pre/post processing)

**Buckets:** 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0 seconds

```promql
# p95 inference time
histogram_quantile(0.95, rate(kronos_model_inference_seconds_bucket[5m]))

# Compare endpoints
histogram_quantile(0.95,
  rate(kronos_model_inference_seconds_bucket{endpoint="/v1/predict/single"}[5m])
)
```

**Use Cases:**
- Identify performance bottlenecks
- Track model optimization improvements
- Compare single vs batch performance

#### `kronos_concurrent_requests`
**Type:** Gauge
**Description:** Number of requests currently being processed

```promql
# Current concurrent requests
kronos_concurrent_requests

# Max concurrent requests over time
max_over_time(kronos_concurrent_requests[5m])

# Average concurrent requests
avg_over_time(kronos_concurrent_requests[5m])
```

**Use Cases:**
- Monitor system load
- Identify peak traffic periods
- Capacity planning

#### `kronos_timeouts_total`
**Type:** Counter
**Labels:** `endpoint`
**Description:** Number of prediction timeouts

```promql
# Timeout rate
rate(kronos_timeouts_total[5m])

# Timeout percentage
rate(kronos_timeouts_total[5m]) / rate(kronos_requests_total[5m]) * 100
```

**Threshold:** Should be < 0.5%

#### `kronos_prediction_input_size`
**Type:** Histogram
**Labels:** `endpoint`
**Description:** Number of input candles per prediction

**Buckets:** 50, 100, 200, 400, 800, 1600

```promql
# p95 input size
histogram_quantile(0.95, rate(kronos_prediction_input_size_bucket[5m]))

# Average input size
rate(kronos_prediction_input_size_sum[5m])
  /
rate(kronos_prediction_input_size_count[5m])
```

**Use Cases:**
- Correlate input size with latency
- Identify unusual input patterns
- Optimize lookback window

### Security Metrics

#### `kronos_security_events_total`
**Type:** Counter
**Labels:** `event`, `container`
**Description:** Security events by type

**Event Types:**
- `unauthorized` - Container not in whitelist
- `blocked` - Request blocked by security middleware

```promql
# Security events by container
rate(kronos_security_events_total[5m])

# Unauthorized access attempts
rate(kronos_security_events_total{event="unauthorized"}[5m])
```

#### `kronos_rate_limit_hits_total`
**Type:** Counter
**Labels:** `container`
**Description:** Rate limit hits per container

```promql
# Rate limit hits by container
rate(kronos_rate_limit_hits_total[5m])

# Containers hitting rate limits frequently
topk(5, rate(kronos_rate_limit_hits_total[10m]))
```

**Threshold:** Excessive rate limiting (>1 req/s) may indicate:
- Misconfigured client
- Insufficient rate limit
- Potential abuse

#### `kronos_request_size_rejections_total`
**Type:** Counter
**Labels:** `container`
**Description:** Requests rejected due to size limits

```promql
# Size rejections
rate(kronos_request_size_rejections_total[5m])
```

## Prometheus Integration

### Step 1: Configure Scraping

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'kronos-api'
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: '/v1/metrics'
    static_configs:
      - targets: ['kronos-api:8000']
        labels:
          service: 'kronos-api'
          environment: 'production'
          team: 'ml-platform'
```

**Important:** Note the `metrics_path: '/v1/metrics'` - Kronos uses a versioned path.

See [monitoring/prometheus/prometheus-scrape-config.yml](../monitoring/prometheus/prometheus-scrape-config.yml) for complete examples.

### Step 2: Verify Scraping

**Check target status:**
```bash
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="kronos-api")'
```

**Expected output:**
```json
{
  "discoveredLabels": {...},
  "labels": {
    "job": "kronos-api",
    "instance": "kronos-api:8000"
  },
  "scrapeUrl": "http://kronos-api:8000/v1/metrics",
  "lastScrape": "2025-10-14T10:30:15.123Z",
  "health": "up"
}
```

### Step 3: Query Metrics

```bash
# Test query
curl -G http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=up{job="kronos-api"}'

# Should return: {"status":"success","data":{"resultType":"vector","result":[{"metric":{"job":"kronos-api"},"value":[1730715015,"1"]}]}}
```

### Network Requirements

**Ensure connectivity:**
```bash
# From Prometheus container
docker exec prometheus ping kronos-api

# If fails, check network:
docker network inspect monitoring
```

**Add Kronos to monitoring network:**
```yaml
# docker-compose.yml
services:
  kronos-api:
    networks:
      - kronos-internal
      - monitoring  # Add this

networks:
  monitoring:
    external: true
```

## Grafana Dashboard

### Importing the Dashboard

1. Open Grafana UI (e.g., http://grafana:3000)
2. Navigate to **Dashboards** → **Import**
3. Upload file: `monitoring/grafana/kronos-dashboard.json`
4. Select Prometheus datasource
5. Click **Import**

### Dashboard Panels

The pre-configured dashboard includes:

#### Panel 1: Request Rate
- **Visualization:** Time series
- **Metrics:** `rate(kronos_requests_total[1m])`
- **Shows:** Requests per second by endpoint and status

#### Panel 2: Total Request Rate
- **Visualization:** Gauge
- **Metrics:** `sum(rate(kronos_requests_total[1m]))`
- **Thresholds:** Yellow >50 req/s, Red >100 req/s

#### Panel 3: p95 Latency
- **Visualization:** Gauge
- **Metrics:** `histogram_quantile(0.95, rate(kronos_request_duration_seconds_bucket[5m]))`
- **Thresholds:** Yellow >2s, Red >5s

#### Panel 4: Latency Percentiles
- **Visualization:** Time series
- **Metrics:** p50, p95, p99 latency
- **Shows:** Latency distribution over time

#### Panel 5: Error & Timeout Rate
- **Visualization:** Time series
- **Metrics:** Error rate and timeout rate as percentages

#### Panel 6: Concurrent Requests
- **Visualization:** Time series
- **Metrics:** `kronos_concurrent_requests`
- **Shows:** System load over time

#### Panel 7: Model Inference Time
- **Visualization:** Time series
- **Metrics:** p50 and p95 inference time by endpoint

#### Panel 8: Input Size Distribution
- **Visualization:** Time series (bars)
- **Metrics:** p95 input size by endpoint

#### Panel 9: Security Events
- **Visualization:** Time series
- **Metrics:** Security events and rate limit hits by container

### Dashboard Variables

**Route Filter:**
- Variable: `$route`
- Type: Query
- Query: `label_values(kronos_requests_total, route)`
- Multi-select: Yes

**Usage:** Filter all panels by specific endpoints

## Alert Rules

### Loading Alert Rules

**Add to your `prometheus.yml`:**
```yaml
rule_files:
  - "alerts/*.yml"
  - "kronos-alerts.yml"  # Add this
```

**Copy alert file:**
```bash
cp monitoring/prometheus/kronos-alerts.yml /path/to/prometheus/alerts/
```

**Reload Prometheus:**
```bash
curl -X POST http://prometheus:9090/-/reload
```

### Alert Severity Levels

#### Critical (Immediate Action Required)

**KronosServiceDown**
- **Condition:** Service unreachable for 1 minute
- **Impact:** All predictions unavailable
- **Action:** Check container status, review logs

**KronosHighErrorRate**
- **Condition:** Error rate >5% for 2 minutes
- **Impact:** Users experiencing frequent failures
- **Action:** Check error logs, review recent deployments

**KronosModelNotLoaded**
- **Condition:** Service up but returning errors for 5 minutes
- **Impact:** All predictions failing (503 errors)
- **Action:** Check readiness endpoint, review model loading logs

#### Warning (Attention Needed)

**KronosHighLatency**
- **Condition:** p95 latency >5s for 5 minutes
- **Impact:** Slow predictions, potential timeouts
- **Action:** Check CPU usage, review concurrent requests, consider scaling

**KronosHighTimeoutRate**
- **Condition:** Timeout rate >0.5% for 3 minutes
- **Impact:** Some predictions timing out
- **Action:** Check inference time, review timeout configuration

**KronosHighMemoryUsage**
- **Condition:** Memory usage >90% for 5 minutes
- **Impact:** Risk of OOM kill
- **Action:** Check for memory leaks, consider increasing memory limit

**KronosExcessiveRateLimiting**
- **Condition:** Rate limit hits >1 req/s for 5 minutes
- **Impact:** Requests being rejected (429 errors)
- **Action:** Review rate limits, investigate client behavior

#### Info (Monitoring)

**KronosSlowInference**
- **Condition:** Model inference p95 >3s for 10 minutes
- **Impact:** Predictions slower than expected
- **Action:** Check CPU, review input size, consider optimization

**KronosLowThroughput**
- **Condition:** Request rate <0.1 req/s for 15 minutes
- **Impact:** May indicate upstream issues
- **Action:** Verify service accessibility, check client health

**KronosSecurityEvents**
- **Condition:** Unauthorized events >0.1 req/s for 5 minutes
- **Impact:** Potential security issue or misconfiguration
- **Action:** Review container whitelist, check security logs

### Alert Manager Integration

See [monitoring/prometheus/kronos-alerts.yml](../monitoring/prometheus/kronos-alerts.yml) for Alert Manager configuration examples including Slack, email, and PagerDuty integration.

## Logging

### Log Format

Kronos uses **structured JSON logging** for easy parsing and analysis.

**Example log entry:**
```json
{
  "timestamp": "2025-10-14T10:30:15.123Z",
  "level": "INFO",
  "logger": "kronos_fastapi.routes",
  "message": "single prediction completed",
  "request_id": "abc123-def456-ghi789",
  "container": "kronos-api-1",
  "endpoint": "/v1/predict/single",
  "series_id": "BTC-USDT",
  "latency_ms": 850,
  "rows": 400,
  "pred_len": 120,
  "status": "success"
}
```

### Log Levels

- **DEBUG:** Detailed diagnostic information
- **INFO:** General informational messages
- **WARNING:** Warning messages (e.g., slow requests, rate limits)
- **ERROR:** Error messages with stack traces
- **CRITICAL:** Critical failures

### Log Configuration

**Set log level via environment variable:**
```bash
KRONOS_LOG_LEVEL=INFO  # Default
KRONOS_LOG_LEVEL=DEBUG # Verbose logging
```

### Common Log Patterns

#### Successful Request
```json
{
  "level": "INFO",
  "message": "single prediction completed",
  "request_id": "abc123",
  "latency_ms": 850,
  "status": "success"
}
```

#### Failed Request
```json
{
  "level": "ERROR",
  "message": "single prediction failed",
  "request_id": "abc123",
  "error": "ValueError: Invalid input shape",
  "traceback": "..."
}
```

#### Timeout
```json
{
  "level": "WARNING",
  "message": "single prediction timeout",
  "request_id": "abc123",
  "timeout_seconds": 30
}
```

#### Rate Limit Hit
```json
{
  "level": "WARNING",
  "message": "Rate limit exceeded",
  "container": "unknown-container",
  "limit": "100 per 1 minute"
}
```

### Log Aggregation

**Recommended tools:**
- **Loki:** Grafana's log aggregation system
- **ELK Stack:** Elasticsearch, Logstash, Kibana
- **Fluentd:** Log collection and forwarding

**Example Loki configuration:**
```yaml
# promtail-config.yml
scrape_configs:
  - job_name: kronos-api
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '.*kronos-api.*'
        action: keep
```

## Troubleshooting

### Problem: Metrics not appearing

**Symptoms:**
- Prometheus target shows DOWN
- Queries return no data

**Diagnosis:**
```bash
# Check metrics endpoint
curl http://kronos-api:8000/v1/metrics

# Check network connectivity
docker exec prometheus ping kronos-api

# Check Prometheus targets
curl http://prometheus:9090/api/v1/targets
```

**Solutions:**
1. Verify `metrics_path: '/v1/metrics'` (not `/metrics`)
2. Ensure Prometheus can reach Kronos (network configuration)
3. Check Kronos is running: `docker ps | grep kronos-api`
4. Review Prometheus logs: `docker logs prometheus`

### Problem: Dashboard panels show "No Data"

**Symptoms:**
- Grafana dashboard imported but panels empty

**Diagnosis:**
```bash
# Verify metrics exist in Prometheus
curl -G http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=kronos_requests_total'

# Check datasource connection in Grafana
# Settings → Datasources → Prometheus → Test
```

**Solutions:**
1. Send test request to generate metrics: `curl http://kronos-api:8000/v1/healthz`
2. Wait for next scrape interval (15s)
3. Verify Prometheus datasource in Grafana
4. Check time range selector (set to "Last 1 hour")

### Problem: Alerts not firing

**Symptoms:**
- Expected alert not showing in Prometheus

**Diagnosis:**
```bash
# Check if alert rules loaded
curl http://prometheus:9090/api/v1/rules | jq '.data.groups[] | select(.name=="kronos_api_alerts")'

# Check alert status
curl http://prometheus:9090/api/v1/alerts
```

**Solutions:**
1. Verify alert file copied to correct location
2. Check syntax: `promtool check rules kronos-alerts.yml`
3. Reload Prometheus: `curl -X POST http://prometheus:9090/-/reload`
4. Trigger test condition to verify alert logic

### Problem: High memory usage in Prometheus

**Symptoms:**
- Prometheus memory growing over time

**Solutions:**
1. Reduce retention period:
   ```yaml
   command:
     - '--storage.tsdb.retention.time=15d'  # Default: 30d
   ```

2. Drop unnecessary metrics:
   ```yaml
   metric_relabel_configs:
     - source_labels: [__name__]
       regex: 'process_.*|python_.*'  # Drop Python internals
       action: drop
   ```

3. Increase scrape interval:
   ```yaml
   scrape_interval: 30s  # Instead of 15s
   ```

## Best Practices

### 1. Establish Baselines

- Run for 1 week to establish normal patterns
- Document baseline metrics (p50, p95, error rate)
- Adjust alert thresholds based on baselines

### 2. Monitor Key Metrics

**Must-watch metrics:**
- Request rate and latency (p95, p99)
- Error rate (<1%)
- Timeout rate (<0.5%)
- Concurrent requests
- Memory usage

### 3. Set Up Actionable Alerts

**Good alert:**
- Clear condition
- Known impact
- Defined action
- Appropriate severity

**Bad alert:**
- Flaps frequently
- No clear action
- Unclear impact

### 4. Use Dashboards for Investigation

**Workflow:**
1. Alert fires → Check dashboard
2. Dashboard shows spike → Check logs
3. Logs show error → Investigate code
4. Fix issue → Deploy
5. Monitor dashboard → Verify fix

### 5. Correlate Metrics

Look for relationships:
- High latency + high concurrent requests = capacity issue
- Error rate spike + recent deployment = bad release
- Memory growth + uptime = memory leak

### 6. Regular Review

**Monthly:**
- Review alert thresholds
- Check for new monitoring needs
- Update dashboards

**Quarterly:**
- Review retention policies
- Evaluate new observability tools
- Update runbooks

## Integration Examples

### Example 1: Complete Monitoring Stack

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./alerts:/etc/prometheus/alerts
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    volumes:
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=secure_password
    networks:
      - monitoring
    ports:
      - "3000:3000"

  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
    networks:
      - monitoring

networks:
  monitoring:
    name: monitoring
```

### Example 2: Add Kronos to Existing Setup

```bash
# 1. Copy monitoring files
cp -r monitoring/grafana /path/to/your/grafana/provisioning/dashboards/
cp monitoring/prometheus/kronos-alerts.yml /path/to/your/prometheus/alerts/

# 2. Update prometheus.yml (add Kronos scrape config)
# 3. Restart Prometheus
docker restart prometheus

# 4. Import dashboard in Grafana
# (Or use provisioning)
```

## Further Reading

- [Performance Guide](PERFORMANCE.md) - Performance optimization and load testing
- [Security Guide](SECURITY.md) - Security configuration and best practices
- [Monitoring Integration](../monitoring/README.md) - Quick start for monitoring setup

## Support

If you need help with observability:

1. Check this guide for configuration examples
2. Review [monitoring/README.md](../monitoring/README.md) for quick start
3. Test metrics endpoint: `curl http://kronos-api:8000/v1/metrics`
4. Check Prometheus targets: http://prometheus:9090/targets
5. Open an issue with logs and configuration

---

**Monitoring Approach:** Configuration-only (Integration with existing infrastructure)
**Last Updated:** 2025-10-14
**Next Review:** 2025-11-14
