# Kronos FastAPI Service - Device-Specific Deployment Guide

**Last Updated:** 2025-10-15
**Purpose:** Guide for deploying Kronos with CPU, GPU, or Hybrid (CPU+GPU) configurations

## Overview

The Kronos FastAPI service supports three deployment configurations:
- **Option A**: CPU-only deployment
- **Option B**: GPU-only deployment
- **Option C**: Hybrid deployment (CPU + GPU simultaneously)

## Quick Start

### Option A: CPU Deployment
```bash
cd services/kronos_fastapi
docker-compose -f docker-compose.cpu.yml up -d
```

### Option B: GPU Deployment
```bash
cd services/kronos_fastapi
docker-compose -f docker-compose.gpu.yml up -d
```

### Option C: Hybrid Deployment
```bash
cd services/kronos_fastapi
docker-compose -f docker-compose.hybrid.yml up -d

# With load balancer (recommended):
docker-compose -f docker-compose.hybrid.yml --profile loadbalancer up -d
```

## Detailed Deployment Instructions

### Option A: CPU-Only Deployment

#### When to Use
- Development and testing
- Light workloads (<50 requests/min)
- Limited hardware resources
- Cost-sensitive deployments

#### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 2+ CPU cores
- 4GB+ RAM

#### Configuration Files
- `docker-compose.cpu.yml` - Main configuration
- Uses `KRONOS_DEVICE=cpu` environment variable

#### Resource Allocation
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      cpus: '1.0'
      memory: 2G
```

#### Performance Characteristics
- **Throughput**: 10-50 requests/min
- **Latency**: 2-10s per prediction (depends on sequence length)
- **Memory**: 2-4GB usage
- **CPU**: 1-2 cores active

#### Deployment Steps

1. **Configure environment** (optional):
```bash
cat > .env <<EOF
KRONOS_MODEL_HOST_PATH=/data/ws/kronos/models
KRONOS_LOG_LEVEL=INFO
KRONOS_RATE_LIMIT_PER_MINUTE=100
KRONOS_MAX_REQUEST_SIZE_MB=10
EOF
```

2. **Start service**:
```bash
docker-compose -f docker-compose.cpu.yml up -d
```

3. **Verify deployment**:
```bash
# Check container status
docker ps | grep kronos-api-cpu

# Health check
curl http://kronos-api-cpu:8000/v1/healthz

# Readiness check (wait for model to load)
curl http://kronos-api-cpu:8000/v1/readyz
```

4. **Test prediction**:
```bash
curl -X POST http://kronos-api-cpu:8000/v1/predict/single \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      [100.0, 105.0, 98.0, 102.0],
      [102.0, 108.0, 101.0, 107.0]
    ],
    "pred_len": 10
  }'
```

5. **Monitor logs**:
```bash
docker-compose -f docker-compose.cpu.yml logs -f
```

#### Stopping Service
```bash
docker-compose -f docker-compose.cpu.yml down
```

---

### Option B: GPU-Only Deployment

#### When to Use
- Production workloads (>100 requests/min)
- Batch processing
- Low-latency requirements
- When GPU resources are available

#### Prerequisites
- NVIDIA GPU with CUDA support
- NVIDIA Docker runtime installed
- Docker 20.10+
- Docker Compose 2.0+
- 4+ CPU cores
- 8GB+ RAM

#### Install NVIDIA Docker Runtime

```bash
# Add NVIDIA package repositories
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install NVIDIA Docker runtime
sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Verify installation
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

#### Configuration Files
- `docker-compose.gpu.yml` - Main configuration
- Uses `KRONOS_DEVICE=cuda:0` environment variable
- Includes `runtime: nvidia` for GPU access

#### Resource Allocation
```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 8G
    reservations:
      cpus: '2.0'
      memory: 4G
      devices:
        - driver: nvidia
          device_ids: ['0']  # GPU device 0
          capabilities: [gpu]
```

#### Performance Characteristics
- **Throughput**: 100-500 requests/min
- **Latency**: 0.5-2s per prediction (10-20x faster than CPU)
- **Memory**: 4-8GB RAM + GPU memory
- **GPU**: Full utilization

#### Deployment Steps

1. **Verify GPU availability**:
```bash
nvidia-smi
```

Expected output should show available GPU(s).

2. **Configure environment** (optional):
```bash
cat > .env <<EOF
KRONOS_MODEL_HOST_PATH=/data/ws/kronos/models
KRONOS_LOG_LEVEL=INFO
KRONOS_DEVICE=cuda:0
NVIDIA_VISIBLE_DEVICES=0
KRONOS_RATE_LIMIT_PER_MINUTE=200
KRONOS_MAX_REQUEST_SIZE_MB=20
EOF
```

3. **Start service**:
```bash
docker-compose -f docker-compose.gpu.yml up -d
```

4. **Verify GPU access**:
```bash
# Check container has GPU access
docker exec kronos-api-gpu nvidia-smi

# Should show GPU information
```

5. **Verify deployment**:
```bash
# Check container status
docker ps | grep kronos-api-gpu

# Health check
curl http://kronos-api-gpu:8000/v1/healthz

# Readiness check
curl http://kronos-api-gpu:8000/v1/readyz

# Verify device is GPU
curl http://kronos-api-gpu:8000/v1/readyz | jq '.device'
# Should return: "cuda:0"
```

6. **Test prediction**:
```bash
curl -X POST http://kronos-api-gpu:8000/v1/predict/single \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      [100.0, 105.0, 98.0, 102.0],
      [102.0, 108.0, 101.0, 107.0]
    ],
    "pred_len": 10
  }'
```

7. **Monitor GPU usage**:
```bash
# Watch GPU utilization
watch -n 1 'docker exec kronos-api-gpu nvidia-smi'
```

#### Stopping Service
```bash
docker-compose -f docker-compose.gpu.yml down
```

#### Multi-GPU Configuration

To use multiple GPUs or specific GPU devices:

```bash
# Use GPU 1 instead of GPU 0
export NVIDIA_VISIBLE_DEVICES=1
export KRONOS_DEVICE=cuda:1
docker-compose -f docker-compose.gpu.yml up -d

# Use multiple GPUs (requires code modification for multi-GPU inference)
export NVIDIA_VISIBLE_DEVICES=0,1
```

---

### Option C: Hybrid Deployment (CPU + GPU)

#### When to Use
- Production environments with mixed workloads
- High availability requirements
- Workload separation (light requests → CPU, heavy → GPU)
- Maximum throughput optimization

#### Prerequisites
- All requirements from Option B (GPU deployment)
- Sufficient resources for both instances simultaneously
- NGINX for load balancing (included in configuration)

#### Architecture

```
                    ┌─────────────────┐
                    │  NGINX Load     │
                    │  Balancer       │
                    │  (Port 8080)    │
                    └────────┬────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
        ┌───────▼────────┐       ┌───────▼────────┐
        │  CPU Instance  │       │  GPU Instance  │
        │  (Port 8000)   │       │  (Port 8000)   │
        │  - Light load  │       │  - Heavy load  │
        │  - Single pred │       │  - Batch pred  │
        └────────────────┘       └────────────────┘
```

#### Configuration Files
- `docker-compose.hybrid.yml` - Main configuration (CPU + GPU + NGINX)
- `nginx.conf` - Load balancer configuration

#### Routing Strategy

The NGINX load balancer routes requests based on:

1. **URL Pattern** (default routing):
   - `/v1/predict/single` → CPU instance
   - `/v1/predict/batch` → GPU instance
   - `/v1/healthz`, `/v1/readyz`, `/v1/metrics` → CPU instance

2. **Custom Header** (override):
   - `X-Kronos-Device: cpu` → Force CPU
   - `X-Kronos-Device: gpu` → Force GPU

#### Resource Allocation

**CPU Instance:**
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      cpus: '1.0'
      memory: 2G
```

**GPU Instance:**
```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 8G
    reservations:
      cpus: '2.0'
      memory: 4G
      devices:
        - driver: nvidia
          device_ids: ['0']
          capabilities: [gpu]
```

**Total Resources Required:**
- CPU: 6 cores (2 for CPU instance + 4 for GPU instance)
- Memory: 12GB (4GB + 8GB)
- GPU: 1 device

#### Deployment Steps

1. **Configure environment** (optional):
```bash
cat > .env <<EOF
KRONOS_MODEL_HOST_PATH=/data/ws/kronos/models
KRONOS_LOG_LEVEL=INFO
KRONOS_LB_PORT=8080
NVIDIA_VISIBLE_DEVICES=0
EOF
```

2. **Start both instances** (without load balancer):
```bash
docker-compose -f docker-compose.hybrid.yml up -d
```

This starts:
- `kronos-api-cpu` - CPU instance
- `kronos-api-gpu` - GPU instance

3. **Start with load balancer** (recommended):
```bash
docker-compose -f docker-compose.hybrid.yml --profile loadbalancer up -d
```

This starts:
- `kronos-api-cpu` - CPU instance
- `kronos-api-gpu` - GPU instance
- `nginx-lb` - NGINX load balancer

4. **Verify both instances**:
```bash
# Check all containers
docker ps | grep kronos

# Health check CPU
curl http://kronos-api-cpu:8000/v1/healthz

# Health check GPU
curl http://kronos-api-gpu:8000/v1/healthz

# Health check load balancer
curl http://localhost:8080/v1/healthz
```

5. **Test routing**:
```bash
# Single prediction (should route to CPU)
curl -X POST http://localhost:8080/v1/predict/single \
  -H "Content-Type: application/json" \
  -d '{
    "data": [[100, 105, 98, 102]],
    "pred_len": 10
  }'

# Batch prediction (should route to GPU)
curl -X POST http://localhost:8080/v1/predict/batch \
  -H "Content-Type: application/json" \
  -d '{
    "batch": [
      {"data": [[100, 105, 98, 102]], "pred_len": 10},
      {"data": [[200, 205, 198, 202]], "pred_len": 10}
    ]
  }'
```

6. **Test custom routing**:
```bash
# Force CPU (even for batch)
curl -X POST http://localhost:8080/v1/predict/batch \
  -H "Content-Type: application/json" \
  -H "X-Kronos-Device: cpu" \
  -d '{"batch": [{"data": [[100, 105, 98, 102]], "pred_len": 10}]}'

# Force GPU (even for single)
curl -X POST http://localhost:8080/v1/predict/single \
  -H "Content-Type: application/json" \
  -H "X-Kronos-Device: gpu" \
  -d '{"data": [[100, 105, 98, 102]], "pred_len": 10}'
```

Check response headers - should include `X-Backend-Used` indicating which backend was used.

7. **Monitor both instances**:
```bash
# View all logs
docker-compose -f docker-compose.hybrid.yml logs -f

# View CPU logs only
docker-compose -f docker-compose.hybrid.yml logs -f kronos-api-cpu

# View GPU logs only
docker-compose -f docker-compose.hybrid.yml logs -f kronos-api-gpu

# View NGINX logs
docker-compose -f docker-compose.hybrid.yml logs -f nginx-lb
```

#### Stopping Service
```bash
# Stop all services
docker-compose -f docker-compose.hybrid.yml --profile loadbalancer down

# Stop without removing containers
docker-compose -f docker-compose.hybrid.yml stop
```

#### Custom NGINX Configuration

The default routing can be customized by editing `nginx.conf`:

```nginx
# Current default routing
map $request_uri $backend {
    default                     kronos_cpu;
    ~*/v1/predict/batch         kronos_gpu;  # Batch → GPU
}
```

**Alternative routing strategies:**

**1. Route based on request size:**
```nginx
# Route large requests to GPU
map $content_length $backend {
    default                     kronos_cpu;
    ~^[0-9]{5,}$               kronos_gpu;  # >10KB → GPU
}
```

**2. Round-robin between CPU and GPU:**
```nginx
upstream kronos_all {
    server kronos-api-cpu:8000;
    server kronos-api-gpu:8000;
}

location / {
    proxy_pass http://kronos_all;  # Round-robin
}
```

**3. Weighted load balancing:**
```nginx
upstream kronos_weighted {
    server kronos-api-cpu:8000 weight=1;
    server kronos-api-gpu:8000 weight=3;  # 75% GPU, 25% CPU
}
```

After modifying `nginx.conf`, reload NGINX:
```bash
docker-compose -f docker-compose.hybrid.yml exec nginx-lb nginx -s reload
```

---

## Performance Comparison

| Metric | CPU | GPU | Hybrid |
|--------|-----|-----|--------|
| **Setup Complexity** | Low | Medium | High |
| **Hardware Cost** | Low | High | Highest |
| **Throughput** | 10-50 req/min | 100-500 req/min | 110-550 req/min |
| **Latency (single)** | 2-10s | 0.5-2s | 0.5-2s (routed) |
| **Latency (batch)** | 10-60s | 2-10s | 2-10s (routed) |
| **Resource Usage** | 2 CPU, 4GB RAM | 4 CPU, 8GB RAM, 1 GPU | 6 CPU, 12GB RAM, 1 GPU |
| **High Availability** | Single point of failure | Single point of failure | Redundancy |

## Monitoring and Metrics

### Check Current Device
```bash
# CPU instance
curl http://kronos-api-cpu:8000/v1/readyz | jq '.device'
# Returns: "cpu"

# GPU instance
curl http://kronos-api-gpu:8000/v1/readyz | jq '.device'
# Returns: "cuda:0"
```

### Metrics Endpoints

Each instance exposes Prometheus metrics:
```bash
# CPU metrics
curl http://kronos-api-cpu:8000/v1/metrics

# GPU metrics
curl http://kronos-api-gpu:8000/v1/metrics

# Hybrid (aggregated via load balancer)
curl http://localhost:8080/v1/metrics
```

### Resource Monitoring

```bash
# Monitor all containers
docker stats

# Monitor specific instance
docker stats kronos-api-cpu
docker stats kronos-api-gpu

# Monitor GPU usage
watch -n 1 'docker exec kronos-api-gpu nvidia-smi'
```

## Troubleshooting

### CPU Deployment Issues

**Problem: High latency**
```bash
# Solution: Reduce sequence length or prediction length
export KRONOS_MAX_CONTEXT=256
export KRONOS_DEFAULT_PRED_LEN=60
```

**Problem: Out of memory**
```bash
# Solution: Increase memory limit in docker-compose.cpu.yml
limits:
  memory: 6G  # Increase from 4G
```

### GPU Deployment Issues

**Problem: GPU not detected**
```bash
# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Check Docker daemon has nvidia runtime
cat /etc/docker/daemon.json
# Should contain: "default-runtime": "nvidia"
```

**Problem: CUDA out of memory**
```bash
# Solution 1: Use smaller batch sizes
# Solution 2: Reduce max context
export KRONOS_MAX_CONTEXT=256

# Solution 3: Use different GPU
export NVIDIA_VISIBLE_DEVICES=1  # Use GPU 1 instead
```

### Hybrid Deployment Issues

**Problem: NGINX not routing correctly**
```bash
# Check NGINX logs
docker-compose -f docker-compose.hybrid.yml logs nginx-lb

# Test NGINX config
docker-compose -f docker-compose.hybrid.yml exec nginx-lb nginx -t

# Reload NGINX
docker-compose -f docker-compose.hybrid.yml exec nginx-lb nginx -s reload
```

**Problem: One instance not healthy**
```bash
# Check health of both instances
curl http://kronos-api-cpu:8000/v1/healthz
curl http://kronos-api-gpu:8000/v1/healthz

# NGINX will automatically route around unhealthy instances
```

## Best Practices

### Development
- Use **Option A (CPU)** for local development
- Keep resource limits reasonable
- Use hot-reload mode for faster iteration

### Staging
- Use **Option B (GPU)** to match production hardware
- Test with production-like workloads
- Validate GPU performance

### Production
- Use **Option C (Hybrid)** for maximum flexibility
- Enable monitoring and alerting
- Set up proper security (container whitelist, rate limiting)
- Use load balancer health checks
- Configure proper resource limits

---

**Related Documentation:**
- [Main Deployment Guide](DEPLOYMENT.md)
- [Service README](README.md)
- [CLAUDE.md](../../CLAUDE.md)
