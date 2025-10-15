# Device Support: CPU and GPU

This document describes the CPU and GPU support changes implemented in Kronos.

## Overview

Kronos now supports both **pure CPU** and **GPU** execution modes with graceful device fallback. The system automatically detects available hardware and falls back to CPU when GPU is unavailable.

## Key Changes

### 1. Device Resolution Module

**File**: `gitSource/model/device.py`

A new `resolve_device()` function provides:
- Auto-detection of best available device (cuda > mps > cpu)
- Explicit device selection (cpu, cuda, cuda:N, mps)
- Graceful fallback with warning messages
- Logging for troubleshooting

**Usage**:
```python
from model.device import resolve_device

device, warning = resolve_device("auto")  # Auto-detect
device, warning = resolve_device("cpu")   # Force CPU
device, warning = resolve_device("cuda:0") # Use GPU 0
```

### 2. Model Code Updates

**File**: `gitSource/model/kronos.py`

- `KronosPredictor.__init__`: Now calls `resolve_device()` to set `self.device` and `self.device_warning`
- Conditional CUDA calls: `torch.cuda.empty_cache()` only called when `device.type == "cuda"`

**Example**:
```python
predictor = KronosPredictor(
    model=model,
    tokenizer=tokenizer,
    device="auto",  # Will use GPU if available, else CPU
    max_context=512
)

print(f"Using device: {predictor.device}")
if predictor.device_warning:
    print(f"Warning: {predictor.device_warning}")
```

### 3. Dependency Management

**Base requirements** (`gitSource/requirements.txt`):
- Removed CUDA-specific packages (nvidia-*, triton)
- Works for CPU-only installations

**CUDA requirements** (`gitSource/requirements-cuda.txt`):
- Contains all nvidia-* and triton packages
- Required for GPU support

**Installation**:

For **CPU-only**:
```bash
pip install -r gitSource/requirements.txt
```

For **GPU support**:
```bash
pip install -r gitSource/requirements.txt
pip install -r gitSource/requirements-cuda.txt
```

### 4. Training Script Updates

**Files**: `gitSource/finetune/train_tokenizer.py`, `gitSource/finetune/train_predictor.py`

Both training scripts now support:
- Device resolution via `resolve_device()`
- CPU single-process training mode
- Automatic DDP detection: `use_ddp = device.type == "cuda" and WORLD_SIZE > 1`
- Conditional distributed operations (only when DDP is active)

**Usage**:

CPU training:
```bash
cd gitSource
python finetune/train_tokenizer.py --device cpu
python finetune/train_predictor.py --device cpu
```

GPU multi-GPU training (unchanged):
```bash
cd gitSource
torchrun --standalone --nproc_per_node=2 finetune/train_tokenizer.py
torchrun --standalone --nproc_per_node=2 finetune/train_predictor.py
```

GPU single-GPU training:
```bash
cd gitSource
python finetune/train_tokenizer.py --device cuda:0
```

### 5. Configuration Update

**File**: `gitSource/finetune/config.py`

Added `training_device` field:
```python
self.training_device = "auto"  # Options: "auto", "cpu", "cuda", "cuda:N", "mps"
```

### 6. FastAPI Service Integration

**Files**: 
- `services/kronos_fastapi/predictor.py`: Added `device` and `device_warning` properties
- `services/kronos_fastapi/schemas.py`: `ReadyResponse` includes device info
- `services/kronos_fastapi/routes.py`: `/v1/readyz` endpoint returns device status

**Example API response**:
```json
{
  "status": "ok",
  "model_loaded": true,
  "device": "cpu",
  "device_warning": "CUDA device 'cuda:0' requested but CUDA not available. Falling back to CPU."
}
```

### 7. WebUI Update

**File**: `gitSource/webui/app.py`

The `/api/load-model` endpoint now returns:
```json
{
  "success": true,
  "message": "Model loaded successfully: Kronos-small (24.7M) on cpu",
  "model_info": {
    "name": "Kronos-small",
    "device": "cpu",
    "device_warning": null
  }
}
```

## Testing

**Test script**: `gitSource/test_device_resolution.py`

Run the test to verify device resolution:
```bash
cd gitSource
python test_device_resolution.py
```

## Migration Guide

### For Existing Code

**Before**:
```python
predictor = KronosPredictor(model, tokenizer, device="cuda:0")
# Would fail if CUDA not available
```

**After**:
```python
predictor = KronosPredictor(model, tokenizer, device="auto")
# Automatically uses CPU if CUDA not available

# Check what device was actually used:
print(f"Using: {predictor.device}")
if predictor.device_warning:
    print(f"Warning: {predictor.device_warning}")
```

### For Docker Deployments

**CPU-only container**:
```dockerfile
FROM python:3.10-slim
COPY gitSource/requirements.txt .
RUN pip install -r requirements.txt
ENV KRONOS_DEVICE=cpu
```

**GPU container**:
```dockerfile
FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04
# Install Python...
COPY gitSource/requirements.txt gitSource/requirements-cuda.txt .
RUN pip install -r requirements.txt -r requirements-cuda.txt
ENV KRONOS_DEVICE=auto
```

## Design Ticket

For full design details, see: `services/tickets/TICKET_004_DES_Device-Agnostic-Kronos.md`

## Acceptance Criteria

All criteria from TICKET_004 have been met:

- ✅ Device resolution module (`model/device.py`)
- ✅ Conditional CUDA calls in inference code
- ✅ Split dependencies (base + CUDA-specific)
- ✅ CPU-compatible training scripts
- ✅ Service integration with device status
- ✅ WebUI device information display
- ✅ Test script for validation
- ✅ Documentation (this file)

## Troubleshooting

### "CUDA device requested but CUDA not available"

**Solution**: Install CUDA packages:
```bash
pip install -r gitSource/requirements-cuda.txt
```

Or force CPU mode:
```bash
export KRONOS_DEVICE=cpu
```

### Training fails with "NCCL error"

**Solution**: You're running distributed training without multiple GPUs. Use single-process:
```bash
python finetune/train_tokenizer.py --device cuda:0
# or
python finetune/train_tokenizer.py --device cpu
```

### "MPS device requested but MPS not available"

**Solution**: MPS is only available on Apple Silicon (M1/M2) with macOS 12.3+. Use CPU or CUDA instead:
```bash
export KRONOS_DEVICE=auto  # Will auto-detect
```

## Environment Variables

For FastAPI service:
- `KRONOS_DEVICE`: Device to use (`auto`, `cpu`, `cuda:0`, etc.)

Example:
```bash
cd gitSource
export KRONOS_DEVICE=cpu
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 8000
```

## Performance Notes

- **CPU inference**: Slower but works without GPU hardware
- **CPU training**: Much slower; recommended only for small experiments
- **GPU inference**: Fast, requires CUDA packages
- **GPU training**: Full speed, supports multi-GPU via DDP

## Related Files

- Design: `services/tickets/TICKET_004_DES_Device-Agnostic-Kronos.md`
- Test: `gitSource/test_device_resolution.py`
- Device module: `gitSource/model/device.py`
- Base requirements: `gitSource/requirements.txt`
- CUDA requirements: `gitSource/requirements-cuda.txt`
