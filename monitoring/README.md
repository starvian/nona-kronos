# Kronos Monitoring Integration

This directory contains configuration files for integrating Kronos FastAPI service into your existing **centralized Prometheus/Grafana monitoring infrastructure**.

## Overview

**Important:** This is a **configuration-only** approach. We do NOT deploy Prometheus or Grafana containers with Kronos. Instead, we provide files that you can integrate into your existing monitoring setup.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Your Centralized Monitoring Infrastructure             │
│  ┌──────────────┐      ┌──────────────┐                │
│  │ Prometheus   │◄─────┤  Grafana     │                │
│  │              │      │              │                │
│  └──────┬───────┘      └──────────────┘                │
│         │                                                │
└─────────┼────────────────────────────────────────────────┘
          │
          ├─────────► Python Backend
          ├─────────► WordPress
          └─────────► Kronos FastAPI ← Add this
```

## Quick Start

### 1. Configure Prometheus Scraping

**Add Kronos to your `prometheus.yml`:**

```yaml
scrape_configs:
  # Your existing services...

  # Add Kronos
  - job_name: 'kronos-api'
    scrape_interval: 15s
    metrics_path: '/v1/metrics'
    static_configs:
      - targets: ['kronos-api:8000']
        labels:
          service: 'kronos-api'
          environment: 'production'
```

**Full example:** See [prometheus/prometheus-scrape-config.yml](prometheus/prometheus-scrape-config.yml)

### 2. Import Grafana Dashboard

1. Open your Grafana UI (e.g., http://grafana:3000)
2. Go to **Dashboards** → **Import**
3. Upload file: `grafana/kronos-dashboard.json`
4. Select your Prometheus datasource
5. Click **Import**

Done! ✅

### 3. Add Alert Rules (Optional)

**Merge alerts into your Prometheus configuration:**

```yaml
# In your prometheus.yml
rule_files:
  - "alerts/*.yml"
  - "kronos-alerts.yml"  # Add this
```

**Copy file:**
```bash
cp monitoring/prometheus/kronos-alerts.yml /path/to/your/prometheus/alerts/
```

**Reload Prometheus:**
```bash
curl -X POST http://prometheus:9090/-/reload
# Or restart Prometheus container
docker restart prometheus
```

## Files Included

### Grafana Dashboard
- **File:** `grafana/kronos-dashboard.json`
- **Description:** Pre-configured dashboard with 9 panels
- **Metrics Displayed:**
  - Request rate and total traffic
  - Latency percentiles (p50, p95, p99)
  - Error and timeout rates
  - Concurrent requests
  - Model inference time
  - Input size distribution
  - Security events

### Prometheus Alerts
- **File:** `prometheus/kronos-alerts.yml`
- **Alert Levels:**
  - **Critical:** Service down, high error rate, model not loaded
  - **Warning:** High latency, timeouts, memory issues, excessive rate limiting
  - **Info:** Slow inference, low throughput, security events

### Scrape Configuration Example
- **File:** `prometheus/prometheus-scrape-config.yml`
- **Description:** Complete example showing how to add Kronos to Prometheus
- **Includes:** Multiple deployment scenarios, troubleshooting tips

## Network Configuration

### Ensure Prometheus Can Reach Kronos

**Option 1: Add to Monitoring Network**

```yaml
# In your kronos docker-compose.yml
services:
  kronos-api:
    networks:
      - kronos-internal  # Internal business network
      - monitoring       # Monitoring network (external)

networks:
  kronos-internal:
    driver: bridge
  monitoring:
    external: true  # Connect to your existing monitoring network
```

**Option 2: Expose to Prometheus Network**

```yaml
# In your prometheus docker-compose.yml
services:
  prometheus:
    networks:
      - monitoring
    extra_hosts:
      - "kronos-api:192.168.1.100"  # Add Kronos host
```

## Verifying Integration

### 1. Check Metrics Endpoint

```bash
# From Prometheus container or same network
curl http://kronos-api:8000/v1/metrics

# Should return Prometheus format metrics:
# kronos_requests_total{route="/v1/predict/single",status="success"} 42
# ...
```

### 2. Check Prometheus Targets

1. Open Prometheus UI: http://prometheus:9090/targets
2. Find `kronos-api` job
3. Status should show **UP** (green)

### 3. Query Metrics

Open Prometheus graph: http://prometheus:9090/graph

Try these queries:
```promql
# Request rate
rate(kronos_requests_total[5m])

# p95 latency
histogram_quantile(0.95, rate(kronos_request_duration_seconds_bucket[5m]))

# Error rate
rate(kronos_requests_total{status="error"}[5m]) / rate(kronos_requests_total[5m])
```

### 4. View Dashboard

1. Open Grafana: http://grafana:3000
2. Go to **Dashboards** → **Kronos FastAPI Service**
3. Should display live metrics

## Available Metrics

### Request Metrics
```promql
kronos_requests_total{route, status}              # Total requests by endpoint and status
kronos_request_duration_seconds{route}            # Request latency histogram
```

### Performance Metrics
```promql
kronos_model_inference_seconds{endpoint}          # Model inference time
kronos_concurrent_requests                        # Current concurrent requests
kronos_timeouts_total{endpoint}                   # Timeout counter
kronos_prediction_input_size{endpoint}            # Input size distribution
```

### Security Metrics
```promql
kronos_security_events_total{event, container}    # Security events
kronos_rate_limit_hits_total{container}           # Rate limit hits
kronos_request_size_rejections_total{container}   # Size rejections
```

See [kronos_fastapi/OBSERVABILITY.md](../kronos_fastapi/OBSERVABILITY.md) for complete metrics reference.

## Troubleshooting

### Problem: Prometheus shows target as DOWN

**Check network connectivity:**
```bash
docker exec prometheus ping kronos-api
```

**Verify Kronos is running:**
```bash
docker ps | grep kronos-api
```

**Test metrics endpoint:**
```bash
curl http://kronos-api:8000/v1/metrics
```

### Problem: Metrics not appearing in Grafana

**Verify Prometheus is scraping:**
```bash
# Check targets page
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="kronos-api")'
```

**Check if metrics exist:**
```bash
curl -G http://prometheus:9090/api/v1/query --data-urlencode 'query=up{job="kronos-api"}'
```

**Verify dashboard datasource:**
- Open dashboard settings
- Check Prometheus datasource is selected
- Test connection

### Problem: Alerts not firing

**Verify alert rules loaded:**
```bash
curl http://prometheus:9090/api/v1/rules | jq '.data.groups[] | select(.name=="kronos_api_alerts")'
```

**Check alert status:**
```bash
curl http://prometheus:9090/api/v1/alerts
```

**Trigger test alert:**
```bash
# Stop Kronos to trigger KronosServiceDown alert
docker stop kronos-api

# Wait 1 minute for alert to fire
# Check: http://prometheus:9090/alerts
```

## Alert Configuration

### Severity Levels

- **Critical:** Immediate action required (service down, high errors)
- **Warning:** Attention needed (performance degradation)
- **Info:** Informational (monitoring, trends)

### Alert Manager Integration

See [prometheus/kronos-alerts.yml](prometheus/kronos-alerts.yml) for Alert Manager configuration examples.

**Notification Channels:**
- Slack
- Email
- PagerDuty
- Webhook

## Best Practices

1. **Start with default thresholds** - Adjust based on your traffic patterns
2. **Monitor for a week** - Establish baseline before tuning alerts
3. **Set up alert routing** - Critical alerts → immediate notification
4. **Create runbooks** - Document response procedures for each alert
5. **Regular review** - Update dashboards and alerts as service evolves

## Integration Examples

### Example 1: Single Prometheus for All Services

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'python-backend'
    static_configs:
      - targets: ['python-backend:8080']

  - job_name: 'wordpress'
    static_configs:
      - targets: ['wordpress-exporter:9117']

  - job_name: 'kronos-api'
    metrics_path: '/v1/metrics'
    static_configs:
      - targets: ['kronos-api:8000']
```

### Example 2: Kubernetes Deployment

```yaml
# ServiceMonitor for Kronos
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: kronos-api
spec:
  selector:
    matchLabels:
      app: kronos-api
  endpoints:
    - port: http
      path: /v1/metrics
      interval: 15s
```

### Example 3: Docker Compose with External Monitoring

```yaml
# docker-compose.yml
version: '3.8'

services:
  kronos-api:
    image: kronos-fastapi:latest
    networks:
      - monitoring  # External monitoring network

networks:
  monitoring:
    external: true
    name: monitoring_network
```

## Further Reading

- [Kronos Observability Guide](../kronos_fastapi/OBSERVABILITY.md) - Complete observability documentation
- [Performance Guide](../kronos_fastapi/PERFORMANCE.md) - Performance metrics and optimization
- [Security Guide](../kronos_fastapi/SECURITY.md) - Security metrics and monitoring

## Support

If you encounter issues integrating Kronos into your monitoring setup:

1. Check [OBSERVABILITY.md](../kronos_fastapi/OBSERVABILITY.md) for detailed guidance
2. Review Prometheus logs: `docker logs prometheus`
3. Test metrics endpoint: `curl http://kronos-api:8000/v1/metrics`
4. Open an issue on GitHub with logs and configuration

---

**Approach:** Configuration-only (no containers deployed)
**Target:** Centralized Prometheus/Grafana infrastructure
**Last Updated:** 2025-10-14
