# TICKET_006_TSK - Phase 4: Enhanced Observability

**Type:** Task
**Status:** In Progress
**Priority:** Medium
**Created:** 2025-10-14
**Related:** TICKET_002_PLN (Productionization Roadmap)

## Overview

Implement enhanced observability for Kronos FastAPI service following **Option 1: Minimized approach**. This phase provides configuration files and documentation for integration with existing centralized Prometheus/Grafana infrastructure, without deploying monitoring components.

## Scope - Minimized Approach ✅

### What We WILL Do:

1. **Grafana Dashboard JSON** ✅
   - Pre-configured Kronos-specific dashboard
   - Can be imported into any Grafana instance
   - Visualizes key metrics

2. **Prometheus Alert Rules Template** ✅
   - Alert rule definitions for Kronos
   - Can be merged into existing Prometheus config
   - Covers critical scenarios

3. **Documentation** ✅
   - How to connect to existing Prometheus
   - How to import Grafana dashboard
   - Metrics reference guide
   - Integration examples

4. **Enhanced Logging** ✅
   - Improve log context and structure
   - Add more diagnostic information
   - Better error messages

### What We Will NOT Do:

- ❌ Deploy Prometheus container
- ❌ Deploy Grafana container
- ❌ Create monitoring docker-compose
- ❌ Bundle monitoring stack with Kronos

**Rationale:** User has centralized Prometheus/Grafana monitoring multiple services (Python backend, WordPress, Kronos). We provide configuration files that can be integrated into their existing setup.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Centralized Monitoring (User's Infrastructure)         │
│  ┌──────────────┐      ┌──────────────┐                │
│  │ Prometheus   │◄─────┤  Grafana     │                │
│  │              │      │              │                │
│  └──────┬───────┘      └──────────────┘                │
│         │                                                │
└─────────┼────────────────────────────────────────────────┘
          │
          ├─────────► Python Backend (/metrics)
          │
          ├─────────► WordPress (exporter)
          │
          └─────────► Kronos FastAPI (/v1/metrics) ← We provide config
```

## Tasks

### 1. Grafana Dashboard JSON
**File:** `monitoring/grafana/kronos-dashboard.json`

**Panels:**
- Request rate (req/s)
- Request latency (p50, p95, p99)
- Error rate and types
- Timeout rate
- Concurrent requests
- Model inference time
- Input size distribution
- Security events (rate limits, rejections)

**Features:**
- Time range selector
- Variable filters (endpoint, status)
- Drill-down capabilities

### 2. Prometheus Alert Rules
**File:** `monitoring/prometheus/kronos-alerts.yml`

**Alerts:**
- High latency (p95 > 5s)
- High error rate (> 1%)
- High timeout rate (> 0.5%)
- Service unavailable
- High memory usage (> 90%)
- Rate limit excessive hits

**Severity Levels:**
- Critical: Service down, high error rate
- Warning: High latency, approaching limits

### 3. OBSERVABILITY.md Documentation
**File:** `kronos_fastapi/OBSERVABILITY.md`

**Contents:**
- Overview of observability approach
- Available metrics reference
- Prometheus integration guide
- Grafana dashboard import guide
- Alert rules setup
- Logging best practices
- Troubleshooting common issues
- Example Prometheus scrape config
- Example alert manager integration

### 4. Enhanced Logging

**Improvements:**
- Add request/response size to logs
- Add client IP/container name
- Add model inference breakdown timing
- Improve error context
- Add correlation IDs for related logs

**Changes in:**
- `logging_utils.py`: Enhanced log formatting
- `middleware.py`: Additional context capture
- `routes.py`: Better error logging

## Deliverables

### Files to Create:
1. ✅ `monitoring/grafana/kronos-dashboard.json` - Grafana dashboard
2. ✅ `monitoring/prometheus/kronos-alerts.yml` - Alert rules
3. ✅ `monitoring/prometheus/prometheus-scrape-config.yml` - Example scrape config
4. ✅ `kronos_fastapi/OBSERVABILITY.md` - Complete observability guide
5. ✅ `monitoring/README.md` - Quick start for monitoring integration

### Files to Update:
1. ✅ `logging_utils.py` - Enhanced logging
2. ✅ `middleware.py` - Additional context
3. ✅ `routes.py` - Better error messages
4. ✅ `README.md` - Reference to observability docs

## Integration Example

### User's Prometheus Config:
```yaml
# User's existing prometheus.yml
scrape_configs:
  - job_name: 'python-backend'
    static_configs:
      - targets: ['python-backend:8080']

  - job_name: 'wordpress'
    static_configs:
      - targets: ['wordpress-exporter:9117']

  # Add Kronos (copy from our example)
  - job_name: 'kronos-api'
    static_configs:
      - targets: ['kronos-api:8000']
    metrics_path: '/v1/metrics'
```

### User's Grafana:
1. Open Grafana UI
2. Import Dashboard
3. Upload `kronos-dashboard.json`
4. Done! ✅

## Success Criteria

- [ ] Dashboard JSON can be imported without errors
- [ ] All metrics display correctly in dashboard
- [ ] Alert rules are valid and can be loaded
- [ ] Documentation is clear and complete
- [ ] Enhanced logging provides better diagnostics
- [ ] No monitoring containers deployed with Kronos

## Testing

### Manual Testing:
1. Import dashboard into Grafana
2. Verify all panels display data
3. Trigger alerts by simulating conditions
4. Check enhanced logs provide context
5. Verify metrics endpoint works

### Integration Testing:
1. Test with user's existing Prometheus
2. Verify scrape config example works
3. Test dashboard with real traffic
4. Verify alerts fire correctly

## Timeline

- **Duration:** 2-3 hours
- **Complexity:** Medium

## Notes

- This is a **configuration-only** phase
- No containers to deploy
- User integrates into existing infrastructure
- Focus on documentation and ease of integration
- Provide examples but don't mandate specific tools

## References

- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
- [Prometheus Alerting Rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [FastAPI Observability](https://fastapi.tiangolo.com/advanced/middleware/#other-middlewares)

---

**Ticket Type:** Task (TSK)
**Phase:** 4 - Enhanced Observability
**Approach:** Option 1 - Minimized (Configuration Only)
**Created By:** Claude Code
**Last Updated:** 2025-10-14
