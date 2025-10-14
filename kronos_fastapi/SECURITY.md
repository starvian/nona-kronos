# Security Model - Kronos FastAPI Microservice

**Last Updated:** 2025-10-14
**Security Model:** Internal Docker Network with Container Whitelisting

## Overview

The Kronos FastAPI microservice is designed for deployment in a trusted internal Docker network. The security model is simplified to reduce complexity while maintaining appropriate protection for internal container-to-container communication.

## Security Architecture

### Deployment Model

```
┌─────────────────────────────────────────────────────────┐
│ Docker Host                                              │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ kronos-internal (Docker Network - internal)    │    │
│  │                                                 │    │
│  │  ┌──────────────┐                              │    │
│  │  │ kronos-api   │ ← This service               │    │
│  │  │ (Port 8000)  │ ← NO external port mapping   │    │
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
│  External Access: BLOCKED ✗                             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Security Layers

### Layer 1: Network Isolation ⭐ Primary Defense

**Docker Internal Network**
- Service accessible ONLY from containers on `kronos-internal` network
- No external port mapping to host in production
- External access completely blocked

**Configuration** (`docker-compose.yml`):
```yaml
services:
  kronos-api:
    networks:
      - kronos-internal
    # NO ports section - no external access

networks:
  kronos-internal:
    driver: bridge
    internal: false  # Allow internet for model downloads only
```

### Layer 2: Container Whitelist

**Purpose:** Additional access control even within internal network

**How It Works:**
1. Extract container name from request (header or reverse DNS)
2. Check if container is in whitelist
3. Allow or reject (403 Forbidden)

**Configuration:**
```bash
# Environment variable in docker-compose.yml or .env
KRONOS_SECURITY_ENABLED=true
KRONOS_CONTAINER_WHITELIST=localhost,frontend-app,worker-service,scheduler
```

**Container Name Resolution:**
- **Method 1:** `X-Container-Name` header (if client sets it)
- **Method 2:** Reverse DNS lookup of client IP
- **Method 3:** IP address (fallback)

**Special Cases:**
- `localhost` always allowed (for development and health checks)
- Health check endpoints (`/v1/healthz`, `/v1/readyz`, `/metrics`) bypass whitelist

### Layer 3: Rate Limiting

**Purpose:** Prevent abuse and ensure fair resource sharing

**Configuration:**
```bash
KRONOS_RATE_LIMIT_ENABLED=true
KRONOS_RATE_LIMIT_PER_MINUTE=100  # Per container
```

**How It Works:**
- Rate limits enforced **per container** (not per IP)
- Uses container name/identifier as key
- Returns `429 Too Many Requests` when exceeded
- Headers show remaining quota

**Example Response:**
```
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1697304000
```

### Layer 4: Request Size Limits

**Purpose:** Prevent resource exhaustion from large payloads

**Configuration:**
```bash
KRONOS_MAX_REQUEST_SIZE_MB=10
```

**Enforcement:**
- Maximum request body: 10MB (configurable)
- Rejected requests return 413 Payload Too Large
- Logged for monitoring

### Layer 5: Non-Root Container User

**Purpose:** Minimize impact of container compromise

**Implementation** (Dockerfile):
```dockerfile
# Create non-root user
RUN groupadd -r kronos && useradd -r -g kronos -u 1000 kronos
USER kronos
```

## What's NOT Implemented (Intentionally)

These security features are **deferred** for the internal Docker network model:

❌ **API Key Authentication**
- **Reason:** All containers in internal network are trusted
- **When to add:** If exposing service externally or to untrusted containers

❌ **TLS/SSL Encryption**
- **Reason:** Internal Docker network provides network-level isolation
- **When to add:** If traffic leaves trusted network or compliance requires it

❌ **OAuth/JWT**
- **Reason:** No multi-tenancy or user-level authentication needed
- **When to add:** If user-specific access control required

❌ **Request Signing**
- **Reason:** Internal trusted network
- **When to add:** If need to prevent request tampering

## Configuration Guide

### Production Configuration

**File:** `docker-compose.yml`

```yaml
services:
  kronos-api:
    environment:
      # Security ENABLED
      - KRONOS_SECURITY_ENABLED=true
      - KRONOS_CONTAINER_WHITELIST=frontend-app,worker-service,scheduler
      - KRONOS_RATE_LIMIT_ENABLED=true
      - KRONOS_RATE_LIMIT_PER_MINUTE=100

    networks:
      - kronos-internal

    # NO ports section - internal only
```

### Development Configuration

**File:** `docker-compose.dev.yml`

```yaml
services:
  kronos-api:
    environment:
      # Security DISABLED for easy testing
      - KRONOS_SECURITY_ENABLED=false
      - KRONOS_RATE_LIMIT_ENABLED=false

    ports:
      - "8000:8000"  # Exposed for development
```

### Environment Variables

```bash
# Security
KRONOS_SECURITY_ENABLED=true           # Enable/disable security middleware
KRONOS_CONTAINER_WHITELIST=...         # Comma-separated container names

# Rate Limiting
KRONOS_RATE_LIMIT_ENABLED=true         # Enable/disable rate limiting
KRONOS_RATE_LIMIT_PER_MINUTE=100       # Requests per minute per container

# Request Limits
KRONOS_MAX_REQUEST_SIZE_MB=10          # Maximum request body size
```

## Security Metrics

Monitor security events via Prometheus metrics at `/v1/metrics`:

```prometheus
# Authorization events
kronos_security_events_total{event="authorized", container="frontend-app"}
kronos_security_events_total{event="unauthorized", container="unknown"}

# Rate limiting
kronos_rate_limit_hits_total{container="frontend-app"}

# Request size rejections
kronos_request_size_rejections_total{container="frontend-app"}
```

## Testing Security

### Test Container Whitelist

**Setup:**
```bash
# Start with test consumers
docker-compose -f docker-compose.test.yml up -d
```

**Test whitelisted access (should succeed):**
```bash
docker exec whitelisted-client curl -X GET \
  http://kronos-api:8000/v1/healthz
```

**Test unauthorized access (should get 403):**
```bash
docker exec unauthorized-client curl -X POST \
  http://kronos-api:8000/v1/predict/single \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Test Rate Limiting

```bash
# Make 150 requests rapidly (limit is 100/min)
for i in {1..150}; do
  docker exec whitelisted-client curl -X GET \
    http://kronos-api:8000/v1/healthz
  echo "Request $i"
done

# After 100 requests, should see 429 responses
```

### Test Request Size Limit

```bash
# Create a 15MB payload (exceeds 10MB limit)
dd if=/dev/zero bs=1M count=15 | base64 > large_payload.txt

docker exec whitelisted-client curl -X POST \
  http://kronos-api:8000/v1/predict/single \
  -H "Content-Type: application/json" \
  --data-binary @large_payload.txt

# Should return 413 Payload Too Large
```

## Incident Response

### Unauthorized Access Detected

**Symptoms:**
- `kronos_security_events_total{event="unauthorized"}` increasing
- 403 responses in logs

**Investigation:**
```bash
# Check logs for unauthorized attempts
docker logs kronos-api | grep "Unauthorized access"

# Check metrics
curl http://localhost:8000/v1/metrics | grep security_events
```

**Response:**
1. Identify the source container/IP
2. Verify if legitimate container missing from whitelist
3. Add to whitelist if legitimate:
   ```bash
   # Update .env
   KRONOS_CONTAINER_WHITELIST=...,new-container

   # Restart service
   docker-compose restart kronos-api
   ```
4. If malicious, investigate how untrusted container joined network

### Rate Limit Abuse

**Symptoms:**
- `kronos_rate_limit_hits_total` increasing rapidly
- Many 429 responses

**Investigation:**
```bash
# Check which container is hitting limits
docker logs kronos-api | grep "Rate limit"
curl http://localhost:8000/v1/metrics | grep rate_limit_hits
```

**Response:**
1. Identify abusive container
2. Check if legitimate spike (e.g., batch job)
3. Options:
   - Increase limit temporarily
   - Fix client to respect rate limits
   - Remove container from network if malicious

## Threat Model

### In-Scope Threats

✅ **Accidental Access** - Unintended containers accessing service
✅ **Resource Abuse** - Single container consuming all capacity
✅ **Large Payloads** - Memory exhaustion from huge requests
✅ **Container Escape** - Minimize impact if container compromised

### Out-of-Scope Threats

❌ **External Attackers** - No external network access
❌ **Malicious Containers** - All containers in network are trusted
❌ **Network Sniffing** - Internal network assumed secure
❌ **Advanced Persistent Threats** - Not a security-critical service

## When to Revisit Security Model

Consider adding stronger security if:

1. **External Exposure**
   - Service needs to be accessed from outside Docker network
   - Public internet access required
   - **Action:** Add API key authentication, TLS

2. **Untrusted Containers**
   - Third-party containers join network
   - Multi-tenant environment
   - **Action:** Add authentication, request signing

3. **Sensitive Data**
   - Service handles PII or financial data
   - Compliance requirements (HIPAA, PCI-DSS)
   - **Action:** Add encryption, audit logging, access controls

4. **High-Value Target**
   - Service becomes critical to business
   - Contains proprietary models/algorithms
   - **Action:** Full security audit, penetration testing

## Compliance

### Current Compliance

- ✅ **CIS Docker Benchmark**: Non-root user, read-only volumes
- ✅ **OWASP Top 10**: Rate limiting, request size limits
- ✅ **Least Privilege**: Minimal permissions, container isolation

### Not Currently Compliant

- ❌ **SOC 2**: No encryption in transit (TLS)
- ❌ **PCI-DSS**: No API authentication
- ❌ **HIPAA**: No audit logging, encryption

If compliance is required, see [COMPLIANCE.md](COMPLIANCE.md) for implementation guide.

## Security Contact

For security issues or questions:
- **GitHub Issues:** https://github.com/starvian/nona-kronos/issues
- **Label:** security
- **Response Time:** 48 hours for critical issues

---

**Security Model Version:** 1.0
**Last Security Review:** 2025-10-14
**Next Review:** 2026-04-14 (6 months)
