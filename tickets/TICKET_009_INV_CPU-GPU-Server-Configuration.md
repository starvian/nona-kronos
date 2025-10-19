# TICKET_009_INV - CPU/GPU Server Configuration Investigation

**Type**: Investigation (INV)
**Status**: Open
**Priority**: Medium
**Created**: 2025-10-15

## Problem Statement

Need to investigate and document whether the Kronos FastAPI service is currently deployed as:
1. Separate CPU and GPU versions
2. A single unified service with device selection
3. Other configuration patterns

This investigation is critical for understanding deployment architecture and planning future infrastructure scaling.

## Investigation Findings

### Current Architecture

Based on code review of the Kronos FastAPI service, here are the findings:

#### 1. **Single Unified Service - Not Separate CPU/GPU Versions**

The Kronos service is **NOT** split into separate CPU and GPU servers. Instead, it uses a **single unified codebase** with runtime device configuration.

**Evidence:**
- Single Dockerfile: `services/kronos_fastapi/Dockerfile`
- Single docker-compose configuration with device selection via environment variable
- Device configured via `KRONOS_DEVICE` environment variable in `config.py:18`

#### 2. **Device Configuration Methods**

**Environment Variable Approach:**
```yaml
# docker-compose.yml (Line 17)
environment:
  - KRONOS_DEVICE=${KRONOS_DEVICE:-cpu}  # Defaults to 'cpu'
```

**Supported Device Values:**
- `cpu` - CPU-only inference (default)
- `cuda:0` - GPU inference on CUDA device 0
- `cuda:1`, `cuda:2`, etc. - Multi-GPU support
- `mps` - Apple Metal Performance Shaders (macOS)

**Configuration File:**
```python
# config.py:18
device: str = Field("cpu", env="KRONOS_DEVICE")
```

#### 3. **Docker Compose Configurations**

**Production** (`docker-compose.yml`):
- Default: `KRONOS_DEVICE=${KRONOS_DEVICE:-cpu}`
- CPU-optimized resource limits:
  - CPUs: 2.0 limit, 1.0 reservation
  - Memory: 4GB limit, 2GB reservation
- No GPU runtime configuration currently present

**Development** (`docker-compose.dev.yml`):
- Same device configuration pattern
- No resource limits for flexibility
- Hot-reload enabled

#### 4. **Missing GPU Runtime Configuration**

**Critical Finding:** While the code supports GPU via `KRONOS_DEVICE=cuda:0`, the Docker configuration is missing GPU runtime setup:

```yaml
# MISSING in docker-compose.yml:
# deploy:
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
#           count: 1
#           capabilities: [gpu]
```

This means:
- ✅ Code is device-agnostic and ready for GPU
- ❌ Docker configuration doesn't expose GPU to container
- ⚠️ To use GPU, need to add NVIDIA runtime configuration

#### 5. **Current Deployment Pattern**

**Single Service, Multiple Deployment Options:**

The service can be deployed in three ways:

**Option A: CPU-only (Current Default)**
```bash
KRONOS_DEVICE=cpu docker-compose up
```

**Option B: GPU-enabled (Requires GPU Runtime)**
```bash
KRONOS_DEVICE=cuda:0 docker-compose up
# NOTE: Requires adding GPU configuration to docker-compose.yml
```

**Option C: Multiple Instances (CPU + GPU)**
```bash
# Run CPU instance on port 8000
KRONOS_DEVICE=cpu docker-compose up -d

# Run GPU instance on port 8001 (requires separate compose file)
KRONOS_DEVICE=cuda:0 docker-compose -f docker-compose.gpu.yml up -d
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│         Kronos FastAPI Service (Unified)            │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  config.py                                   │  │
│  │  - device: str = Field("cpu")                │  │
│  │    ├─ Configurable via KRONOS_DEVICE env     │  │
│  │    ├─ Supports: cpu, cuda:0, mps             │  │
│  │    └─ Set at container startup               │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Deployment Options:                         │  │
│  │                                              │  │
│  │  1. CPU-only    (KRONOS_DEVICE=cpu)         │  │
│  │  2. GPU-enabled (KRONOS_DEVICE=cuda:0)      │  │
│  │  3. Multi-instance (CPU + GPU separate)     │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Comparison: Current vs Separate CPU/GPU Approach

| Aspect | Current (Unified) | Separate CPU/GPU |
|--------|------------------|------------------|
| **Codebase** | Single codebase | Two separate services |
| **Maintenance** | Easier - one codebase | Harder - sync required |
| **Deployment** | Environment variable | Different containers |
| **Resource Optimization** | Manual tuning needed | Pre-optimized per device |
| **Scaling** | Horizontal scaling complex | Independent scaling |
| **Configuration** | Runtime device selection | Build-time specialization |

## Recommendations

### Short-term (Immediate)

1. **Add GPU Docker Compose Configuration**
   - Create `docker-compose.gpu.yml` with NVIDIA runtime
   - Document GPU deployment process
   - Add GPU-optimized resource limits

2. **Document Device Selection**
   - Update README with device configuration options
   - Add examples for CPU, GPU, and multi-instance deployments
   - Document hardware requirements

### Medium-term (1-2 weeks)

3. **Create Deployment Templates**
   - CPU-optimized: `docker-compose.cpu.yml`
   - GPU-optimized: `docker-compose.gpu.yml`
   - Hybrid: `docker-compose.hybrid.yml` (CPU + GPU instances)

4. **Add Resource Auto-Detection**
   - Detect available GPUs at startup
   - Warn if CUDA requested but not available
   - Add healthcheck for device availability

### Long-term (Future)

5. **Consider Multi-Instance Architecture**
   - Deploy separate CPU and GPU instances
   - Load balancer routes based on request type
   - CPU handles light requests, GPU handles heavy batches

6. **Add Device Pool Management**
   - Support multiple GPU devices
   - Automatic device selection based on load
   - Device affinity for request routing

## Technical Details

### File References

**Configuration:**
- `services/kronos_fastapi/config.py:18` - Device configuration
- `services/kronos_fastapi/docker-compose.yml:17` - Environment variable
- `services/kronos_fastapi/Dockerfile` - Single unified image

**Model Loading:**
- `model/kronos.py` - KronosPredictor accepts device parameter
- Device passed during model initialization in `predictor.py`

### Environment Variables

```bash
# Current environment variables for device control:
KRONOS_DEVICE=cpu           # CPU inference (default)
KRONOS_DEVICE=cuda:0        # GPU inference on device 0
KRONOS_DEVICE=cuda:1        # GPU inference on device 1
KRONOS_DEVICE=mps           # Apple Metal (macOS)

# Model path (same for CPU/GPU):
KRONOS_MODEL_PATH=/models

# Performance tuning (device-agnostic):
KRONOS_MAX_CONTEXT=512
KRONOS_DEFAULT_PRED_LEN=120
```

### Missing GPU Docker Configuration

To enable GPU support, add to `docker-compose.yml`:

```yaml
services:
  kronos-api:
    # ... existing config ...

    # Add GPU runtime (for NVIDIA GPUs):
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1  # or "all"
              capabilities: [gpu]
```

## Acceptance Criteria

- [x] Document current architecture (unified vs separate)
- [x] Identify device configuration mechanism
- [x] List all deployment options
- [x] Document missing GPU runtime configuration
- [x] Provide recommendations for improvements
- [x] Create GPU-enabled docker-compose template
- [x] Update documentation with device selection guide
- [x] Create hybrid deployment configuration
- [x] Create deployment scripts for all options
- [x] Document configuration priority and loading mechanism

## Related Tickets

- TICKET_001_IMP - FastAPI Production Readiness Assessment
- TICKET_002_PLN - Productionization Roadmap
- TICKET_003_DES - Kronos FastAPI Microservice Design
- TICKET_004_DES - Device-Agnostic Kronos (if exists)

## Implementation Summary (2025-10-15)

All recommendations have been implemented:

### Created Files

**Docker Compose Configurations:**
1. `services/kronos_fastapi/docker-compose.cpu.yml` - CPU-optimized deployment
2. `services/kronos_fastapi/docker-compose.gpu.yml` - GPU-optimized deployment with NVIDIA runtime
3. `services/kronos_fastapi/docker-compose.hybrid.yml` - Hybrid deployment (CPU + GPU + Load Balancer)

**Load Balancer:**
4. `services/kronos_fastapi/nginx.conf` - Smart routing configuration (single → CPU, batch → GPU)

**Deployment Scripts:**
5. `services/kronos_fastapi/deploy-cpu.sh` - CPU deployment convenience script
6. `services/kronos_fastapi/deploy-gpu.sh` - GPU deployment convenience script (includes GPU checks)
7. `services/kronos_fastapi/deploy-hybrid.sh` - Hybrid deployment script with routing tests

**Documentation:**
8. `services/kronos_fastapi/DEPLOYMENT_DEVICE_OPTIONS.md` - Comprehensive device deployment guide (16KB)
9. `services/MANUAL_DEPLOYMENT_CONFIGS.md` - Configuration priority and startup methods manual

### Configuration Loading Mechanism

**Priority Order (High to Low):**
```
1. Environment Variables (export/script)
2. .env file (services/kronos_fastapi/.env)
3. Code defaults (services/kronos_fastapi/config.py)
```

**Existing Startup Scripts:**
- `services/start_cpu_simple.sh` - Sets `KRONOS_DEVICE=cpu` + disables security (development)
- `services/start_cpu_simple_v2.sh` - Enhanced version with explicit timeout settings
- `services/start_gpu_simple.sh` - Sets `KRONOS_DEVICE=cuda:0` + GPU checks
- Manual `uvicorn` - Uses `.env` file or environment variables

### Deployment Options

| Option | Command | Use Case |
|--------|---------|----------|
| **A: CPU** | `./deploy-cpu.sh` | Development, light workloads |
| **B: GPU** | `./deploy-gpu.sh` | Production, high throughput |
| **C: Hybrid** | `./deploy-hybrid.sh --with-lb` | Production HA, workload separation |

### Routing Strategy (Hybrid)

**Automatic:**
- `/v1/predict/single` → CPU instance
- `/v1/predict/batch` → GPU instance

**Manual Override:**
- Header `X-Kronos-Device: cpu` → Force CPU
- Header `X-Kronos-Device: gpu` → Force GPU

---

**Status**: ✅ **COMPLETED** (2025-10-15)

**Conclusion**: The Kronos service is a **single unified service** with runtime device configuration via `KRONOS_DEVICE` environment variable. It is **NOT** split into separate CPU and GPU versions. All deployment options (CPU, GPU, Hybrid) have been implemented with complete documentation and convenience scripts.
